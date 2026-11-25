# Dokumentimport

Die Pipeline liest eine UTF-8-Textdatei, zerlegt sie in Chunks, ergänzt optional Keywords und speichert Text und Embeddings über die Vector-API. Bei aktivierter Anreicherung wird derselbe Text eingebettet und gespeichert: Keywords, Zeilenumbruch und Originalchunk.

## Voraussetzungen

Alle Befehle aus dem Projektstamm ausführen. In der Python-Umgebung müssen `requests` und der von diesem Projekt verwendete LangChain-Textsplitter verfügbar sein. Für einen vollständigen Import müssen die Vector-API und Ollama mit den ausgewählten Modellen laufen. Die Einrichtung der Dienste steht im [Projekt-README](../README.md).

## Vollständiger Import

```powershell
python -m Ingest.pipeline --file Ingest/pg3060.txt --config Ingest/experiments/snowflake-arctic-embed-v2.json --output-dir artifacts/pg3060/run-001
```

Jeder Lauf benötigt ein neues Ausgabeverzeichnis. Beim Retrieval die `embedding_set_id` aus der Konfiguration verwenden. Für den Aufruf oben ist das `snowflake-arctic-embed-v2`.

| Konfiguration und Set-ID | Chunking | Anreicherung |
|---|---|---|
| [test-recursive-1000](experiments/test-recursive-1000.json) | 1.000 Zeichen, 150 Überlappung, Absatz- und Satztrennzeichen mit Zeichen-Fallback | Keine |
| [snowflake-arctic-embed-v1](experiments/snowflake-arctic-embed-v1.json) | LangChain-Standardtrennzeichen, 1.000 Zeichen, 100 Überlappung | Keine |
| [snowflake-arctic-embed-v2](experiments/snowflake-arctic-embed-v2.json) | Chunkgrenzen wie `import3.py`, 1.000 Zeichen, 150 Überlappung, ohne Zeichen-Fallback | `gemma3:4b` mit `keywords-v1` |

Alle drei Beispiele verwenden `snowflake-arctic-embed2` mit 1.024 Dimensionen und L2-Normalisierung. Für eigene Versuche eine Konfiguration kopieren und bei geänderter Verarbeitung eine eigene Set-ID vergeben. Die Zuordnung wird im [Set-Verzeichnis](../docs/8-2-embedding-sets.md) gepflegt.

Unter `chunking.parameters.separators` kann eine geordnete Liste literaler Trennzeichen angegeben werden. Standard ist `["\n\n", ".\n", ". ", ""]`. Ein leeres letztes Element aktiviert den Zeichen-Fallback. Ohne dieses Element können lange ungetrennte Passagen die konfigurierte Chunkgröße überschreiten. Für Keywords `enrichment.strategy` auf `keywords` setzen. `enrichment.parameters.model` und `enrichment.parameters.prompt` wählen das Modell und die Promptversion.

## Chunking und Wiederverwendung

```powershell
python -m Ingest.chunk --file Ingest/pg3060.txt --config Ingest/experiments/test-recursive-1000.json --output artifacts/pg3060/chunks.json
python -m Ingest.pipeline --from chunks --input artifacts/pg3060/chunks.json --config Ingest/experiments/test-recursive-1000.json --output-dir artifacts/pg3060/run-002
```

`Ingest.chunk` benötigt weder Ollama noch die Vector-API. Mit `--from chunks` beginnt die Pipeline bei der Anreicherung. Mit `--from enriched --input <Pfad zu enriched.json>` beginnt sie beim Embedding. Die Chunking-Einstellungen und bei `--from enriched` auch die Anreicherungseinstellungen müssen zum Artefakt passen.

## Keyword-Experimente

Erzeuge `chunks.json` einmal und verwende es als Eingabe für alle Varianten. Das Beispiel startet mit derselben Konfiguration wie der vollständige Import oben. Für einen schnellen Vergleich kann `--file` auf eine kurze repräsentative UTF-8-Datei zeigen.

```powershell
python -m Ingest.chunk --file Ingest/pg3060.txt --config Ingest/experiments/snowflake-arctic-embed-v2.json --output artifacts/keywords/chunks.json
python -m Ingest.enrich --input artifacts/keywords/chunks.json --config Ingest/experiments/snowflake-arctic-embed-v2.json --output artifacts/keywords/baseline/enriched.json
```

Kopiere für jede Variante die JSON-Konfiguration und verwende einen eigenen Ausgabepfad. Belasse die Chunking-Einstellungen und ändere `enrichment.parameters.model` für einen Modellvergleich oder `enrichment.parameters.prompt` für einen Promptvergleich.

- `keywords-v1` verwendet den ausführlichen Import3-Prompt mit längenabhängiger Keyword-Anzahl.
- `keywords-v2` verwendet einen kürzeren Prompt für bis zu fünf Stichwörter in der Originalschreibweise.
- Für einen eigenen Systemprompt setze in `enrichment.parameters` beispielsweise `"prompt": "ortsbegriffe-v1"` und `"system_prompt": "Extrahiere nur Ortsnamen als kommaseparierte Liste."`. Der Originalchunk ist dann die User-Nachricht. Vergib für Änderungen am Prompttext eine neue Version.

`Ingest.enrich` benötigt für die Keyword-Strategie nur Ollama. Die Konfiguration braucht `format_version`, `chunking` und `enrichment`. Für jede Variante enthält `enriched.json` das Modell, die Promptversion, die Originalchunks, die Keywords im Feld `enrichment` und den zusammengesetzten `chunktext`. Pro Chunk enthält `enrichment_metrics` die gemessene Anfragezeit in Sekunden (`request_seconds`), Ollama-Zeiten in Nanosekunden (`total_duration`, `load_duration`, `prompt_eval_duration`, `eval_duration`) und Tokenzahlen (`prompt_eval_count`, `eval_count`). Fehlende Providerwerte sind `null`.

Mit `Ingest.pipeline --from enriched` kannst du die gewählte Variante einbetten und speichern. Verwende dafür eine vollständige Konfiguration mit derselben Chunking- und Anreicherungseinstellung sowie der gewünschten Set-ID.

## Dienstadressen und Zeitlimits

| Umgebungsvariable | Standard |
|---|---|
| `OLLAMA_HOST_URL` | `http://localhost:11434` |
| `IMPORT_VECTOR_URL` | `http://127.0.0.1:5500/vectors` |
| `IMPORT_CONNECT_TIMEOUT` | 5 Sekunden |
| `IMPORT_KEYWORD_TIMEOUT` | 120 Sekunden |
| `IMPORT_EMBED_TIMEOUT` | 300 Sekunden |
| `IMPORT_STORE_TIMEOUT` | 60 Sekunden |

**IPv6 und `localhost` unter Windows.** Python kann `localhost` zuerst zu `::1` auflösen. Ist der veröffentlichte Podman-Port der Vector-API nur über IPv4 erreichbar, wartet Python auf die Ablehnung der IPv6-Verbindung, bevor es `127.0.0.1` versucht. In der lokalen Messung kostete das rund zwei Sekunden pro Verbindungsversuch. Der Standard `127.0.0.1` verbindet sich direkt über IPv4. Für einen anderen Host oder Port lässt sich `IMPORT_VECTOR_URL` weiterhin setzen.

## Abbruch, Wiederaufnahme und Teilimport

Die Pipeline berechnet und speichert jeden Chunk einzeln. Bei einem Fehler bricht sie sofort ab. Bereits gespeicherte Chunks sind abrufbar. Bis ein Lauf erfolgreich beendet ist, kann die Datenbank sowohl alte als auch neue Chunks enthalten.

Beim Abbruch gibt die Pipeline die Nummer des ersten noch nicht bestätigten Chunks aus. Starte mit dem angezeigten `--start`, derselben Eingabe und Konfiguration, derselben Vector-API-Adresse und einem neuen Ausgabeverzeichnis. Nach einer verlorenen Speicherantwort kann der betroffene Chunk erneut per Upsert geschrieben werden. Wenn sich die Quelldatei seit dem Abbruch geändert hat, kannst du das im bisherigen Ausgabeverzeichnis gespeicherte `chunks.json` mit `--from chunks --input …` verwenden. Bei einem Import aus `enriched.json` verwende wieder dasselbe Anreicherungsartefakt.

Für einen **neuen Lauf ab Chunk 5**, auch nach einem erfolgreichen Import:

```powershell
python -m Ingest.pipeline --file Ingest/pg3060.txt --start 5 --config Ingest/experiments/snowflake-arctic-embed-v2.json --output-dir artifacts/rom/run-003
```

`--start` zählt ab 1. Die Pipeline verwendet die Chunknummern des vollständigen neuen Inputs und lässt alle Chunks vor dem Startpunkt unangetastet. Der bestehende Präfix muss zum gewünschten Datenstand passen. Mit der Nummer unmittelbar nach dem letzten Chunk wird nur bereinigt. Nach dem letzten bestätigten Write löscht die Pipeline alle Chunks oberhalb der Gesamtzahl für denselben Dateistamm im selben Set. Scheitert die Bereinigung, gibt die Pipeline die Nummer nach dem letzten Chunk für einen reinen Bereinigungslauf aus. Importiere dasselbe Dokument im selben Set jeweils mit einem Lauf zur Zeit.

Ein erfolgreicher Lauf ab Chunk 1 schreibt vollständige Anreicherungs- und Embeddingartefakte. Läufe ab einem späteren Chunk speichern das Eingabeartefakt. Exitcode 0 steht für Abschluss einschließlich Bereinigung, 1 für Abbruch und 2 für ungültige Eingaben. Die Pipeline ruft zur Bereinigung `DELETE /chunks` mit `document_id`, `embedding_set_id` und `from` gleich Gesamtzahl plus eins auf. Eine Schemaänderung ist dafür nicht erforderlich.
