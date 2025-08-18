# Konfiguration
$ollamaUrl = "http://localhost:11434/api/embeddings"
$modelName = "snowflake-arctic-embed2"
$prompt = "Was ist die Hauptstadt von Frankreich?"
$numCalls = 100

# Speichert den vorherigen Vektor
$previousVector = $null
$vectorsAreEqual = $true

Write-Host "Starte Test der Ollama Embedding-Schnittstelle ($numCalls Aufrufe)..."
Write-Host "Modell: $modelName"
Write-Host "Prompt: '$prompt'"
Write-Host "--------------------------------------------------"

for ($i = 1; $i -le $numCalls; $i++) {
    Write-Host "Aufruf $i von $numCalls..."

    try {
        # JSON-Body für die Anfrage
        $body = @{
            model = $modelName
            prompt = $prompt
        } | ConvertTo-Json

        # API-Aufruf
        $response = Invoke-RestMethod -Uri $ollamaUrl -Method Post -ContentType "application/json" -Body $body

        # Überprüfen, ob die Antwort ein Embedding enthält
        if ($response.embedding) {
            $currentVector = $response.embedding

            # Beim ersten Durchlauf den Vektor speichern
            if ($previousVector -eq $null) {
                $previousVector = $currentVector
                Write-Host "Erster Vektor gespeichert."
            } else {
                # Vektoren vergleichen
                # Konvertiere beide Arrays in Strings für einen einfachen Vergleich
                # Alternativ könnte man elementweise vergleichen für Präzision, aber das ist für Gleichheit oft ausreichend
                $currentVectorString = ($currentVector | ForEach-Object { "$_" }) -join ","
                $previousVectorString = ($previousVector | ForEach-Object { "$_" }) -join ","

                if ($currentVectorString -ne $previousVectorString) {
                    Write-Warning "!!! ABWEICHUNG ERKANNT !!!"
                    Write-Warning "Aufruf $i : Aktueller Vektor weicht vom vorherigen ab."
                    Write-Warning "Vorheriger Vektor (Anfang): $($previousVector[0..4] -join ',')..."
                    Write-Warning "Aktueller Vektor (Anfang): $($currentVector[0..4] -join ',')..."
                    $vectorsAreEqual = $false
                    # Optional: Breche hier ab, wenn die erste Abweichung reicht
                    # break
                } else {
                    Write-Host "Vektor stimmt mit dem vorherigen überein."
                }
                $previousVector = $currentVector # Setze den aktuellen Vektor als vorherigen für den nächsten Durchlauf
            }
        } else {
            Write-Error "Fehler: 'embedding' Feld nicht in der Antwort gefunden für Aufruf $i."
            break
        }
    }
    catch {
        Write-Error "Fehler beim Aufruf der Ollama-Schnittstelle für Aufruf $i : $($_.Exception.Message)"
        break
    }

    Write-Host "--------------------------------------------------"
    Start-Sleep -Milliseconds 100 # Kurze Pause, um den Server nicht zu überlasten
}

Write-Host "`nTest beendet."
Write-Host $currentVectorString
if ($vectorsAreEqual) {
    Write-Host "Alle $numCalls Vektoren waren identisch." -ForegroundColor Green
} else {
    Write-Host "Es wurden Abweichungen in den Vektoren festgestellt." -ForegroundColor Red
}