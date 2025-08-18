# Test-Skript für die REST-API
# Globale Variable für die Dimensionen
$globalDimensions = 1024

# Funktion zur Erzeugung eines zufälligen Vektors
function Generate-RandomVector {
    param (
        [int]$dimensions = $globalDimensions  # Standardmäßig aus globaler Variable
    )
    $vector = @()
    for ($i = 0; $i -lt $dimensions; $i++) {
        $vector += (Get-Random -Minimum -1.0 -Maximum 1.0)  # Zufällige Werte zwischen -1.0 und 1.0
    }
    return $vector
}


# Basis-URL der API
$baseUrl = "http://localhost:5500"

# Header für die Anfragen
$headers = @{
    "Content-Type" = "application/json"
}

# Testdaten für den POST-Endpunkt /vectors
$vectorData1 = @{
    chunk_id = "chunk1"
    embedding = "embedding1"
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    metadata = "Test-Metadaten 1"
} | ConvertTo-Json -Depth 10

$vectorData2 = @{
    chunk_id = "chunk2"
    embedding = "embedding2"
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    metadata = "Test-Metadaten 2"
} | ConvertTo-Json -Depth 10

$vectorData3 = @{
    chunk_id = "chunk3"
    embedding = "embedding1"
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    metadata = "Test-Metadaten 3"
} | ConvertTo-Json -Depth 10

$vectorData4 = @{
    chunk_id = "chunk4"
    embedding = "embedding1"
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    metadata = "Test-Metadaten 4"
} | ConvertTo-Json -Depth 10

$vectorData5 = @{
    chunk_id = "chunk5"
    embedding = "embedding2"
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    metadata = "Test-Metadaten 5"
} | ConvertTo-Json -Depth 10

$vectorData6 = @{
    chunk_id = "chunk5"
    embedding = "embedding2"
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    metadata = "Test-Metadaten 6"
} | ConvertTo-Json -Depth 10

Write-Host "Teste POST /vectors..."
$responsePost1 = Invoke-WebRequest -Uri "$baseUrl/chunk" -Method POST -Headers $headers -Body $vectorData1
$responsePost2 = Invoke-WebRequest -Uri "$baseUrl/chunk" -Method POST -Headers $headers -Body $vectorData2
$responsePost3 = Invoke-WebRequest -Uri "$baseUrl/chunk" -Method POST -Headers $headers -Body $vectorData3
$responsePost4 = Invoke-WebRequest -Uri "$baseUrl/chunk" -Method POST -Headers $headers -Body $vectorData4
$responsePost5 = Invoke-WebRequest -Uri "$baseUrl/chunk" -Method POST -Headers $headers -Body $vectorData5
$responsePost6 = Invoke-WebRequest -Uri "$baseUrl/chunk" -Method POST -Headers $headers -Body $vectorData6

Write-Host "Antwort von POST /chunk:"
Write-Host $responsePost1.Content
Write-Host $responsePost2.Content
Write-Host $responsePost3.Content
Write-Host $responsePost4.Content
Write-Host $responsePost5.Content
Write-Host $responsePost6.Content

# Test des POST-Endpunkts /search ohne embedding-Filter
$searchData1 = @{
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    num_results = 5
    metric = "euclidean"
} | ConvertTo-Json -Depth 10

Write-Host "Teste POST /search ohne embedding-Filter..."
$responseSearch1 = Invoke-WebRequest -Uri "$baseUrl/search" -Method POST -Headers $headers -Body $searchData1
Write-Host "Antwort von POST /search ohne embedding-Filter:"
Write-Host $responseSearch1.Content

# Test des POST-Endpunkts /search mit embedding-Filter
$searchData2 = @{
    vector = (Generate-RandomVector -dimensions $globalDimensions)
    num_results = 5
    metric = "euclidean"
    embedding = "embedding1"
} | ConvertTo-Json -Depth 10

Write-Host "Teste POST /search mit embedding-Filter..."
$responseSearch2 = Invoke-WebRequest -Uri "$baseUrl/search" -Method POST -Headers $headers -Body $searchData2
Write-Host "Antwort von POST /search mit embedding-Filter:"
Write-Host $responseSearch2.Content
