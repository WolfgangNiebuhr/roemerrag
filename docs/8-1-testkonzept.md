# Testkonzept für den Podman-Betrieb

## Ziel und Umfang

Dieses Konzept beschreibt automatisierte Tests für den lokalen Betrieb des RAG-Systems mit Podman. Kubernetes-Manifeste und Kubernetes-spezifische Abläufe sind nicht Teil des Umfangs.

Das System besteht aus PostgreSQL mit pgvector, der Vector-API, Ollama, der RAG-API, dem Reranker sowie den Ingestion-Skripten. Die Tests sollen Datenhaltung und Schnittstellen absichern, die Zusammenarbeit der Dienste prüfen und einen reproduzierbaren Start mit Podman ermöglichen.

## Teststufen

| Stufe | Prüfumfang | Voraussetzungen |
|---|---|---|
| Komponententests | Eingabevalidierung, Fehlerbehandlung und RAG-Ablauf mit gemockten HTTP-Abhängigkeiten | Python; keine Container |
| Podman-Integration | Image-Build, PostgreSQL/pgvector, Vector-API, Persistenz und API-Verhalten | gestartete Podman-Machine |
| Ende zu Ende | Ingestion, Retrieval und Antwortgenerierung mit echten Modellen | vollständiger Stack und verfügbare Ollama-Modelle |
| Betrieb und Last | Neustarts, parallele Anfragen, Ressourcenverhalten und optionale GPU-Erkennung | Podman; GPU nur auf passender Hardware |

Jeder Integrationstest verwendet eindeutige Test-IDs, eine eigene Datenbank beziehungsweise ein eigenes Volume und räumt die eigenen Ressourcen am Ende auf. Produktive oder manuell genutzte Volumes dürfen nicht verwendet werden.

## Testfälle

### PostgreSQL und Vector-API

- Beim frischen Datenbankstart sind `vector`, Tabelle `vectors`, Unique Constraint auf `(chunk_id, embedding)` und der vorgesehene Index vorhanden.
- `POST /chunk` speichert einen Chunk; `GET /chunk/<chunk_id>` und `GET /chunks` liefern ihn zurück.
- Erneutes Speichern desselben Schlüssels aktualisiert den Eintrag und erzeugt keine Duplikate.
- `POST /search` liefert Treffer nach Distanz sortiert, sowohl mit Embedding-Filter als auch ohne Filter über mehrere Embedding-Werte hinweg, und begrenzt die Ergebnismenge über `num_results`.
- `DELETE /chunk` entfernt den Eintrag; die anschließende Suche beziehungsweise Zählung findet ihn nicht mehr.
- Ungültige Vektordimension, fehlende Felder, ungültiges JSON und nicht unterstützte Metriken werden kontrolliert beantwortet.
- Nach Neustart beziehungsweise Neuerstellung des Datenbankcontainers bleiben Daten im Named Volume erhalten.

Die bestehende Tabelle speichert Vektoren mit 1024 Dimensionen. Integrationstests müssen reproduzierbare Vektoren dieser Dimension verwenden, statt Zufallswerte.

### RAG-API

- Komponententests mocken Ollama und Vector-API und prüfen die Aufrufreihenfolge: Embedding, Suche, Kontextaufbereitung, Generierung.
- `/process` weist fehlendes oder leeres `query` zurück.
- Leere oder fehlerhafte Embeddings, HTTP-Fehler externer Dienste, unerwartete Suchantworten sowie Treffer ohne erwartete Felder werden geprüft.
- Integrationstests senden eine feste Frage an einen kleinen Testkorpus und prüfen Antwortschema, Metrikfelder und zurückgegebene Chunk-IDs.
- Modellantworten werden wegen ihrer Variabilität nicht wortgenau verglichen. Erwartete Treffer und fachliche Kriterien des Testkorpus sind stabiler.
- Eine Frage außerhalb des Testwissens prüft, dass die Antwort auf den bereitgestellten Kontext begrenzt bleibt.

### Reranker

- `/health` wird vor und nach dem Modellladen geprüft.
- Eine gültige Anfrage liefert jeden Eingabetext genau einmal, erhält `original_index`, gibt endliche numerische Scores zurück und sortiert absteigend nach Score.
- Fehlende Felder, falsche Typen und eine leere Dokumentliste werden geprüft.
- Modelllade- und Inferenzfehler liefern kontrollierte Fehlerantworten.
- GPU-Erkennung und Inferenz werden optional auf unterstützter Hardware geprüft; CPU dient als Referenz.

### Ingestion und Ende zu Ende

- Chunking wird mit einer kleinen versionierten Textdatei auf Anzahl, Reihenfolge, Grenzen und Overlap geprüft.
- Ein Import in eine Testdatenbank erzeugt die erwartete Anzahl Chunks mit passenden Metadaten.
- Eine Frage mit bekannter Antwort ruft erwartete Chunks ab; eine nicht beantwortbare Frage prüft die Ablehnungsantwort.

### Podman-Betrieb

- Datenbank und APIs starten mit den dokumentierten Images und Ports.
- Readiness wird für PostgreSQL geprüft, bevor die Vector-API startet, da diese ihren Verbindungspool beim Prozessstart erstellt.
- Logs und Containerstatus sind bei fehlgeschlagenem Start Teil der Diagnose.
- Einzelne Container sowie der gesamte Pod werden neu gestartet; Datenintegrität und Erreichbarkeit werden danach erneut geprüft.
- Die veröffentlichten Ports werden von der Host-Seite erreicht.

## Automatisierte Tests im Repository

Die Tests sind nach Art getrennt: echte Unit-Tests liegen unter `tests/unit`; Podman- und externe Dienst-Integrationstests liegen unter `tests/podman`.

| Pfad | Verantwortung |
|---|---|
| `tests/unit/test_rag_components.py` | RAG-Erfolgspfad mit gemockten Ollama-/Vector-Antworten sowie Embedding-, Retrieval- und Generierungsfehlerfälle. |
| `tests/unit/test_reranker_unit.py` | Reranker-Route mit Fake-Modell: Validierung, leere Dokumente, Rangfolge und Inferenzfehler. |
| `tests/unit/test_vector_api_unit.py` | Vector-API-Routen mit gemocktem PostgreSQL-Pool und Cursor. |
| `tests/unit/test_chunking.py` | UTF-8-Dateieinlesen, Splitter-Konfiguration und Unicode-Inhalt. |
| `tests/podman/test_vector_api.py` | HTTP-Integration für CRUD, Upsert sowie gefilterte und ungefilterte Suche gegen pgvector. |
| `tests/podman/test_rag_api.py` | HTTP-Eingabevalidierung der laufenden RAG-API. |
| `tests/podman/test_reranker.py` | HTTP-Integration für Health und Reranking mit geladenem Modell. |
| `tests/podman/test_ollama_embedding.py` | Aufrufe an die Ollama-Embedding-API auf dem Host. |
| `tests/conftest.py` | Gemeinsame Optionen (`--all`, `--include-*`, `--no-podman`, `--keep-podman`) und optionale Testauswahl. |
| `tests/podman/conftest.py` | Podman-Fixture für Image-Build, Pod/Volume, Readiness und Teardown. |
| `tests/pytest.ini` | Gemeinsame pytest-Konfiguration für beide Testgruppen. |

Die pytest-Konfiguration deaktiviert den Cache-Provider (`-p no:cacheprovider`), sodass kein Zugriff auf `.pytest_cache` erforderlich ist. Die Chunking-Tests legen eindeutige temporäre UTF-8-Dateien direkt unter `tests/unit` an und löschen sie nach jedem Test. Sie verwenden daher weder das Benutzer-Temp-Verzeichnis noch pytest `tmp_path`.

Ausführung aus dem Projektstamm:

```powershell
python -m pip install -r tests/podman/requirements.txt
# Nur Unit-Tests
python -m pytest -c tests/pytest.ini tests/unit
# Standard-Integration
python -m pytest -c tests/pytest.ini tests/podman
# Optionale Dienste
python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker
python -m pytest -c tests/pytest.ini tests/podman --include-ollama
# Unit- und alle Integrationstests
python -m pytest -c tests/pytest.ini tests --all
# Nur containerfreie Tests
python -m pytest -c tests/pytest.ini tests --no-podman
# Ressourcen zur Fehlersuche behalten
python -m pytest -c tests/pytest.ini tests --all --keep-podman
```

`--all` aktiviert RAG-, Reranker- und Ollama-Integrationstests. Der Reranker lädt sein Cross-Encoder-Modell beim Image-Build; Ollama muss unter `localhost:11434` laufen und das Modell `snowflake-arctic-embed2` bereitstellen. `--no-podman` überspringt explizit markierte Container-Tests und führt Unit-Tests weiter aus.

Die Standardintegration deckt PostgreSQL/pgvector und Vector-API ab. Der RAG-HTTP-Test prüft die Eingabevalidierung im Container; die RAG-Komponententests laufen mit gemockten Abhängigkeiten. Ein vollständiger RAG-Ende-zu-Ende-Test mit echtem Testkorpus ist noch offen. Ingestion-, Persistenz- und Lasttests sind weitere Ausbaustufen.
## Bestehende Lücken und Risiken

- RAG-URLs sind im Anwendungscode fest konfiguriert; Umgebungsvariablen würden Tests und Containerbetrieb flexibler machen.
- Die Vector-API validiert Metriken und Request-Schemata nicht vollständig.
- Die RAG-API setzt voraus, dass Treffer `metadata` und `chunk_id` enthalten.
- Es gibt keine einheitlichen Readiness-Endpunkte für alle Dienste.
- Modellbasierte Ergebnisse sind variabel und können durch Modellversion, Hardware oder Sampling beeinflusst werden.
- Der erste Image-Build kann durch Modell-Downloads oder externe Paketquellen zeitaufwendig sein; für reproduzierbare Läufe sollten Images und Modelle versioniert beziehungsweise zwischengespeichert werden.

## Empfohlene Ausbaureihenfolge

1. Vector-API-Integration einschließlich Persistenz und Request-Validierung vervollständigen.
2. RAG- und Reranker-Komponententests sowie Chunking-Tests ohne externe Dienste ergänzen.
3. Ingestion mit festem Testkorpus prüfen.
4. Ende-zu-Ende-Test mit Ollama-Modellen ergänzen.
5. Neustart-, Last- und optionale GPU-Prüfungen als getrennte, länger laufende Testgruppe ausführen.
