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
- `POST /vectors` speichert einen Chunk; `GET /chunks/<chunk_id>` liefert ihn zurück, `GET /chunks` zählt die gespeicherten Zeilen im Feld `chunks`.
- Erneutes Speichern desselben Schlüssels aktualisiert den Eintrag und erzeugt keine Duplikate.
- `POST /search` liefert Treffer nach Distanz sortiert, sowohl mit Embedding-Filter als auch ohne Filter über mehrere Embedding-Werte hinweg, und begrenzt die Ergebnismenge über `num_results`.
- `GET /find?query=...` durchsucht Metadaten case-insensitiv mit `ILIKE` und liefert passende Chunk-IDs.
- `DELETE /chunks` löscht einzelne Chunks mit gleichen Grenzen und prüft inklusive Bereiche über eine Dezimalgrenze hinweg. Die Pipeline-Integration prüft das offene Ende sowie die Abgrenzung nach Dokument und Set.
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

- Health- und Modellladefehler prüfen: Gültige nichtleere Rerank-Anfragen und der erste `/health`-Aufruf laden das Modell bei Bedarf. Ungültige Requests und leere Dokumentlisten lösen kein Modellladen aus. Getrennte Liveness-/Readiness-Endpunkte bleiben offen.
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
| `tests/unit/test_import3.py` | Tats?chlicher Aufruf von `import3.process_file` einschlie?lich Keyword-Gateway und Chunking; nur HTTP wird gemockt. Pr?ft Keyword-Präfix in Embedding und Metadaten, Normalisierung, Chunk-IDs, Variante und Wiederaufnahme mit `start=2`. |
| `tests/unit/test_chunking.py` | UTF-8-Dateieinlesen, Splitter-Konfiguration, Unicode-Inhalt sowie konkrete Absatzgrenzen, Reihenfolge und Overlap mit und ohne ?berlappung. |
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

Die pytest-Konfiguration deaktiviert den Cache-Provider (`-p no:cacheprovider`), sodass kein Zugriff auf `.pytest_cache` erforderlich ist. Die Chunking-Tests legen eindeutige temporäre UTF-8-Dateien direkt unter `tests/unit` an und löschen sie nach jedem Test. Die Chunking-Tests benötigen daher keine Tempverzeichnisse. Andere Tests dürfen `tmp_path` verwenden: `tests/conftest.py` setzt einen eindeutigen Basispfad außerhalb des Checkouts und weist projektinterne `--basetemp`-Pfade sowie einen projektinternen System-/Benutzer-Tempbereich zurück. Migrationstests verwenden ebenfalls externe Tempverzeichnisse. Dadurch entstehen private Tempverzeichnis-ACLs unter Windows nicht mehr im Projekt. Der Cache-Provider bleibt deaktiviert.

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

Die Standardintegration deckt PostgreSQL/pgvector und Vector-API ab. Der RAG-HTTP-Test prüft die Eingabevalidierung im Container; die RAG-Komponententests laufen mit gemockten Abhängigkeiten. Der Ende-zu-Ende-Test importiert `tests/podman/fixtures/early_rome.txt` mit echten Embeddings und stellt die Frage „Wer beherrschte in der Frühzeit Roms das westliche Mittelmeer“. Er prüft den erwarteten Quellabschnitt, Karthago als Antwortinhalt und Generierungsmetriken. Ein eigener Variantenfilter isoliert die Daten; die Chunks werden auch bei Fehlern gelöscht. Aktivierung: `--include-rag --include-ollama` oder `--all`, mit den Host-Ollama-Modellen `snowflake-arctic-embed2` und `phi3:mini`. Keyword-Anreicherung und `import3.py` sind nicht Teil dieses E2E-Tests; sie werden containerfrei ?ber den tats?chlichen Importpfad mit gemockten HTTP-Antworten gepr?ft. Nicht beantwortbare Fragen sowie vollständige Importskript-, Persistenz- und Lasttests bleiben weitere Ausbaustufen.
## Bestehende Lücken und Risiken

Die Ollama-Ermittlung wird containerfrei in `tests/unit/test_ollama_endpoint.py` geprüft (explizite Konfiguration, WSL-Routingtabelle, Gateway-Fallback, Cache und erneuter Versuch nach Fehler). Der E2E-Test verwendet ohne `OLLAMA_CONTAINER_URL` dieselbe automatische Ermittlung wie der reguläre RAG-Prozess. Sie erkennt nur Gateways der sichtbaren Netzwerkumgebung; bei eigenen Bridge-Netzen kann eine explizite Serveradresse erforderlich sein.

- Die RAG-API konfiguriert die Vector-Suchadresse über `VECTOR_API_URL` und beide Ollama-Endpunkte über `OLLAMA_BASE_URL`. Der E2E-Test prüft vor dem Import die erforderlichen Modelle vom Host und aus dem RAG-Container. Abweichende Zugriffsadressen werden über `OLLAMA_HOST_URL` und `OLLAMA_CONTAINER_URL` gesetzt (siehe README).
- Die Vector-API validiert Eingabefelder, Aliase, Metriken, Trefferzahlen und Vektoren früh; Nebenläufigkeit und Transaktionsbereinigung bleiben offen.
- Die RAG-API prüft Trefferobjekte einschließlich String-Chunktext und nichtleerer String-ID; ungültige Antworten liefern 502, leerer Kontext führt nicht zur Generierung.
- Es gibt keine einheitlichen Readiness-Endpunkte für alle Dienste.
- Modellbasierte Ergebnisse sind variabel und können durch Modellversion, Hardware oder Sampling beeinflusst werden.
- Der erste Image-Build kann durch Modell-Downloads oder externe Paketquellen zeitaufwendig sein; für reproduzierbare Läufe sollten Images und Modelle versioniert beziehungsweise zwischengespeichert werden.

## Empfohlene Ausbaureihenfolge

Die projektweite Reihenfolge und die Abschlusskriterien stehen in [Kapitel 11.2 – Technische Schulden](11-2-technische-schulden.md#1123-priorisierte-reihenfolge-für-den-abbau). TS-17 beschreibt die übergreifenden Testlücken. Tests begleiten die jeweilige Korrektur:

1. Zuerst Regressionstests für abweichende Defaults, wirkungslose Modellwahl, falschen Goldtext, ungültige Requests, leeren Kontext und Nullzeiten ergänzen (Pakete 1 und 2).
2. Atomare Writes, Poolnutzung und verzögerten DB-Start isoliert mit Podman prüfen; danach Migration, Variantenisolation und Wiederholungsimporte absichern (Pakete 3 bis 5).
3. Schnittstellen- und Adapterverträge sowie den tatsächlichen Importpfad inklusive Keywords und Chunkgrenzen prüfen; E2E um nicht beantwortbare Fragen ergänzen (Pakete 6 und 7).
4. Modellinitialisierung und Health-Zustände prüfen; Schema-/Indexnachweise, Persistenz, Neustart- und Lastfälle nach Änderung und Betriebsbedarf ergänzen. Optionale GPU-Prüfungen bleiben eine getrennte Testgruppe (Pakete 8 und 9).

Historische Ergebnisse und Grenzen einzelner Analyseläufe stehen im [Changelog](../changelog.md). Aktuelle Befunde und offene Nachweislücken werden weiterhin im jeweiligen Fachkapitel beschrieben.

### Integration des realen Importpfads

Der Pipeline-Integrationstest erzeugt zuerst ein Chunk-Artefakt und fuehrt die Anreicherung separat mit echtem Ollama aus. Er prueft die Provider-Metriken und das leere Zielset vor dem anschliessenden Import aus dem Anreicherungsartefakt. Unit-Tests vergleichen Modell- und Promptvarianten auf denselben Chunks und pruefen den Fehlerfall ohne fertiges Artefakt.


Der Set-ID-Test in tests/podman/test_import_pipeline_integration.py verwendet die drei Pipeline-Beispiele direkt. Er prueft die gespeicherte Set-ID und den Chunktext per Einzelabruf, die Ruecksuche desselben Vektors mit Set-Filter und die leeren frueheren Set-IDs im isolierten Testvolume. Aktivierung mit --include-ollama.


Der Kompatibilitaetstest in tests/podman/test_import_pipeline_integration.py fuehrt Import3 und die Pipeline mit snowflake-arctic-embed-v2.json am selben Testtext aus. Er vergleicht die Keyword-Praefixe exakt und die gespeicherten 1024-dimensionalen Vektoren komponentenweise mit absoluter Toleranz 1e-6. Beide Importpfade verwenden getrennte Test-Sets im isolierten Stack.



`tests/unit/test_import_pipeline.py` prueft die CLI-Einstiege fuer Chunking und Import mit gemockten Diensten. Faelle umfassen feste Chunkgrenzen und Overlap bei langen ungetrennten Passagen, unveraenderten Text ohne Keywords, denselben angereicherten Text fuer Embedding und Speicherung, Wiederverwendung von Artefakten und Abbruch bei fehlerhaften Providern oder Writes.

`tests/podman/test_import_pipeline_integration.py` prueft denselben Pipeline-Einstieg mit echten Ollama-Keywords, normalisierten Embeddings und Ruecksuche ueber die Vector-API im isolierten Teststack. Der Test verwendet ein eigenes Embedding-Set und entfernt die Testchunks im finally-Block. Aktivierung mit `--include-ollama`; benoetigte Modelle sind `gemma3:4b` und `snowflake-arctic-embed2`.

Unit-Tests prüfen die ausgegebene Startnummer und einen neuen Aufruf damit nach Fehlern bei Embedding, Einzelwrite und Bereinigung. Die Podman-Standardintegration prüft den sichtbaren Teilstand nach einem Abbruch, einen Neustart ab einer frei gewählten Chunknummer und die anschließende Bereinigung. Fremde Sets und Dokumente dienen als Kontrollfälle.

`tests/podman/test_import3_integration.py` ruft `import3.process_file` mit realem Chunking, Keyword-Gateway (`gemma3:4b`), Embedding (`snowflake-arctic-embed2`) und Vector-API im isolierten Podman-Teststack auf. Nur Endpunkte und die eindeutige Importvariante werden konfiguriert. Der Test kontrolliert Chunkanzahl, nicht leeres Keyword-Präfix, unver?nderten Quelltext und Retrieval des gespeicherten Vektors durch erneutes Embedding der angereicherten Metadaten. Modellantworten werden nicht wortgenau verglichen. Testchunks werden im finally-Block entfernt. Aktivierung: `--include-ollama` oder `--all`; Host-Adresse ?ber `OLLAMA_HOST_URL`. Der RAG-Container ist nicht erforderlich. Der CLI-Argumentparser ist nicht Teil dieser Pr?fung.

## Set-Kennung und Bestandsmigration (TS-01)

Unit-Tests sichern gemeinsame Import-/Retrievaldefaults, API-Aliase und Konflikte vor SQL-/Modellzugriff ab. `tests/podman/test_embedding_migration.py` verwendet eigene Testdatenbanken und prueft unveraenderte Zeilen/Vektoren, Unique Constraint, Wiederholbarkeit und Wiederherstellung des Backups. Vector-Integration mischt alte und neue Feldnamen; echte Modelle bleiben den optionalen Ollama-/RAG-Tests vorbehalten.

Die Migrationsintegration prueft auch `002_chunktext.sql`: Erhalt von Chunktext und Vektoren, Wiederholbarkeit und Wiederherstellung des vorherigen Schemas aus dem Backup. API-Tests erwarten ausschliesslich `chunktext`; der alte Antwortname `metadata` ist entfernt.

## Reranker-Modellwahl (TS-02)

Unit-Tests pruefen Request-Modell und Default, Wiederverwendung und Wechsel, parallele Anfragen, unveraenderten Default nach expliziter Auswahl, Ladefehler ohne Fallback, Wiederholung und Validierung vor Modellarbeit. Der isolierte Podman-Test `test_reranker.py --include-reranker` verwendet MiniLM-L6 und TinyBERT-L2 nacheinander im selben Container und wechselt zum Default zurueck. Alle Antworten weisen das verwendete Modell aus. Der erste Download des Zusatzmodells benoetigt Netzwerkzugriff.

## Fehlervertrag TS-03

Tests in tests/unit/test_http_errors.py prüfen frühe Validierung vor Modell-/Poolzugriff, RFC-9457-Felder und Medientyp, sichere interne Fehler, Request-Korrelation sowie HTTP-Status und Allow-Header. Vector-Erfolgstests verwenden dimensionsgültige Eingaben. Podman-Fehlerprüfungen verwenden type statt des bisherigen error-Felds. API-Builds verwenden scripts/build_image.py mit temporären Kontexten aus explizit aufgelisteten Dateien und rag_common. Vier Unit-Tests in tests/unit/test_build_image.py sichern Dateiauswahl und Bereinigung auch bei Buildfehlern ab. Der Podman-Test tests/podman/test_http_errors.py prüft den tatsächlichen RFC-9457-Vertrag aller drei APIs einschließlich Status, Medientyp, Typ-URI, Request-ID und Allow-Header.

Historical change and verification records: [Changelog](../changelog.md).

## Tempverzeichnisse und CLI-Vertragstests

Die gemeinsame Konfiguration greift auch bei Aufrufen aus `tests`, `tests/unit` und `tests/podman`. Der Cache-Provider bleibt standardmäßig deaktiviert; bei expliziter Aktivierung wird sein Cache vor Initialisierung nach `<System-/Benutzer-Temp>/rag-pytest-cache` umgeleitet. Fixture-Tempbasispfade sind pro Lauf eindeutig und außerhalb des Projekts. Projektinterne `--basetemp`-Pfade sowie projektinterne System-/Benutzer-Tempbereiche werden zurückgewiesen; `PYTEST_DEBUG_TEMPROOT` kann Fixtures nicht ins Projekt umleiten. Dies setzt das Laden der gemeinsamen Konfiguration voraus; `--noconftest`, eine ausschließende `--confcutdir`-Grenze oder fremde Plugins können die Schutzmaßnahmen umgehen.

`test_temporary_paths.py` prüft diese Regeln einschließlich echter Subprozessaufrufe aus Unterverzeichnissen. `test_interact.py` prüft deutsche Argumentfehler, Problemantworten, HTTP-Fallbacks, Zeitlimits, Exitcodes, Exportabbrüche und fehlenden Kontext ohne Modellarbeit. `test_rag_components.py` sichert Retrievalvertragsverletzungen einschließlich ungültigem JSON, technische Ausfälle und robuste Metriken ab. Ein echter Modelltest zur fachlichen Nichtbeantwortbarkeit bei nichtleerem Kontext bleibt ein gesonderter Qualitätsnachweis. Historische Ergebnisse stehen ausschließlich im [Changelog](../changelog.md).

Pytest verwendet `--import-mode=importlib`, damit gleichnamige Unit- und Integrationstestmodule im gemeinsamen Lauf getrennt geladen werden. Die Testverzeichnisse sind fuer bestehende Helper-Imports im Python-Suchpfad eingetragen (`tests/pytest.ini`).

TS-07 prueft in einem zusaetzlichen isolierten Pod den API-Start vor PostgreSQL, Liveness ohne Datenbank, 503-Problemantworten der Readiness sowie selbststaendige Erholung nach Datenbankstart und nach Ausfall/Wiederanlauf ohne API-Neustart. Die Datenbank verwendet ausschliesslich tmpfs im eigenen Testcontainer; regulaere Volumes werden nicht verwendet. Der zusaetzliche Pod wird auch bei Fehlern entfernt.

TS-09: Unit-Vertragstests sichern einen einzigen CLI-Aufruf an die RAG-API, Modell- und Rerankingparameter, getrennte urspruengliche/ausgewaehlte Treffer und Export. Providervertraege pruefen Vektoren, Generierungsantworten und eindeutige Reranking-Indizes sowie begrenzte Retries und abgelaufenes Budget. Isolierte Ende-zu-Ende-Tests generieren mit echten Modellen sowohl ohne als auch mit Reranking.

Laufzeit-Vertragstests mit kontrollierter monotoner Uhr sichern Embedding-, Retrieval- und Pipelinezeit bei normalem Ablauf, Reranking und no_context vor/nach Reranking. CLI-Tests pruefen Gruppierung und Sekundenformat. Echte RAG-Integration prueft nichtnegative Zeiten und dass die Pipelinezeit mindestens die Summe der gemessenen Teilzeiten umfasst; der Alias generation_duration/total_duration bleibt kompatibel.

Evaluations-Vertragstests pruefen direkt verkettbare next_request-Antworten, erhaltene Identitaet/Distanzen/Scores, unabhaengige Dienstaufrufe, gespeicherte Vektoren, leere Eingaben und fruehe Eingabe-/Promptvalidierung. Eine isolierte Podman-Integration speichert einen eigenen Testchunk, durchlaeuft Retrieve/Rerank/Generate mit echten Modellen und entfernt den Chunk danach.

## IDE-aufloesbare Testimporte und Patchziele

Tests verwenden statische Paketimporte fuer normale Projektmodule. Reexportierte Funktionen und Providerzugriffe koennen mit vollqualifizierten pytest-Patchzielen ersetzt werden, etwa `monkeypatch.setattr("requests.post", fake_post)` oder `monkeypatch.setattr("rag.app.resolve_ollama_base_url", resolver)`. Dynamisches Laden bleibt fuer bewusst isolierte Module/Fixtures mit Stubs erhalten; deren Modulnamensraum wird gezielt mit `monkeypatch.setitem(vars(module), "db_pool", pool)` ersetzt. Dabei nur bekannte, vom Test benoetigte Schluessel setzen; anders als setattr prueft setitem nicht auf ein bereits vorhandenes Attribut. Alle Aenderungen werden durch monkeypatch zurueckgesetzt. Referenzinspektionen bleiben aktiv; keine pauschalen Suppressionen fuer Testdateien.
