---
purpose: "Änderungshistorie des Römer-RAG-Projekts; Anleitungen stehen in README.md."
order: "Neueste Änderungen zuerst (umgekehrt chronologisch)."
agent_instructions:
  - "Neue Datumsgruppen direkt unter der Überschrift Changelog einfügen, neuestes Datum zuerst."
  - "Innerhalb desselben Tages neue Einträge vor älteren Einträgen einfügen."
  - "Datum im Format YYYY-MM-DD angeben; unbekannte Daten nicht erfinden."
  - "Änderungen, Prüfungen und Ausrollstände hier protokollieren; dauerhafte Anleitungen in README.md pflegen."
  - "Historische Prüfergebnisse als damaligen Stand erhalten, nicht als neuen Testlauf ausgeben."
---

# Changelog

Aus README und docs übernommene Änderungshistorie. Gleichdatierte Einträge folgen der umgekehrten Reihenfolge der dortigen Nachträge. Nicht datierbare Einträge stehen am Ende. Anleitungen: [README](README.md). Fachkonzepte: [Testkonzept](docs/8-1-testkonzept.md) und [Error-Handling](docs/8-3-error-handling.md).

## 2026-11-22
### TS-09: RAG-Image ausgerollt und CLI am laufenden System geprueft

`python scripts/build_image.py rag-api --tag localhost/rag-api:ts09-20261122` erfolgreich. Image-ID `5b8f07e93e665b01d2a2639d94e987e7f6bf89ac4124bed44740ee5b20079d4b`, ebenfalls als `localhost/rag-api:local` markiert. Laufenden Container `rag-api` mit bisheriger Konfiguration (Port 5600:5600, eigenstaendiges Netzwerk, keine zusaetzlichen Umgebungsvariablen) ersetzt. Vorheriger Container bleibt gestoppt als `rag-api-before-ts09` fuer einen Rueckweg erhalten. Datenbank, Vector-API, Reranker und Volumes unveraendert.

Quellhash von rag/app.py im Container entspricht dem Workspace: `90ae159e67d8e145cec9d0cd418bbf8c6a96d1d80fcdc2c88202a1552364ae25`. Ollama aus dem Container unter `http://172.24.64.1:11434` aufgeloest; Reranker-Health ueber host.containers.internal:5000 erfolgreich (HTTP 200).

Live-Pruefung: `python interact.py --query "Wer beherrschte das westliche Mittelmeer?" --num_results 3 --top_k 0` und derselbe Aufruf mit `--top_k 1`: beide Exitcode 0, generierte Antwort und Metriken, je drei urspruengliche Exportpassagen. Ohne Reranking drei ausgewaehlte Chunks; mit Reranking genau ein ausgewaehlter Chunk (`pg3060-552`), Modell `cross-encoder/ms-marco-MiniLM-L6-v2`, Rerankingdauer 0,01765 s. Beide `/process`-Aufrufe HTTP 200; Rerankerlog bestaetigt POST /rerank HTTP 200 mit drei Dokumenten. Bestehende search_results.json nach den Pruefungen bytegetreu wiederhergestellt. Keine Datenbank-Schreibpruefungen auf regulaeren Daten.

Vorheriger vollstaendiger Testnachweis (204 bestanden) bleibt gueltig; bei diesem reinen Ausrollen keine Codeaenderungen und keine erneute Gesamtsuite. CLI und Reranking nutzen jetzt die neue Logik im laufenden System.

### TS-09: RAG-Orchestrierung zentralisiert und CLI umgestellt

`interact.py` nutzt ausschliesslich `POST /process`; lokale Argumentpruefung, Anzeige und JSON-Export bleiben erhalten. Die API unterstuetzt optionales Reranking (top_k, reranker), Antwortmodellwahl (answer_model), urspruengliche und ausgewaehlte Treffer sowie Rerankinglaufzeit. API-Default bleibt ohne Reranking; CLI sendet top_k=6 explizit. Gemeinsamer Antwortmodellstandard ist phi3:mini; bisheriger CLI-Standard gemma4:e4b kann explizit gewaehlt werden. Fortschrittsmeldungen und Export bei spaeteren Providerfehlern entfallen wie beauftragt.

Analyse verwendet Providerfunktionen und Prompt aus rag/app.py. RAG-Transport kapselt sichere Fehler, konfigurierbare Verbindungs-/Lesezeitlimits, Restbudget und Request-ID-Weitergabe. Maximal ein Retry mit Zufallswartezeit fuer Transportfehler bei Embedding, Retrieval und Reranking; Generierung und Writes nie automatisch wiederholen. Kein harter Abbruch blockierender Socket-Aufrufe; Budgetpruefung vor/nach Aufrufen. Import3 hat jetzt konfigurierte Verbindungs-/Lesezeitlimits. TS-09 im Register abgeschlossen; gesonderte Importabschluss-, Provider- und historische Variantenaufgaben bleiben ihren Registereintraegen zugeordnet.

Pruefung auf finalem Stand: `python -m pytest -c tests/pytest.ini tests --all`: **204 passed in 250.73s (0:04:10)**, Exitcode 0, keine ausgelassenen Tests. Enthalten: 191 Unit-Tests und 13 isolierte Integrationstests einschliesslich echter RAG-Verarbeitung mit und ohne Reranking sowie verz?gertem DB-Start. Unit-Suite separat: **191 passed in 7.76s**. Vertragstests pruefen CLI-Delegation, Modellwahl, Ergebnisidentitaet, leeres Reranking, ungueltige Providerantworten und Retry-/Budgetgrenzen. Der vorherige Gesamtlauf (192 passed, 2 failed) verwendete noch alte Importtest-Erwartungen ohne die ergaenzten Timeouts; diese Erwartungen korrigiert und finalen Gesamtlauf erfolgreich wiederholt. Testressourcen automatisch bereinigt, regulaere Volumes unveraendert.

README, Baustein-/Laufzeitsicht, Architekturentscheidung, Fehler- und Testkonzept aktualisiert. Keine regulaeren Container im Rahmen dieses Umbaus ersetzt; das RAG-Image muss fuer die neue CLI vor Verwendung neu gebaut und der RAG-Container neu erstellt werden.

### TS-07: Initialisierung, Readiness und Datenbankerholung

Vector-API um `/health/live` (Prozesspruefung ohne Datenbankzugriff) und `/health/ready` (Schema-Pruefung; 503 Problem Details bei Nichtbereitschaft) ergaenzt. Poolinitialisierung bleibt bedarfsgesteuert und wiederholbar; parallele Anfragen warten nicht auf den Initialisierungslock. Verbindungsaufbau, Statements und Lock-Wartezeit sind jeweils auf drei Sekunden begrenzt. Initialisierungswarnungen enthalten keine rohen DB-Fehlertexte. Kein gemeinsames Request-Gesamtbudget und keine automatischen Schreib-Retries.

Pruefung: `python -m pytest -c tests/pytest.ini tests/unit -q`: **174 passed in 7.92s**. `python -m pytest -c tests/pytest.ini tests/podman/test_vector_api.py -q`: **4 passed in 98.60s**. Neuer isolierter Test startet API vor PostgreSQL, prueft Liveness und 503-Readiness, startet die Datenbank und prueft selbststaendige Bereitschaft; danach Datenbank-Stopp und Wiederanlauf mit erneuter Erholung. API-ID unveraendert, RestartCount 0. Eigener Test-Pod mit tmpfs-Datenbank automatisch entfernt; keine regulaeren Volumes angefasst. Erster Testversuch scheiterte an Portermittlung vor Containerstart (3 passed, 1 failed); Reihenfolge korrigiert und obigen Lauf erfolgreich wiederholt.

TS-07 abgeschlossen; README, Bausteinsicht, Fehlerkonzept, Testkonzept und Schuldenregister aktualisiert. Optionale RAG-/Reranker-/Ollama-Tests und gemeinsamer Gesamtlauf nicht erneut ausgefuehrt, da nur Vector-Lebenszyklus betroffen. Kein Ausrollen der TS-07-Aenderung in regulaere Container im Rahmen dieser Aufgabe.

### Gemeinsamer vollstaendiger Testlauf erfolgreich

`python -m pytest -c tests/pytest.ini tests --all`: **182 passed in 229.61s (0:03:49)**, Exitcode 0; keine Fehler oder uebersprungenen Tests. Der gemeinsame Lauf bestaetigt die korrigierte pytest-Konfiguration mit importlib und Helper-Suchpfaden sowie das Zusammenspiel der 171 Unit-Tests und elf Integrationstests in einer Sitzung. Alle optionalen Gruppen (RAG, Reranker, Ollama einschliesslich Ingestion und Ende-zu-Ende-Antwortgenerierung) sowie TS-06 enthalten. Ausfuehrung mit genehmigtem Podman-Zugriff ausserhalb der Sandbox; isolierte Testressourcen automatisch bereinigt. Die zuvor noch ausstehende gemeinsame Ausfuehrungspruefung ist damit abgeschlossen. Keine weiteren Code- oder Containeraenderungen erforderlich.

### Optionale Integration und TS-06 im laufenden System

Alle optionalen Tests ausgefuehrt: `python -m pytest -c tests/pytest.ini tests/podman --all -q`: **11 passed** in 224,12 s, ohne uebersprungene Tests. Enthalten sind RAG, echte Ingestion/Keywords, Ollama-Embeddings, Ende-zu-Ende-Antwortgenerierung, Reranker und TS-06. Isolierte Testressourcen anschliessend automatisch entfernt.

Der zunaechst versuchte gemeinsame Aufruf `tests --all` scheiterte beim Einsammeln an gleichnamigen Testmodulen. `tests/pytest.ini` verwendet jetzt importlib und explizite Suchpfade fuer vorhandene Helper-Imports. Anschliessend alle **182 Tests erfolgreich eingesammelt**, **171 Unit-Tests bestanden** in 7,50 s. Vollstaendiger gemeinsamer Ausfuehrungslauf nach der Konfigurationskorrektur nicht wiederholt; Unit- und Integrationstests wurden separat erfolgreich ausgefuehrt.

Laufende Vector-API enthielt zuvor weder atomare Upserts noch ThreadedConnectionPool. Neues Image `localhost/vectorapi:ts06-20261122` gebaut (ID `4d6774060f5e`), auch als `localhost/vectorapi:local` markiert und Container `vector-api` mit bisheriger Pod-/DB-Konfiguration neu erstellt. Alter Container bleibt gestoppt als `vector-api-before-ts06` erhalten. Datenbank, Volumes, RAG-API und Reranker nicht ersetzt. Quellhash von Vector/app.py im neuen Container entspricht dem Workspace (`012a94aca8ec95e22731cbf8650cd1838866bbdce927e1f7aabe10b6cbe031b0`). ThreadedConnectionPool und ON CONFLICT bestaetigt; GET /chunks innerhalb des Containers und ueber localhost:5500 erfolgreich (HTTP 200; 10378 Chunks). Keine Schreibpruefung auf regulaeren Daten vorgenommen.

### TS-06: Podman-Abnahme erfolgreich

Exitcode 125 auf fehlenden Sandbox-Zugriff auf Podmans SSH-Identitaet unter dem Benutzerprofil zurueckgefuehrt (`podman info`: Access is denied). Isolierte Tests mit genehmigter Ausfuehrung ausserhalb der Sandbox erfolgreich; keine Aenderung an Dockerfiles, Schluesseln oder Dateirechten erforderlich. README um die Diagnose ergaenzt.

Pruefung: `python -m pytest -c tests/pytest.ini tests/podman -q`: **4 passed, 6 skipped** in 79,92 s. Anschliessend `python -m pytest -c tests/pytest.ini tests/podman/test_vector_api.py -q`: **3 passed** in 64,50 s, einschliesslich neuem echtem SQL-Fehlerpfad: Rollback einer vorherigen Einfuegung, dieselbe Verbindung wiederverwendbar und im Idle-Zustand, danach erfolgreicher API-Request. Parallele Upserts auf einen neuen Schluessel und stabile IDs bestanden. Testressourcen automatisch bereinigt; regulaere Volumes unveraendert. TS-06 abgeschlossen. Optionale RAG-, Reranker- und Ollama-Gruppen nicht aktiviert, da nicht betroffen; Unit-Tests nicht erneut ausgefuehrt, da nur Integrationstest und Dokumentation geaendert.

### TS-06: atomare Upserts und Transaktionsbereinigung

Vector-API auf ThreadedConnectionPool und INSERT ON CONFLICT DO UPDATE umgestellt. Zentraler Transaktionskontext behandelt Commit, Rollback, defekte Verbindungen und Poolr?ckgabefehler. Unit-Tests erg?nzt; 171 Unit-Tests bestanden. Podman-Suite versucht: vier Setupfehler beim isolierten Image-Build (Exitcode 125), sechs optionale Tests ?bersprungen. Parallelit?tspr?fung daher noch nicht abgenommen; optionale RAG-, Reranker- und Ollama-Tests nicht aktiviert, da nicht betroffen.

### Gemeinsame GPU-Nutzung untersucht; stabile Aufteilung vorgeschlagen

Reranker-Startlog bestätigt cuda:0; Ollama-Logs bestätigen GPU-Offloading auf dieselbe RTX 4060 mit 8 GB. Hostmessung: rund 2454 MiB GPU-Belegung, pro Prozess unter Windows/WDDM keine verlässliche Speicherzuordnung verfügbar. Der frühere lange Batch und Ollamas CUDA-Initialisierungsfehler sind belegt, ihre Kausalität durch GPU-Konkurrenz jedoch nicht. Separate Torch-GPU-Abfragen beschreiben nicht den damaligen Speicherzustand des aktiven Rerankermodells.

Isolierter CPU-Prozess mit gecachten MiniLM-L6-Gewichten, vier Torch-Threads und Batchgröße 8 bewertete 100 aus vorhandenen Exportpassagen wiederholte Beispiele in 2,444 Sekunden; Modellladen 0,238 Sekunden. Der Dienst blieb unverändert auf GPU. Dies ist kein identischer A/B-Vergleich zum früheren 100-Treffer-Lauf. Die Messwerte wurden erfolgreich ausgegeben; die äußere Diagnoseausgabe endete danach beim Ausgeben von Unicode-Ladefortschritt mit einem Windows-Encodingfehler.

Vorschlag, noch nicht ausgerollt: Reranker explizit auf CPU (CrossEncoder device=cpu), Batchgröße 8 und zunächst vier Torch-Threads; Ollama allein auf GPU mit OLLAMA_NUM_PARALLEL=1 und OLLAMA_MAX_LOADED_MODELS=1. Letzteres kann häufigere Modellwechsel zwischen Embedding und Generierung verursachen. Kontext zunächst explizit 4096, bei größeren Retrievalkontexten Tokenbudget prüfen statt still kürzen. Zusätzlich begrenztes Warten auf MODEL_LOCK und getrennte Healthzustände wie zuvor vorgeschlagen. Neue Reranker-Optionen benötigen explizite Codeverdrahtung, keine bloß gesetzten ungenutzten Umgebungsvariablen. Quellen: [Ollama-Konfiguration](https://github.com/ollama/ollama/blob/main/envconfig/config.go), [CrossEncoder](https://sbert.net/docs/package_reference/cross_encoder/model.html). Keine produktive Konfiguration verändert.

### Ollama-Embeddingfehler eingegrenzt und CLI-Meldung ergänzt

Ollama-Log vom 22.11.2026, 10:34:32: Embedding-Runner nach CUDA-Fehler „shared object initialization failed“ mit Status 0xc0000409 beendet; /api/embeddings antwortete mit HTTP 500. Erneute Diagnoseanfrage erhielt HTTP 200 und ein Embedding, ohne Dienstneustart. Ein Zusammenhang mit der früheren langen Reranker-Inferenz oder GPU-Speicherkonkurrenz ist damit nicht bewiesen.

interact.py zeigt nun neben RFC-9457-Problemfeldern auch Ollamas textuelles JSON-error-Feld, falls keine title/detail-Meldung vorliegt. Keine rohen HTML- oder nichttextuellen Fehlerbodys. 36 CLI-Unit-Tests bestanden; kein erneuter Podman-Lauf erforderlich, da ausschließlich lokale CLI-Fehlerdarstellung geändert wurde. Keine GPU-/Modellkonfiguration verändert.


### Architektur- und Verhaltensbeschreibungen abgeglichen

README und docs mit dem aktuellen API-/CLI-Code zu TS-03 und TS-08 abgeglichen: Validierung, leerer Kontext, robuste Metriken, Poolinitialisierung und Fehlerstatus korrigiert. Das Sequenzdiagramm enthält den no_context-Pfad. Implementierte Verträge sind von offenen Budgets, Retries, Adapterklassifikation und Readiness abgegrenzt. Keine Tests erneut ausgeführt (nur Dokumentation); Format- und lokale Linkprüfung erfolgreich.


### Dokumentationsverweise bereinigt

Lokale Dateilinks und Abschnittsanker in README, docs und Changelog geprueft; Verweise auf das ehemalige kombinierte Kapitel 11 und den verschobenen TS-08-Ausrollnachweis korrigiert. Verweise auf historische Pruefergebnisse zeigen auf das Changelog. Datumsgruppen stehen absteigend; explizit datierte Detailnachweise wurden aus dem undatierten Bereich einsortiert. Beschaedigten Umlaut in der README korrigiert. Keine Code-Tests erforderlich (nur Dokumentation).


### Deutsche CLI-Validierung

Validierungsfehler in `interact.py` werden auf Deutsch ausgegeben: fehlende Pflichtparameter und Werte, unbekannte Optionen, ungültige Ganzzahlen und Wertebereiche. Die Metrikmeldung nennt den Eingabewert und die erlaubten Werte `cosine` und `euclidean`; `L2` wird nicht akzeptiert. Parameterabkürzungen wurden deaktiviert. Fehlerhafte Aufrufe enden vor Dienstzugriffen mit Exitcode 2.

### Gemeinsames RAG-Modul ausgerollt

Die regulären API-Container wurden mit neu gebauten Images einschließlich `rag_common/rag_results.py` aktualisiert. Modulimport, API-Verträge, leerer Kontext, Reranker-Inferenz und RAG-Generierung wurden erfolgreich geprüft. Datenbestand: weiterhin 10.378 Zeilen. Ausführliche historische Nachweise folgen in diesem Changelog.

### CLI-Fehlerbehandlung und TS-08 vereinheitlicht

CLI und RAG-API teilen Retrievalvalidierung und Metrikaufbereitung aus `rag_common/rag_results.py`. Die CLI zeigt verständliche Problem-Details-Meldungen, verwendet Fehler-Exitcodes und HTTP-Zeitlimits und bricht bei Exportfehlern ab. Leerer Kontext beendet den Lauf ohne Reranking oder Generierung; ungültige Metriken verhindern die vorhandene Antwort nicht mehr.

### TS-08 implementiert und ausgerollt

Retrievalantworten werden validiert; verletzte Antwortverträge liefern HTTP 502 Problem Details. Leerer Kontext liefert `no_context` ohne Generierung und mit `metrics: null`. Ungültige oder fehlende Einzelmetriken werden null; bei fehlender oder nullwertiger Dauer wird keine Antwortgeschwindigkeit berechnet.

TS-08 wurde auf die regulären API-Container ausgerollt. API-Verträge, leeres Retrieval, Reranker-Inferenz und vollständige RAG-Generierung wurden erfolgreich geprüft. Datenbestand unverändert: 10.378 Zeilen. Nachweise und Rückwegcontainer stehen in Kapitel 8.3.

### pytest-Cache- und Tempverzeichnisse abgesichert

Die gemeinsame pytest-Konfiguration schützt auch Aufrufe aus `tests`, `tests/unit` und `tests/podman`. Ein ausdrücklich aktivierter Cache-Provider wird selbst bei überschriebenen Optionen in den externen Tempbereich umgeleitet. Projektinterne Tempbasispfade werden zurückgewiesen; eingeschränkt zugängliche pytest-Artefakte wurden entfernt.

Podman-Integration unter der geänderten pytest-Konfiguration: 6 Tests bestanden, 3 optionale Ollama-Tests übersprungen. Die anschließende Projektprüfung fand keine Cache-/Tempverzeichnisse oder Verzeichnisse mit abgeschalteter ACL-Vererbung; Prüfumfang im Testkonzept.

### Historische Nachweise aus docs

#### Quelle: `docs/11-2-technische-schulden.md`

Ausrollnachweis gemeinsames RAG-Modul (22.11.2026, TS-08/TS-09): Alle drei regulären API-Images einschließlich rag_common/rag_results.py neu gebaut und laufende API-Container aktualisiert. Modulimport, aktuelle Image-IDs und Konfigurationserhalt geprüft. RFC-9457-Verträge, leeres Retrieval (no_context), Reranker-Inferenz und vollständige RAG-Generierung bestanden. Datenbank/Volume erhalten, weiterhin 10.378 Datensätze. Vorgängercontainer bleiben gestoppt mit Suffix -before-shared-module-20261122 als Rückweg erhalten. Ausführlicher Nachweis in Kapitel 8.3.

#### Quelle: `docs/11-2-technische-schulden.md`

CLI-Fortschreibung (22.11.2026, TS-08/TS-09/TS-12): interact.py verwendet dieselbe Retrievalvalidierung und Metrikaufbereitung wie die RAG-API (rag_common/rag_results.py). Verständliche Problemantworten, Fehler-Exitcodes und getrennte HTTP-Zeitlimits sind im CLI umgesetzt; leere Kontexte lösen keine Generierung aus. 146 Unit-Tests bestanden. TS-09/TS-12 bleiben für die übrige Verarbeitung, Konfiguration und Provideradapter offen. Details und Grenzen im Error-Handling-Konzept und README.

#### Quelle: `docs/11-2-technische-schulden.md`

- **Ausrollen und Betriebsprüfung (22.11.2026):** Alle drei regulären API-Images neu gebaut und die laufenden API-Container mit ihren bisherigen Startparametern ersetzt. Aktuelle Image-IDs sowie Erhalt von Ports, Pod-Zuordnung, Startkonfiguration, Umgebungsvariablen (außer HOSTNAME), GPU-Geräten und Mounts verifiziert. RFC-9457-Antworten aller APIs, Reranker-Health/Inferenz und vollständige RAG-Generierung mit zwei Quellchunks erfolgreich geprüft. Eine RAG-Anfrage mit zufälliger unbenutzter Set-ID lieferte HTTP 200 mit `status: no_context`, leeren Chunks und `metrics: null`, ohne Bestandsdaten zu verändern. Datenbankcontainer und Volume `pgvector-data` blieben erhalten; SQL- und API-Zählung ergaben weiterhin 10.378 Zeilen. Vorgängercontainer bleiben gestoppt mit Suffix `-before-ts08-20261122` als Rückweg erhalten. Details: [TS-08-Ausrollnachweis](#ts-08-implementiert-und-ausgerollt).

#### Quelle: `docs/8-1-testkonzept.md`

Deutsche CLI-Validierung (22.11.2026): 33 CLI-Tests bestanden, einschließlich zehn zusätzlicher Fälle für fehlende query, fehlende Werte aller Textoptionen, ungültige Metrik/Ganzzahlen und unbekannte Argumente. Die bereits vorhandenen Tests prüfen Wertebereiche und leere Texte für die übrigen Parameter. Alle Fehler werden vor HTTP-Zugriff mit Exitcode 2 ausgegeben. Podman-Tests nicht erneut ausgeführt, da nur lokale Argumentvalidierung geändert wurde.

#### Quelle: `docs/8-1-testkonzept.md`

CLI-Validierung (22.11.2026): 23 Tests in tests/unit/test_interact.py bestanden, einschließlich sechs Regressionstests für konkrete Parameterfehlermeldungen vor HTTP-Zugriff. Der direkte Aufruf mit --metric L2 nennt L2 sowie cosine/euclidean und endet mit Exitcode 2. Podman-Integration nicht wiederholt, da ausschließlich CLI-Argumentvalidierung und deren Tests geändert wurden.

#### Quelle: `docs/8-1-testkonzept.md`

##### Ausrollen des gemeinsamen RAG-Moduls (22.11.2026)

#### Quelle: `docs/8-1-testkonzept.md`

CLI-Integrationsnachweis (22.11.2026): Isolierte Podman-Regression mit --include-rag --include-reranker: 6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert (137 Sekunden), da keine vollständige Ingestion oder Modellqualitätsprüfung erforderlich war. Zusätzlich bestand der direkte Aufruf von interact.py mit echtem Ollama-Embedding und einer unbenutzten Set-ID: kontrollierte no_context-Antwort, Exitcode 0, keine Generierung und kein Export. Die regulären API-Container wurden für die gemeinsame Codeextraktion nicht neu ausgerollt; geprüft wurden neu gebaute isolierte API-Images.

#### Quelle: `docs/8-1-testkonzept.md`

CLI-Prüfnachweis (22.11.2026): 146 Unit-Tests bestanden, darunter 17 neue Prüfungen in tests/unit/test_interact.py zu verständlichen Problemantworten, HTTP-Fallback, Netzwerkfehlern, Timeouts, Exitcodes, Exportabbruch, leerem Kontext ohne Modellarbeit und ungültigen Metriken. Retrievalvalidierung und Metrikaufbereitung sind zwischen CLI und API geteilt; scripts/build_image.py nimmt das neue gemeinsame Modul explizit in die Kontexte auf.

#### Quelle: `docs/8-1-testkonzept.md`

##### TS-08: Ausrollen und Betriebsprüfung (22.11.2026)

#### Quelle: `docs/8-1-testkonzept.md`

TS-08-Prüfnachweis (22.11.2026): Isolierte Podman-Regression mit python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker --tb=short erfolgreich: 6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert (128,99 Sekunden). Die TS-08-Sonderfälle sind durch deterministische Unit-Tests abgesichert; ein echter Modelltest für eine fachlich nicht beantwortbare Frage wurde nicht ausgeführt. Reguläre API-Container wurden für diese Änderung nicht aktualisiert.

#### Quelle: `docs/8-1-testkonzept.md`

TS-08 (22.11.2026): 129 Unit-Tests bestanden. 18 zusätzliche Prüfungen in test_rag_components.py sichern ungültige Retrievalantworten/JSON, leeren Kontext ohne Generierung, getrennte technische Retrievalfehler und ungültige beziehungsweise fehlende Metriken ab.

#### Quelle: `docs/8-1-testkonzept.md`

##### Podman-Nachprüfung der pytest-Schutzmaßnahmen (22.11.2026)

#### Quelle: `docs/8-1-testkonzept.md`

##### Schutz bei Aufrufen aus Unterverzeichnissen (22.11.2026)

#### Quelle: `docs/8-3-error-handling.md`

##### Ausrollen des gemeinsamen RAG-Moduls (22.11.2026)

#### Quelle: `docs/8-3-error-handling.md`

CLI-Integrationsnachweis (22.11.2026): Isolierte Podman-Regression mit --include-rag --include-reranker: 6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert (137 Sekunden), da keine vollständige Ingestion oder Modellqualitätsprüfung erforderlich war. Zusätzlich bestand der direkte Aufruf von interact.py mit echtem Ollama-Embedding und einer unbenutzten Set-ID: kontrollierte no_context-Antwort, Exitcode 0, keine Generierung und kein Export. Die regulären API-Container wurden für die gemeinsame Codeextraktion nicht neu ausgerollt; geprüft wurden neu gebaute isolierte API-Images.

#### Quelle: `docs/8-3-error-handling.md`

##### CLI-Fehlerbehandlung und TS-08 (22.11.2026)

#### Quelle: `docs/8-3-error-handling.md`

##### TS-08: Ausrollen und Betriebsprüfung (22.11.2026)

#### Quelle: `docs/8-3-error-handling.md`

TS-08-Prüfnachweis (22.11.2026): Isolierte Podman-Regression mit python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker --tb=short erfolgreich: 6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert (128,99 Sekunden). Die TS-08-Sonderfälle sind durch deterministische Unit-Tests abgesichert; ein echter Modelltest für eine fachlich nicht beantwortbare Frage wurde nicht ausgeführt. Reguläre API-Container wurden für diese Änderung nicht aktualisiert.

## 2026-11-21

### Historische Nachweise aus docs

#### Quelle: `docs/9-architekturentscheidungen.md`

Nachweis am 21.11.2026: 45 Unit-Tests und 7 Podman-Integrationstests mit `--include-rag --include-ollama` bestanden, einschließlich Backup-Wiederherstellung, Migration, echtem Keyword-/Embedding-Import und RAG-E2E. Die optionale Reranker-Integration wurde nicht aktiviert; die Umstellung der CLI-Rerankingdaten auf `chunktext` ist durch einen Unit-Test abgesichert. Die Bestandsmigration erhielt alle 10.378 Zeilen mit identischen Prüfsummen über IDs, Set-Kennungen, Vektoren und Text. Backup vor der Migration: `backups/20261121-145838-030786.dump`.

##### Umsetzungsstand TS-08 (22.11.2026)

#### Quelle: `docs/11-2-technische-schulden.md`

- **Ausrollen und Betriebsprüfung (21.11.2026):** Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` neu gebaut und die laufenden Container `vector-api`, `rag-api` und `reranker` daraus neu erstellt. Anschließend wurden HTTP 400 mit `application/problem+json`, Typ-URI, übereinstimmendem HTTP-/Bodystatus und Request-ID an allen drei APIs erfolgreich geprüft. `GET /chunks` lieferte 10.378 Datensätze; `/health` bestätigte das geladene Rerankermodell `cross-encoder/ms-marco-MiniLM-L6-v2`, und eine echte `/rerank`-Anfrage bewertete zwei Dokumente. Eine vollständige `/process`-Anfrage durchlief Embedding, Retrieval und Generierung erfolgreich und lieferte eine Antwort mit zwei Quellchunks (`pg3060-552`, `pg3061-301`). Diese Betriebsprüfungen ergänzen die isolierte Testsuite; sie sind kein erneuter vollständiger E2E-/Importtest.

#### Quelle: `docs/11-2-technische-schulden.md`

- **Nachweis (21.11.2026):** 99 containerfreie Unit-Tests bestanden, einschließlich vier Prüfungen für Dateiauswahl und Bereinigung temporärer Build-Kontexte. Isolierte Podman-Integration mit `python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker --tb=short`: 6 Tests bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert. Nachgewiesen sind API-Image-Builds, Datenbankmigrationen, Vector-CRUD/Suche, RAG-Validierung, echter Reranker-Modellwechsel und RFC-9457-Vertrag aller drei APIs einschließlich Medientyp, Typ-URI, HTTP-/Bodystatus, Request-ID und Allow-Header. Das bisherige Buildhindernis ist durch explizite temporäre Kontexte in `scripts/build_image.py` behoben; gesperrte Workspace-Verzeichnisse werden nicht durchsucht. Bestehende manuell genutzte Daten und Volumes bleiben unberührt.

#### Quelle: `docs/11-2-technische-schulden.md`

- **Nachweis:** Unit-Tests pruefen explizite Auswahl, Default, Wiederverwendung, Wechsel, Ladefehler und Wiederholung. Der Podman-Test prueft zwei echte Modelle und den Wechsel zurueck ohne Containerneustart. Verifikation am 21.11.2026: 57 Unit-Tests bestanden, einschliesslich paralleler Modellwahl und Health-Verhalten; isolierter Podman-Rerankertest mit zwei echten Modellen bestanden (1 Test). Andere Integrationsgruppen wurden fuer diese Aenderung nicht ausgefuehrt, da Import, Vector-API und RAG unveraendert sind. Einmaliges Ausrollen der geaenderten App ist erforderlich; danach sind Modellwechsel reine Requestparameter.

#### Quelle: `docs/8-1-testkonzept.md`

Prüfnachweis Tempverzeichnisse (21.11.2026): tests/.pytest-tmp wurde gezielt gelöscht. 105 Unit-Tests bestanden, darunter sechs Regressionstests für externe Tempverzeichnisse, eindeutige Basispfade, Zurückweisung projektinterner Pfade und eine echte tmp_path-Fixture. Podman-Integration nicht erneut ausgeführt, da ausschließlich lokale Testpfade geändert wurden.

#### Quelle: `docs/8-1-testkonzept.md`

Prüfnachweis vom 21.11.2026: 99 Unit-Tests bestanden. Podman-Lauf mit --include-rag --include-reranker: 6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert. Die API-Builds und der RFC-9457-Vertrag sind damit integriert geprüft; für TS-03 ist keine echte Generierung oder Ingestion erforderlich.

#### Quelle: `docs/8-3-error-handling.md`

##### Ausrollen und anschließende API-Prüfungen (21.11.2026)

## 2026-11-15

### Historische Nachweise aus docs

#### Quelle: `docs/7-verteilungssicht.md`

Diese Sicht beschreibt Repository-Konfiguration und die im bisherigen Arbeitsverlauf geprüfte Windows-/WSL-Umgebung. Der E2E-Test mit Ollama-Hintergrund-App und automatischer Gateway-Ermittlung war am 15.11.2026 erfolgreich. Für die Ergänzung dieser Dokumentation wurden keine Container verändert, keine Volumes entfernt und keine erneuten GPU-, Neustart- oder Lasttests ausgeführt.

##### Umsetzungsstand TS-03 (21.11.2026)

#### Quelle: `docs/5-bausteinsicht.md`

Beschrieben sind aktuelle Repository-Implementierung und dokumentierte Podman-Konfiguration. Der E2E-Test wurde am 15.11.2026 erfolgreich mit Windows-Ollama als Hintergrund-App und automatischer Gateway-Ermittlung ausgeführt. Diese Dokumentationsbereinigung umfasst keine erneute Deployment- oder Lastprüfung. Historische Dateien und das separate Structurizr-Modell können vom aktuellen Podman-Aufbau abweichen.

#### Quelle: `docs/8-3-error-handling.md`

Quelle: `docs/8-1-testkonzept.md`

Der vorhandene E2E-Test wurde am 15.11.2026 mit der Ollama-Hintergrund-App und automatischer Gateway-Ermittlung erfolgreich ausgeführt. Das ist kein Nachweis für die noch geplanten Betriebs-/Lastfälle oder die fachliche Qualität auf dem gesamten historischen Korpus.

## Frühere Änderungen ohne Datumsangabe in der README

Die bisherige README nennt hierfür kein belastbares Änderungsdatum; die folgende Reihenfolge behauptet keine genauere zeitliche Zuordnung.

- Gemeinsame Import-/Retrievaldefaults und unabhängige Konfiguration von Embeddingmodell und Set-ID eingeführt. `embedding_set_id` ersetzt den bisherigen Namen bei kompatiblen API-Aliasen; Migrationswerkzeug mit vorab geprüftem Backup ergänzt.
- Chunkquelltext von `metadata` auf `chunktext` umbenannt; transaktionale, wiederholbare Migration ohne neue Embeddingberechnung bereitgestellt. Kein API-Alias für `metadata`.
- Rerankermodell pro Anfrage auswählbar gemacht, mit synchronisiertem Laden und Inferenz sowie Modellkennung ohne stillen Fallback.
- Frühe Requestvalidierung und RFC-9457-Fehlerantworten für die drei APIs eingeführt (TS-03).
- API-Builds auf temporäre Kontexte aus expliziten Quelldateien umgestellt, um gesperrte lokale Verzeichnisse beim Windows-Podman-Build nicht zu durchsuchen.
- NVIDIA-GPU-Konfiguration mit WSL-Treiberbibliotheken auf einer GeForce RTX 4060 mit CUDA-Berechnung geprüft.

## Undatierte Nachweise aus docs

#### Quelle: `docs/8-3-error-handling.md`

Frühe Requestvalidierung und zentrale RFC-9457-Fehlerantworten der drei APIs sind in rag_common/http_errors.py umgesetzt. Eingangsregeln und Build-Umstellung beschreibt das README. 99 Unit-Tests und 6 isolierte Podman-Integrationstests mit RAG/Reranker bestehen. Drei optionale Ollama-/Import-/RAG-E2E-Tests wurden nicht aktiviert, da TS-03 keine echte Generierung oder Ingestion ändert. scripts/build_image.py erstellt temporäre Kontexte aus expliziten Quelldateien und umgeht den zuvor bestätigten Windows-Podman-Zugriffsfehler auf tests/.pytest-tmp. Der HTTP-Vertrag aller drei APIs in der isolierten Testumgebung ist durch tests/podman/test_http_errors.py nachgewiesen. Die übrigen Maßnahmen dieses Kapitels bleiben Zielzustände; insbesondere erfolgt noch keine vollständige Adapterfehlerklassifikation oder Readiness-Trennung. Details siehe TS-03 in Kapitel 11.2.

#### Quelle: `docs/8-3-error-handling.md`

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` neu gebaut. Die Container `vector-api`, `rag-api` und `reranker` laufen seit dem Update mit diesen Images. An den regulären Ports 5500, 5600 und 5000 wurden anschließend ungültige Requests erfolgreich mit HTTP 400 und RFC-9457-Problemantworten beantwortet; geprüft wurden Medientyp, Typ-URI, HTTP-/Bodystatus und Request-Korrelation.

#### Quelle: `docs/8-3-error-handling.md`

Zusätzlich bestanden folgende Betriebsprüfungen: Vector-Zählung über `GET /chunks` (10.378 Datensätze), Reranker-Health mit geladenem `cross-encoder/ms-marco-MiniLM-L6-v2`, echte Bewertung zweier Dokumente sowie eine vollständige RAG-Abfrage mit Embedding, Retrieval und Generierung. Die RAG-Antwort enthielt zwei Quellchunks (`pg3060-552`, `pg3061-301`). Diese lesenden Prüfungen im regulären Betrieb ergänzen die isolierten Integrationstests und ersetzen keinen vollständigen Import-/E2E-Testlauf.

#### Quelle: `docs/8-3-error-handling.md`

Der Datenbankcontainer wurde weder ersetzt noch neu gestartet; das Volume `pgvector-data` blieb unverändert eingebunden. Vorherige und anschließende SQL-Zählung ergaben jeweils 10.378 Zeilen. Ports, Pod-Zuordnung, Geräte einschließlich GPU, Mounts und Startkonfiguration der APIs wurden erhalten und abgeglichen; lediglich automatisch vergebene Container-Hostnamen änderten sich. Die bisherigen API-Container bleiben gestoppt mit dem Suffix `-before-ts03-20261121` als Rückweg erhalten. Den ausführlichen Prüfnachweis führt [TS-03 in Kapitel 11.2](docs/11-2-technische-schulden.md#ts-03--requestvalidierung-und-fehlerverträge--p1--abgeschlossen). Die weiteren Zielmaßnahmen dieses Konzepts bleiben davon unberührt.

#### Quelle: `docs/8-3-error-handling.md`

Retrievalvalidierung, kontrollierte Antworten ohne Kontext und robuste Metriken sind in `rag/app.py` umgesetzt. Jeder Treffer benötigt eine nichtleere String-`chunk_id` und String-`chunktext`; ungültige Antworten einschließlich ungültigem JSON liefern 502 Problem Details. Leere Texte werden nach vollständiger Vertragsprüfung aus Kontext und Quellliste entfernt. Bleibt kein Text, erfolgt HTTP 200 mit `status: no_context`, `chunks: []`, `metrics: null` und Ablehnungsantwort ohne Generierung. Retrievalausfälle lösen diesen Erfolgspfad nicht aus.

#### Quelle: `docs/8-3-error-handling.md`

Bei vorhandener Modellantwort bleiben die Metrikfelder erhalten: nicht verfügbare oder ungültige Einzelwerte sind null, gemessene Nullwerte bleiben 0. Tokenzahlen sind nichtnegative Integer ohne Booleans. `answer_rate` ist nur bei gültiger positiver Generierungsdauer und gültiger Tokenzahl definiert; nicht endliche Raten sind null. 129 Unit-Tests bestanden, einschließlich 18 zusätzlicher TS-08-Prüfungen. Die übrigen offenen Maßnahmen dieses Konzepts und die fehlende Garantie fachlicher Beantwortbarkeit bleiben bestehen.

#### Quelle: `docs/8-3-error-handling.md`

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` neu gebaut. Die laufenden API-Container wurden mit ihren zuvor ausgelesenen Startparametern ersetzt und ihre Image-IDs gegen die aktuellen regulären Tags geprüft. Ports, Pod-Zuordnung, Startkommando, Benutzer, Arbeitsverzeichnis, Restart-Policy, Umgebungsvariablen (außer automatisch vergebenem HOSTNAME), GPU-Geräte und Mounts stimmen mit den Vorgängern überein. Die vorherigen API-Container bleiben gestoppt mit dem Suffix `-before-ts08-20261122` als Rückweg erhalten.

#### Quelle: `docs/8-3-error-handling.md`

Die anschließenden lesenden Betriebsprüfungen bestanden: RFC-9457-Fehlerantworten aller drei APIs; Reranker-Health mit geladenem Modell und echte Bewertung zweier Dokumente; vollständige RAG-Abfrage mit Embedding, Retrieval und Generierung sowie zwei Quellchunks (`pg3060-552`, `pg3061-301`). Eine zusätzliche echte RAG-Anfrage mit einer zufälligen, unbenutzten Set-ID prüfte leeres Retrieval ohne Datenänderung: HTTP 200, `status: no_context`, `chunks: []`, `metrics: null` und kontrollierte Ablehnungsantwort. Das Überspringen der Generierung ist zusätzlich durch die Unit-Tests mit nicht aufgerufenem Generierungs-Mock abgesichert.

#### Quelle: `docs/8-3-error-handling.md`

Datenbankcontainer `vectordb` und Volume `pgvector-data` wurden bei diesem Ausrollen weder ersetzt noch neu gestartet oder verändert. Die SQL-Zählung und Vector-API ergaben weiterhin 10.378 Datensätze. Der reguläre Betrieb verwendet damit TS-08; frühere Hinweise zum noch ausstehenden Ausrollen beschreiben den Stand vor diesem Schritt. Ein echter Modelltest zur fachlichen Nichtbeantwortbarkeit bei nichtleerem Kontext ist weiterhin kein Bestandteil dieses Nachweises.

#### Quelle: `docs/8-3-error-handling.md`

`interact.py` verwendet gemeinsame Retrievalvalidierung und Metrikaufbereitung aus `rag_common/rag_results.py`, die auch die RAG-API nutzt. Fehlerhafte Treffer werden nicht als leerer Kontext behandelt. Bei leeren Treffern oder ausschließlich leeren Texten endet die CLI mit kontrollierter Ablehnungsantwort (`no_context`), ohne Export, Reranking oder Generierung. Wenn Reranking keine verwertbaren Dokumente liefert, entfällt ebenfalls die Generierung.

#### Quelle: `docs/8-3-error-handling.md`

HTTP-Fehler erscheinen verständlich mit Verarbeitungsschritt, tatsächlichem HTTP-Status, `title`/`detail` und vorhandener Typ-URI/Request-ID; rohe Fehlerbodys werden nicht ausgegeben. Timeout und Nichterreichbarkeit erhalten eigene Meldungen. Fehler gehen auf stderr. Exitcode 0 bedeutet Erfolg (auch ohne Kontext), 1 einen Verarbeitungs-/Exportabbruch und 2 ungültige CLI-Argumente. Exportfehler führen zum Abbruch statt zum stillen Fortsetzen. Es gibt keine automatischen Wiederholungen.

#### Quelle: `docs/8-3-error-handling.md`

Alle HTTP-Aufrufe verwenden getrennte Verbindungs-/Antwortzeitlimits: 5 Sekunden Verbindung, 300 Sekunden Embedding, 60 Sekunden Retrieval sowie 600 Sekunden Generierung und Reranking. Dies sind Requests-Verbindungs-/Lesezeitlimits, kein Gesamtbudget des gesamten Laufs. Fehlende oder ungültige Metriken werden als „nicht verfügbar“ dargestellt; Nullzeiten verursachen keine Division durch null. Der CLI ruft Ollama, Vector-API und Reranker weiterhin direkt auf; seine Modellwahl bleibt unabhängig von der RAG-API.

#### Quelle: `docs/8-3-error-handling.md`

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` einschließlich `rag_common/rag_results.py` neu gebaut und die drei laufenden API-Container mit den bisherigen Startparametern ersetzt. Aktuelle Image-IDs wurden mit den regulären Tags abgeglichen; das gemeinsame Modul wurde in jedem Container erfolgreich vom Paketpfad `/rag_common/rag_results.py` importiert. Die Apps nehmen den übergeordneten Paketpfad wie bisher beim Start in den Python-Suchpfad auf.

#### Quelle: `docs/8-3-error-handling.md`

Die anschließenden lesenden Betriebsprüfungen bestanden: RFC-9457-Fehlerantworten aller drei APIs einschließlich Medientyp, Status und Request-ID; Reranker-Health und echte Bewertung zweier Dokumente; vollständige RAG-Abfrage mit Antwort und zwei Quellchunks (`pg3060-552`, `pg3061-301`). Eine zusätzliche RAG-Abfrage mit zufälliger unbenutzter Set-ID lieferte HTTP 200 mit `status: no_context`, `chunks: []` und `metrics: null`.

#### Quelle: `docs/8-3-error-handling.md`

Datenbankcontainer `vectordb` wurde weder ersetzt noch neu gestartet; Volume `pgvector-data` blieb eingebunden. SQL- und API-Zählung bestätigten weiterhin 10.378 Datensätze. Ports, Pod-Zuordnung, Mounts, GPU-Geräte, Restart-Policy, Startkommando, Benutzer, Arbeitsverzeichnis und Umgebungsvariablen (außer automatisch vergebenem HOSTNAME) der APIs wurden gegen die Vorgänger abgeglichen und erhalten. Die vorherigen API-Container bleiben gestoppt mit Suffix `-before-shared-module-20261122` als Rückweg erhalten. Die zuvor dokumentierte noch ausstehende Ausrollung der gemeinsamen Codeextraktion ist damit erfolgt; der Nachweis mit 146 Unit-Tests und 6 isolierten Podman-Integrationstests wird durch diese Betriebsprüfung ergänzt.

#### Quelle: `docs/8-1-testkonzept.md`

Die gemeinsame Konfiguration in `tests/conftest.py` greift auch bei pytest-Aufrufen aus `tests`, `tests/unit` und `tests/podman`. Sechs Subprozess-Regressionstests prüfen die normale Konfigurationssuche ohne `-c` sowie Aufrufe mit überschriebenem `addopts`, explizit aktiviertem `cacheprovider` und projektintern angefordertem `cache_dir`. Der Cache wird vor der Initialisierung des Providers nach `<System-/Benutzer-Temp>/rag-pytest-cache` umgeleitet. Der Temp-Fixture-Basispfad bleibt pro Lauf eindeutig außerhalb des Projekts; eine projektinterne Umleitung durch `PYTEST_DEBUG_TEMPROOT` bleibt wirkungslos. Insgesamt bestanden 111 Unit-Tests.

#### Quelle: `docs/8-1-testkonzept.md`

Die Absicherung gilt, wenn die gemeinsame Testkonfiguration geladen wird. Aufrufe mit `--noconftest`, einer ausschließenden `--confcutdir`-Grenze oder fremden Test-/Plugin-Skripten können diese Regeln bewusst umgehen. Reguläre Testbefehle daher wie dokumentiert verwenden. Private Rechte externer Tempverzeichnisse sind weiterhin zulässig; im Checkout werden dafür keine Verzeichnisse erzeugt. Podman-Tests wurden nicht wiederholt, da nur lokale pytest-Konfiguration und deren Regressionstests geändert wurden.

#### Quelle: `docs/8-1-testkonzept.md`

Nach Start der zuvor ausgeschalteten vorhandenen Podman-Maschine wurde `python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker --tb=short` mit der geänderten pytest-Konfiguration erfolgreich ausgeführt: **6 bestanden, 3 übersprungen** (136,39 Sekunden). Enthalten waren Datenbankmigrationen, RFC-9457-Verträge aller APIs, RAG-Validierung, Reranker einschließlich Modellwechsel und Vector-CRUD/Suche. Die drei optionalen Host-Ollama-/Import-/RAG-E2E-Tests waren nicht aktiviert, da die Änderung nur die Testkonfiguration betrifft. Der erste Versuch vor dem Maschinenstart scheiterte am nicht erreichbaren Podman-Dienst; der Wiederholungslauf bestand vollständig für die aktivierten Gruppen.

#### Quelle: `docs/8-1-testkonzept.md`

Nach abgeschlossenem Lauf und automatischer Bereinigung der isolierten Testressourcen wurde der Projektbaum erneut geprüft: keine pytest-Cache-/Tempverzeichnisse, sonstigen erkannten Cache-/Tempverzeichnisse oder Verzeichnisse mit abgeschalteter ACL-Vererbung gefunden. Insbesondere blieben `tests/.pytest-tmp`, `tests/.pytest_cache`, `tests/unit/.pytest_cache` und `tests/podman/.pytest_cache` abwesend. Historische `k8s`-Verzeichnisse, Git-/IDE-/Agentenmetadaten und Reparse Points waren von der Prüfung ausgeschlossen. Der vorherige Nachweis mit 111 erfolgreichen Unit-Tests bleibt gültig; die Aussage zur damals nicht wiederholten Podman-Integration ist durch diese Nachprüfung ergänzt.

#### Quelle: `docs/8-1-testkonzept.md`

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` neu gebaut. Die laufenden API-Container wurden mit ihren zuvor ausgelesenen Startparametern ersetzt und ihre Image-IDs gegen die aktuellen regulären Tags geprüft. Ports, Pod-Zuordnung, Startkommando, Benutzer, Arbeitsverzeichnis, Restart-Policy, Umgebungsvariablen (außer automatisch vergebenem HOSTNAME), GPU-Geräte und Mounts stimmen mit den Vorgängern überein. Die vorherigen API-Container bleiben gestoppt mit dem Suffix `-before-ts08-20261122` als Rückweg erhalten.

#### Quelle: `docs/8-1-testkonzept.md`

Die anschließenden lesenden Betriebsprüfungen bestanden: RFC-9457-Fehlerantworten aller drei APIs; Reranker-Health mit geladenem Modell und echte Bewertung zweier Dokumente; vollständige RAG-Abfrage mit Embedding, Retrieval und Generierung sowie zwei Quellchunks (`pg3060-552`, `pg3061-301`). Eine zusätzliche echte RAG-Anfrage mit einer zufälligen, unbenutzten Set-ID prüfte leeres Retrieval ohne Datenänderung: HTTP 200, `status: no_context`, `chunks: []`, `metrics: null` und kontrollierte Ablehnungsantwort. Das Überspringen der Generierung ist zusätzlich durch die Unit-Tests mit nicht aufgerufenem Generierungs-Mock abgesichert.

#### Quelle: `docs/8-1-testkonzept.md`

Datenbankcontainer `vectordb` und Volume `pgvector-data` wurden bei diesem Ausrollen weder ersetzt noch neu gestartet oder verändert. Die SQL-Zählung und Vector-API ergaben weiterhin 10.378 Datensätze. Der reguläre Betrieb verwendet damit TS-08; frühere Hinweise zum noch ausstehenden Ausrollen beschreiben den Stand vor diesem Schritt. Ein echter Modelltest zur fachlichen Nichtbeantwortbarkeit bei nichtleerem Kontext ist weiterhin kein Bestandteil dieses Nachweises.

#### Quelle: `docs/8-1-testkonzept.md`

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` einschließlich `rag_common/rag_results.py` neu gebaut und die drei laufenden API-Container mit den bisherigen Startparametern ersetzt. Aktuelle Image-IDs wurden mit den regulären Tags abgeglichen; das gemeinsame Modul wurde in jedem Container erfolgreich vom Paketpfad `/rag_common/rag_results.py` importiert. Die Apps nehmen den übergeordneten Paketpfad wie bisher beim Start in den Python-Suchpfad auf.

#### Quelle: `docs/8-1-testkonzept.md`

Die anschließenden lesenden Betriebsprüfungen bestanden: RFC-9457-Fehlerantworten aller drei APIs einschließlich Medientyp, Status und Request-ID; Reranker-Health und echte Bewertung zweier Dokumente; vollständige RAG-Abfrage mit Antwort und zwei Quellchunks (`pg3060-552`, `pg3061-301`). Eine zusätzliche RAG-Abfrage mit zufälliger unbenutzter Set-ID lieferte HTTP 200 mit `status: no_context`, `chunks: []` und `metrics: null`.

#### Quelle: `docs/8-1-testkonzept.md`

Datenbankcontainer `vectordb` wurde weder ersetzt noch neu gestartet; Volume `pgvector-data` blieb eingebunden. SQL- und API-Zählung bestätigten weiterhin 10.378 Datensätze. Ports, Pod-Zuordnung, Mounts, GPU-Geräte, Restart-Policy, Startkommando, Benutzer, Arbeitsverzeichnis und Umgebungsvariablen (außer automatisch vergebenem HOSTNAME) der APIs wurden gegen die Vorgänger abgeglichen und erhalten. Die vorherigen API-Container bleiben gestoppt mit Suffix `-before-shared-module-20261122` als Rückweg erhalten. Die zuvor dokumentierte noch ausstehende Ausrollung der gemeinsamen Codeextraktion ist damit erfolgt; der Nachweis mit 146 Unit-Tests und 6 isolierten Podman-Integrationstests wird durch diese Betriebsprüfung ergänzt.

#### Quelle: `docs/11-2-technische-schulden.md`

- **Nachweis:** 129 containerfreie Unit-Tests und die isolierte Podman-Regression mit RAG/Reranker (6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert) bestanden. Darunter sind 18 zusätzliche TS-08-Prüfungen für Treffer-/JSON-Verträge, leeren Kontext, Retrievalausfall und robuste Metriken. Die Umsetzung folgt [8.3.3](docs/8-3-error-handling.md#833-problemtypregister-und-statuszuordnung) und [8.3.6](docs/8-3-error-handling.md#836-fachliche-ergebnisse-und-importabschluss). Der deterministische Fehlerpfadnachweis erfolgt mit gemockten Abhängigkeiten; ein echter Modelltest für eine fachlich nicht beantwortbare Frage bleibt ein gesonderter Qualitätsnachweis, da nichtleerer Kontext keine Beantwortbarkeit garantiert.

#### Quelle: `docs/11-2-technische-schulden.md`

- **Nachweis:** Unit-Vertragstest importiert mit Modell-Mocks und findet die Chunks per Standardanfrage. Podman-Test prueft unveraenderte Daten, Unique Constraint, wiederholte Migration und echte Backup-Wiederherstellung. Verifikation: 42 Unit-Tests bestanden; 6 Podman-Tests mit `--include-rag --include-ollama` bestanden, einschliesslich echtem Import mit Keywords und RAG-E2E. Reranker-Gruppe nicht aktiviert, da unabhaengig von TS-01. Architekturentscheidung: [9.1](docs/9-architekturentscheidungen.md). Bestandsmigration: 10.378 Zeilen vor/nach Migration mit identischem SHA-256 ueber geordnete Zeilenpruefsummen; Backup `backups/20261121-143748-053410.dump`. Beide API-Aliase liefern 10.373 Zeilen des Standardsets; Standard-RAG-Anfrage ohne Filter liefert 5 Quellchunks.

#### Quelle: `docs/11-2-technische-schulden.md`

- **Daten- und Konfigurationserhalt:** Der Datenbankcontainer `vectordb` blieb mit derselben Container-ID und Startzeit unverändert in Betrieb; das Volume `pgvector-data` blieb eingebunden. Die SQL-Zählung ergab vor und nach dem Update jeweils 10.378 Zeilen. API-Ports, Pod-Zuordnung, Startkommando, Benutzer, Arbeitsverzeichnis, Restart-Policy, Geräte und Mounts wurden gegen die bisherigen Container abgeglichen; insbesondere blieb die GPU-Einbindung des Rerankers erhalten. Umgebungsvariablen stimmen bis auf automatisch neu vergebene `HOSTNAME`-Werte der eigenständigen Container überein. Die bisherigen API-Container bleiben gestoppt unter den Namen `vector-api-before-ts03-20261121`, `rag-api-before-ts03-20261121` und `reranker-before-ts03-20261121` als Rückweg erhalten.

#### Quelle: `docs/11-2-technische-schulden.md`

Die Analyse umfasst Python-Code, SQL, Dockerfiles und Tests. Die 24 containerfreien Unit-Tests bestanden bei der Analyse. Ergänzende lokale Prüfungen mit gemockten HTTP-, Datenbank- und Modellabhängigkeiten bestätigten die unter TS-03, TS-08 und TS-14 beschriebenen Fehler. Podman-, Modell-, Parallelitäts- und Lasttests wurden dafür nicht ausgeführt. Aus Code abgeleitete Auswirkungen sind daher keine gemessenen Ausfälle oder Performancebefunde. Ein im Testkonzept dokumentierter früherer E2E-Lauf ersetzt diese Prüfungen nicht.
