[CmdletBinding(DefaultParameterSetName = 'Build')]
param(
    [Parameter(ParameterSetName = 'Build')]
    [switch]$TestOnly,
    [Parameter(Mandatory, ParameterSetName = 'Deploy')]
    [ValidatePattern('^[0-9a-f]{12}$')]
    [string]$DeployTested
)

$ErrorActionPreference = 'Stop'

function Invoke-Podman {
    & podman @args
    if ($LASTEXITCODE -ne 0) {
        throw "Podman $($args[0]) failed with exit code $LASTEXITCODE."
    }
}

function Get-ApiContainer($Name) {
    (Invoke-Podman container inspect $Name | ConvertFrom-Json)[0]
}

function Wait-ApiHealth($Service) {
    $probe = "import json, sys, urllib.request; r = urllib.request.urlopen(sys.argv[1], timeout=5); sys.exit(json.load(r)['status'] != 'UP')"
    $url = "http://127.0.0.1:$($Service.Port)/actuator/health"
    $deadline = (Get-Date).AddMinutes(3)
    if ($Service.Name -eq 'reranker') { $deadline = (Get-Date).AddMinutes(10) }
    do {
        & podman exec $Service.Name python -c $probe $url *> $null
        if ($LASTEXITCODE -eq 0) { return }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "$($Service.Name) did not become healthy."
}

function Invoke-ApiCheck($Port, $Path, $Body, $Timeout = 15) {
    $options = @{Uri = "http://127.0.0.1:$Port$Path"; TimeoutSec = $Timeout}
    if ($null -ne $Body) {
        $options.Method = 'Post'
        $options.ContentType = 'application/json'
        $options.Body = ConvertTo-Json -InputObject $Body -Compress
    }
    Invoke-RestMethod @options
}

function Get-VectorState {
    $count = (Invoke-ApiCheck 5500 '/chunks').chunks
    $sets = @((Invoke-ApiCheck 5500 '/actuator/info').embeddingSetIds | Sort-Object)
    if ($null -eq $count) { throw 'Vector API did not return a chunk count.' }
    @{Count = $count; Sets = $sets}
}

function Get-DatabaseIdentity {
    $db = Get-ApiContainer 'vectordb'
    if (-not $db.State.Running) { throw 'vectordb must remain running.' }
    ConvertTo-Json -InputObject @($db.Id, $db.Image, $db.State.StartedAt, $db.Mounts) -Depth 8 -Compress
}

function Test-DeployedApis($Names, $Before) {
    $after = Get-VectorState
    if ($after.Count -ne $Before.Count -or ($after.Sets -join "`n") -cne ($Before.Sets -join "`n")) {
        throw 'Vector API returned a different chunk count or embedding set list.'
    }
    Write-Host "Vector API: $($after.Count) chunks in $($after.Sets.Count) embedding sets."

    if ('reranker' -in $Names) {
        $ranking = Invoke-ApiCheck 5000 '/rerank' @{
            query = 'What is Rome?'; documents = @('Rome is a city.', 'A fish swims.')
        } 60
        $scores = @($ranking.ranked_documents | ForEach-Object { $_.score })
        if (-not $ranking.model -or $scores.Count -ne 2) { throw 'Unexpected reranker response.' }
        foreach ($score in $scores) {
            if ($null -eq $score -or [double]::IsNaN($score) -or [double]::IsInfinity($score)) {
                throw 'Reranker did not return two finite scores.'
            }
        }
        Write-Host "Reranker: two finite scores from $($ranking.model)."
    }

    if ('rag-api' -in $Names) {
        $variant = 'snowflake-arctic-embed2-v2'
        $payload = @{query = 'Wer war Hannibal?'; embedding_set_id = $variant; answer_model = 'phi3:mini'; top_k = 0}
        if ('reranker' -in $Names) {
            $payload.top_k = 2
            $payload.reranker = $ranking.model
        }
        $result = Invoke-ApiCheck 5600 '/process' $payload 240
        if ($result.status -ne 'ok' -or [string]::IsNullOrWhiteSpace($result.response) -or -not $result.chunks) {
            throw 'RAG API did not generate an answer with retrieved chunks.'
        }
        if ($payload.top_k -and (@($result.chunks).Count -ne 2 -or $result.reranking.model -ne $ranking.model)) {
            throw 'RAG API did not return the expected reranked chunks.'
        }
        $chunk = [uri]::EscapeDataString($result.chunks[0])
        $stored = Invoke-ApiCheck 5500 "/chunks/${chunk}?embedding_set_id=$variant"
        if ([string]::IsNullOrWhiteSpace($stored.chunktext)) { throw 'Vector API did not return the stored chunk.' }
        Write-Host "RAG API: answer with $(@($result.chunks).Count) selected chunks. Vector API read $chunk."
    }
}

$mutex = New-Object System.Threading.Mutex($false, 'Local\RoemerRagApiImageUpdate')
$locked = $false
$runId = [guid]::NewGuid().ToString('N').Substring(0, 12)
$report = Join-Path ([System.IO.Path]::GetTempPath()) "rag-update-$runId.xml"
$previousTestImages = $env:RAG_TEST_API_IMAGES
$previousPytestOptions = $env:PYTEST_ADDOPTS
Push-Location (Join-Path $PSScriptRoot '..')
try {
    try { $locked = $mutex.WaitOne(0) }
    catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'An API update is already running.' }

    $definitions = @(
        @{Name = 'reranker'; Image = 'reranker'; Port = 5000}
        @{Name = 'vector-api'; Image = 'vectorapi'; Port = 5500}
        @{Name = 'rag-api'; Image = 'rag-api'; Port = 5600}
    )
    $running = @(Invoke-Podman ps --format '{{.Names}}')
    $services = @($definitions | Where-Object { $_.Name -in $running })
    if ('vector-api' -notin $services.Name) {
        throw 'The running stack must include a container named vector-api.'
    }

    $images = @{}
    foreach ($service in $services) {
        $name = $service.Name
        $service.Previous = Get-ApiContainer $name
        $command = $service.Previous.Config.CreateCommand
        $nameIndex = [array]::IndexOf($command, '--name')
        $imageIndex = -1
        $imageReferences = @($service.Previous.ImageName, $service.Previous.Config.Image,
            $service.Previous.Image, "sha256:$($service.Previous.Image)")
        foreach ($reference in $imageReferences) {
            if (-not $reference) { continue }
            $imageIndex = [array]::IndexOf($command, $reference)
            if ($imageIndex -ge 0) { break }
        }
        if ($command[1] -notin @('run', 'create') -or $nameIndex -lt 2 -or
            $imageIndex -le ($nameIndex + 1) -or
            ($command -match '^--(?:rm|replace|cidfile)(?:=|$)')) {
            throw "Unsupported launch command for $name."
        }
        $service.Candidate = "$name-candidate-$runId"
        $service.Backup = "$name-before-update-$runId"
        $arguments = @($command[2..($imageIndex - 1)])
        $arguments[$nameIndex - 1] = $service.Candidate
        $service.CreateOptions = @($arguments | Where-Object { $_ -notin @('-d', '--detach') })
        $service.Command = @()
        if ($imageIndex -lt ($command.Count - 1)) {
            $service.Command = @($command[($imageIndex + 1)..($command.Count - 1)])
        }
    }

    $manifestDir = Join-Path $PWD 'artifacts/tested-api-images'
    if ($DeployTested) {
        $manifest = Get-Content -LiteralPath (Join-Path $manifestDir "$DeployTested.json") -Raw | ConvertFrom-Json
        $testedImages = @($manifest.PSObject.Properties.Name)
        if (Compare-Object @($services.Image | Sort-Object) @($testedImages | Sort-Object)) {
            throw 'The tested image set does not match the running API services.'
        }
        foreach ($service in $services) {
            $id = $manifest.($service.Image)
            if ($id -notmatch '^(sha256:)?[0-9a-f]{64}$' -or
                (Invoke-Podman image inspect --format '{{.Id}}' $id) -cne $id) {
                throw "Tested image for $($service.Name) is unavailable or invalid."
            }
            $images[$service.Image] = $id
        }
    } else {
        foreach ($service in $services) {
            $tag = "localhost/$($service.Image):update-$runId"
            & python -B scripts/build_image.py $service.Image --tag $tag --refresh
            if ($LASTEXITCODE -ne 0) { throw "Build failed for $($service.Name)." }
            $images[$service.Image] = Invoke-Podman image inspect --format '{{.Id}}' $tag
        }

        $testOptions = @()
        $excluded = @()
        if ('rag-api' -in $services.Name) {
            $testOptions += '--include-rag', '--include-ollama'
        } else {
            $excluded += 'not rag', 'not ollama'
        }
        if ('reranker' -in $services.Name) {
            $testOptions += '--include-reranker'
        } else {
            $excluded += 'not reranker'
        }
        if ($excluded.Count) { $testOptions += '-m', ($excluded -join ' and ') }
        $env:RAG_TEST_API_IMAGES = ConvertTo-Json -InputObject $images -Compress
        $env:PYTEST_ADDOPTS = ''
        & python -B -m pytest -c tests/pytest.ini tests/podman "--junitxml=$report" @testOptions
        if ($LASTEXITCODE -ne 0) { throw 'Integration tests failed.' }
        $results = [xml](Get-Content -LiteralPath $report -Raw)
        if (@($results.SelectNodes('//testcase')).Count -eq 0 -or
            $results.SelectSingleNode('//skipped | //failure | //error')) {
            throw 'Integration tests did not all run successfully.'
        }
        New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
        $manifestPath = Join-Path $manifestDir "$runId.json"
        ConvertTo-Json -InputObject $images | Set-Content -LiteralPath $manifestPath -Encoding UTF8
        Write-Host "Tested release: $runId. Deploy with -DeployTested $runId."
        if ($TestOnly) { return }
    }

    $current = @(Invoke-Podman ps --format '{{.Names}}')
    foreach ($service in $services) {
        if ($service.Name -notin $current -or
            (Get-ApiContainer $service.Name).Id -ne $service.Previous.Id) {
            throw "Container $($service.Name) changed during testing."
        }
    }
    foreach ($definition in $definitions) {
        if ($definition.Name -in $current -and $definition.Name -notin $services.Name) {
            throw "Container $($definition.Name) started during testing."
        }
    }

    $database = Get-DatabaseIdentity
    $vectorState = Get-VectorState
    $prepared = @()
    try {
        foreach ($service in $services) {
            $options = $service.CreateOptions
            $command = $service.Command
            Invoke-Podman create @options $images[$service.Image] @command | Out-Null
            $prepared += $service
        }
        foreach ($service in $services) {
            $service.SwitchStarted = $true
            Invoke-Podman stop $service.Name | Out-Null
            Invoke-Podman rename $service.Name $service.Backup
            $service.PreviousRenamed = $true
            Invoke-Podman rename $service.Candidate $service.Name
            $service.CandidateRenamed = $true
            Invoke-Podman start $service.Name | Out-Null
            Wait-ApiHealth $service
        }
        foreach ($service in $services) { Wait-ApiHealth $service }
        Test-DeployedApis $services.Name $vectorState
        if ((Get-DatabaseIdentity) -cne $database) {
            throw 'vectordb identity, start time or mounts changed during rollout.'
        }
    } catch {
        [array]::Reverse($prepared)
        foreach ($service in $prepared) {
            try {
                if ($service.CandidateRenamed) {
                    if ((Get-ApiContainer $service.Name).State.Running) {
                        Invoke-Podman stop $service.Name | Out-Null
                    }
                    Invoke-Podman rename $service.Name $service.Candidate
                }
                if ($service.PreviousRenamed) {
                    Invoke-Podman rename $service.Backup $service.Name
                }
                if ($service.SwitchStarted -and -not (Get-ApiContainer $service.Name).State.Running) {
                    Invoke-Podman start $service.Name | Out-Null
                }
                Invoke-Podman rm $service.Candidate | Out-Null
            } catch { Write-Warning "Rollback for $($service.Name) failed. Previous container ID: $($service.Previous.Id)." }
        }
        throw
    }
    foreach ($service in $services) {
        Write-Output "$($service.Name) updated. Previous container: $($service.Backup)"
    }
} finally {
    $env:RAG_TEST_API_IMAGES = $previousTestImages
    $env:PYTEST_ADDOPTS = $previousPytestOptions
    if (Test-Path -LiteralPath $report) { Remove-Item -LiteralPath $report }
    Pop-Location
    if ($locked) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
