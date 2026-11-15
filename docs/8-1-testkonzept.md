# Testkonzept für den Podman-Betrieb

Stand: 15.11.2026. Komponenten beschreibt die [Bausteinsicht](5-bausteinsicht.md), Abläufe und Ollama-Netzwerkgrenzen die [Laufzeitsicht](6-laufzeitsicht.md).

## Ziel und Umfang

Dieses Konzept beschreibt automatisierte Tests für den lokalen Betrieb des RAG-Systems mit Podman. Kubernetes-Manifeste und Kubernetes-spezifische Abläufe sind nicht Teil des Umfangs.

Das System besteht aus PostgreSQL mit pgvector, der Vector-API, Ollama, der RAG-API, dem Reranker sowie den Ingestion-Skripten. Die Tests sollen Datenhaltung und Schnittstellen absichern, die Zusammenarbeit der Dienste prüfen und einen reproduzierbaren Start mit Podman ermöglichen.

## Teststufen

Die [Verteilungssicht](7-verteilungssicht.md) beschreibt den isolierten Test-Pod, dynamische Hostports, das eigene Datenvolume und den gemeinsam genutzten Windows-Ollama-Dienst im Vergleich zum regulären Betrieb.

| Stufe | Prüfumfang | Voraussetzungen |
|---|---|---|
| Komponententests | Eingabevalidierung, Fehlerbehandlung und RAG-Ablauf mit gemockten HTTP-Abhängigkeiten | Python; keine Container |
| Podman-Integration | Image-Build, PostgreSQL/pgvector, Vector-API und API-Verhalten; Persistenz nach Neustart noch offen | gestartete Podman-Machine |
| Ende zu Ende | Kleinkorpus importieren, Retrieval und Antwortgenerierung mit echten Modellen | Teststack mit RAG-API, Host-Ollama mit Embedding- und Antwortmodell; kein Reranker nötig |
| Betrieb und Last (geplant) | Neustarts, parallele Anfragen, Ressourcenverhalten und optionale GPU-Erkennung | Podman; GPU nur auf passender Hardware |

Containerbasierte Integrationstests teilen pro Testsitzung einen isolierten Pod mit eigener Datenbank und eigenem Volume. Namen und Datenkennungen enthalten eine eindeutige Test-ID. Am Ende werden Testressourcen entfernt, außer bei `--keep-podman`. Produktive oder manuell genutzte Volumes dürfen nicht verwendet werden. Ollama ist ein externer, gemeinsam genutzter Host-Dienst; der eigenständige Embedding-Test benötigt weder Pod noch Testvolume.

Der Test-Pod veröffentlicht die benötigten APIs auf dynamisch von Podman vergebenen Hostports. Die Fixtures ermitteln diese am Infrastrukturcontainer; Readiness und HTTP-Tests verwenden dieselben Ports. PostgreSQL benötigt keinen Hostport. Die RAG-API erhält `VECTOR_API_URL=http://127.0.0.1:5500/search`, sodass sie innerhalb des Test-Pods auf die Testdaten zugreift, auch wenn ein regulärer Stack parallel läuft. `tests/unit/test_podman_stack_config.py` prüft diese Konfiguration ohne Container.

## Zielkatalog der Testfälle

Die folgenden Fälle beschreiben das Testziel. Nicht jeder Fall ist bereits automatisiert; der Abschnitt „Automatisierte Tests im Repository“ beschreibt den tatsächlichen Bestand. Insbesondere Schema-/Indexinspektion, Persistenz nach Neustart, vollständige Requestvalidierung, nicht beantwortbare Fragen, Last und GPU-Verhalten sind noch nicht vollständig abgedeckt.

### PostgreSQL und Vector-API

- Beim frischen Datenbankstart sind `vector`, Tabelle `vectors`, Unique Constraint auf `(chunk_id, embedding)` und der vorgesehene Index vorhanden.
- `POST /chunk` speichert einen Chunk; `GET /chunk/<chunk_id>` liefert ihn zurück, `GET /chunks` zählt die gespeicherten Zeilen im Feld `count`.
- Erneutes Speichern desselben Schlüssels aktualisiert den Eintrag und erzeugt keine Duplikate.
- `POST /search` liefert Treffer nach Distanz sortiert, sowohl mit Embedding-Filter als auch ohne Filter über mehrere Embedding-Werte hinweg, und begrenzt die Ergebnismenge über `num_results`.
- `DELETE /chunk` entfernt den Eintrag; die anschließende Suche beziehungsweise Zählung findet ihn nicht mehr.
- Ungültige Vektordimension, fehlende Felder, ungültiges JSON und nicht unterstützte Metriken werden kontrolliert beantwortet.
- Nach Neustart beziehungsweise Neuerstellung des Datenbankcontainers bleiben Daten im Named Volume erhalten.

Die bestehende Tabelle speichert Vektoren mit 1024 Dimensionen. CRUD-/Suchtests verwenden feste synthetische Vektoren dieser Dimension. Der E2E-Test verwendet echte normalisierte Ollama-Embeddings; deren konkrete Werte werden nicht fest verglichen.

### RAG-API

- Komponententests mocken Ollama und Vector-API und prüfen die Aufrufreihenfolge: Embedding, Suche, Kontextaufbereitung, Generierung.
- `/process` weist fehlendes oder leeres `query` zurück.
- Leere oder fehlerhafte Embeddings, HTTP-Fehler externer Dienste, unerwartete Suchantworten sowie Treffer ohne erwartete Felder werden geprüft.
- Integrationstests senden eine feste Frage an einen kleinen Testkorpus und prüfen Antwortschema, Metrikfelder und zurückgegebene Chunk-IDs.
- Modellantworten werden wegen ihrer Variabilität nicht wortgenau verglichen. Erwartete Treffer und fachliche Kriterien des Testkorpus sind stabiler.
- Eine Frage außerhalb des Testwissens prüft, dass die Antwort auf den bereitgestellten Kontext begrenzt bleibt.

### Reranker

- Ziel ist die Prüfung von Health und Modellladefehlern. Die aktuelle App lädt vor jeder ersten Anfrage, auch vor `/health`; ein sichtbarer HTTP-Health-Zustand vor dem Laden ist daher im aktuellen Ablauf nicht gewährleistet.
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
| `tests/unit/test_ollama_endpoint.py` | Explizite Adresse, WSL-Gateway-Dekodierung, Fallback, Cache und erneuter Versuch nach fehlgeschlagener Ermittlung. |
| `tests/unit/test_podman_stack_config.py` | Dynamische Hostports und podinterne Retrievaladresse ohne Container prüfen. |
| `tests/podman/test_vector_api.py` | HTTP-Integration für CRUD, Upsert sowie gefilterte und ungefilterte Suche gegen pgvector. |
| `tests/podman/test_rag_e2e.py` | Ende zu Ende mit versioniertem Kleinkorpus: Chunking, echte normalisierte Ollama-Embeddings, Speicherung und Retrieval über pgvector sowie Antwortinhalt und Metriken über die RAG-API. Aktiv mit `--include-rag --include-ollama` oder `--all`; benötigt `snowflake-arctic-embed2` und `phi3:mini`. |
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

`--all` aktiviert RAG-, Reranker- und Ollama-Integrationstests einschließlich E2E. Das benötigt `snowflake-arctic-embed2` und `phi3:mini` auf Host-Ollama; RAG-Container und Host müssen denselben Modellserver erreichen. Der Reranker lädt Gewichte beim Image-Build herunter und lädt das Modell beim ersten HTTP-Aufruf in den Prozess. `--no-podman` überspringt explizit markierte Container-Tests und führt Unit-Tests weiter aus. Es deaktiviert nicht den eigenständigen Host-Ollama-Test, wenn dieser gleichzeitig durch `--include-ollama` oder `--all` aktiviert wird. `--no-podman` allein bleibt ohne externe Dienste ausführbar.

Die Standardintegration deckt PostgreSQL/pgvector und Vector-API ab. Der RAG-HTTP-Test prüft die Eingabevalidierung im Container; die RAG-Komponententests laufen mit gemockten Abhängigkeiten. Der Ende-zu-Ende-Test importiert `tests/podman/fixtures/early_rome.txt` mit echten Embeddings und stellt die Frage „Wer beherrschte in der Frühzeit Roms das westliche Mittelmeer“. Er prüft den erwarteten Quellabschnitt, Karthago als Antwortinhalt und Generierungsmetriken. Ein eigener Variantenfilter isoliert die Daten; die Chunks werden auch bei Fehlern gelöscht. Aktivierung: `--include-rag --include-ollama` oder `--all`, mit den Host-Ollama-Modellen `snowflake-arctic-embed2` und `phi3:mini`. Keyword-Anreicherung und `import3.py` sind nicht Teil dieses Tests. Nicht beantwortbare Fragen sowie vollständige Importskript-, Persistenz- und Lasttests bleiben weitere Ausbaustufen.
## Bestehende Lücken und Risiken

Die Ollama-Ermittlung wird containerfrei in `tests/unit/test_ollama_endpoint.py` geprüft (explizite Konfiguration, WSL-Routingtabelle, Gateway-Fallback, Cache und erneuter Versuch nach Fehler). Der E2E-Test verwendet ohne `OLLAMA_CONTAINER_URL` dieselbe automatische Ermittlung wie der reguläre RAG-Prozess. Sie erkennt nur Gateways der sichtbaren Netzwerkumgebung; bei eigenen Bridge-Netzen kann eine explizite Serveradresse erforderlich sein.

- Die RAG-API konfiguriert die Vector-Suchadresse über `VECTOR_API_URL` und beide Ollama-Endpunkte über `OLLAMA_BASE_URL`. Der E2E-Test prüft vor dem Import die erforderlichen Modelle vom Host und aus dem RAG-Container. Abweichende Zugriffsadressen werden über `OLLAMA_HOST_URL` und `OLLAMA_CONTAINER_URL` gesetzt (siehe README).
- Die Vector-API validiert Metriken und Request-Schemata nicht vollständig.
- Die RAG-API setzt voraus, dass Treffer `metadata` und `chunk_id` enthalten.
- Es gibt keine einheitlichen Readiness-Endpunkte für alle Dienste.
- Modellbasierte Ergebnisse sind variabel und können durch Modellversion, Hardware oder Sampling beeinflusst werden.
- Der erste Image-Build kann durch Modell-Downloads oder externe Paketquellen zeitaufwendig sein; für reproduzierbare Läufe sollten Images und Modelle versioniert beziehungsweise zwischengespeichert werden.

## Empfohlene Ausbaureihenfolge

1. Vector-API-Integration um Schema-/Indexprüfungen, Persistenz und Requestvalidierung erweitern.
2. Den vorhandenen E2E-Test um nicht beantwortbare Fragen und den vollständigen Importskriptpfad mit Keyword-Anreicherung erweitern.
3. Neustart-, Last- und optionale GPU-Prüfungen als getrennte, länger laufende Testgruppe ergänzen.

Der vorhandene E2E-Test wurde am 15.11.2026 mit der Ollama-Hintergrund-App und automatischer Gateway-Ermittlung erfolgreich ausgeführt. Das ist kein Nachweis für die noch geplanten Betriebs-/Lastfälle oder die fachliche Qualität auf dem gesamten historischen Korpus.
