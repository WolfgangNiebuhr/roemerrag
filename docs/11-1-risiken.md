# 11.1 Risiken

Stand: 22.11.2026. Dieses Register enthält ausschließlich ausdrücklich als Risiko markierte Einträge. Technische Schulden werden separat in [Abschnitt 11.2](11-2-technische-schulden.md) geführt und gelten nicht automatisch als Risiken. Risiken erhalten eine eigene Nummerierung mit dem Präfix R.

## R-01 – Manuelle Zuordnung von Importvarianten · Akzeptiertes Risiko

- **Befund:** `embedding_set_id` ist eine frei gewählte Kennung. Import3 und Retrieval können Modell und Set unabhängig konfigurieren; die Datenbank speichert und prüft keine vollständige Verarbeitungskonfiguration. Eine Set-ID allein belegt daher weder Chunking, Anreicherung und Prompts noch das tatsächlich verwendete Modell und die Normalisierung.
- **Entscheidung vom 21.11.2026:** Keine zusätzliche technische Speicherung oder Absicherung dieser Konfiguration. Stattdessen wird die Zuordnung manuell im [Set-ID-Verzeichnis, arc42-Abschnitt 8.2](8-2-embedding-sets.md) gepflegt. Die [Architekturentscheidung 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026) ersetzt den bisherigen Vorschlag einer persistierten Variantenkonfiguration.
- **Manuelle Behandlung:** Vor einem Import die tatsächlichen Parameter zum Set dokumentieren; bei geänderter Verarbeitung eine neue Set-ID verwenden. Evaluationen nennen die verwendete Set-ID. Unbekannte historische Angaben bleiben ausdrücklich unbekannt; der aktuelle Codezustand ist kein vollständiger Herkunftsnachweis für Bestandsvektoren. Ein erneutes Embedding ist hierfür nicht erforderlich.
- **Akzeptiertes Restrisiko:** Eine falsche Kennung oder veraltete Dokumentation kann unterschiedliche Verarbeitungen unter derselben Set-ID vermischen. Gleiche `(chunk_id, embedding_set_id)` können überschrieben werden; Vergleiche werden dadurch schwer erklärbar oder nicht wiederholbar. Das Verzeichnis unterstützt die Nachvollziehbarkeit, verhindert solche Fehler aber nicht technisch. Es besteht kein offener Implementierungsauftrag für die ursprünglich vorgeschlagene Konfigurationspersistenz. Importlaufprobleme bleiben TS-05; Modellrevisionen und Buildstände behandelt TS-15.

Herkunft: bisheriger Eintrag TS-04.

## R-02 Dateistamm als Dokumentidentitaet

**Status: Akzeptiertes Risiko, Entscheidung vom 22.11.2026.**

- **Regel:** Chunk-IDs verwenden den Dateinamen ohne die letzte Erweiterung und eine bei 1 beginnende Chunknummer, beispielsweise rom.band1-1 aus rom.band1.txt. Der Dateistamm muss innerhalb eines Embedding-Sets eindeutig sein; Verzeichnis und Erweiterung gehoeren nicht zum Schluessel.
- **Akzeptiertes Restrisiko:** Dateien wie rom.txt und rom.md besitzen denselben Stamm und erzeugen im selben Set dieselben Chunk-IDs. Auch gleiche Dateinamen aus verschiedenen Verzeichnissen kollidieren. Atomare Upserts koennen dadurch fremde Chunks ueberschreiben; bei unterschiedlichen Chunkzahlen koennen vermischte Restbestaende entstehen. Retrieval und Qualitaetsmessungen koennen dadurch falsche Quellen enthalten.
- **Manuelle Behandlung:** Vor Import Dateistaemme innerhalb des Sets eindeutig halten; kollidierende Quellen umbenennen oder unterschiedlichen Sets zuordnen. Keine automatische Erweiterungs-/Verzeichniskennung oder technische Kollisionsregistrierung vorgesehen. Gleichnamige Dateien in verschiedenen Sets kollidieren wegen des zusammengesetzten Datenbankschluessels nicht.
- **Abgrenzung:** Die Korrektur von erster auf letzte Erweiterung bleibt als Codeaenderung unter TS-05 offen. Kuerzere Wiederholungsimporte, Fehlerabschluss und Resume bleiben ebenfalls TS-05. Das Risiko akzeptiert keine unbeabsichtigte Loeschung von Bestandsdaten und ersetzt keinen Umstellungsplan.

Konzept: [Kapitel 8.4.7](8-4-importkonzept.md#847-identitaet-wiederholung-und-abschluss).
