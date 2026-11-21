# 11.2 Technische Schulden

Stand: 21.11.2026. Dieses Kapitel nach arc42 dokumentiert die im Projekt untersuchten technischen Schulden und einen vorgeschlagenen Abbauplan. TS-01, TS-02 und TS-03 sind abgeschlossen (Nachweise siehe Eintraege). Der bisherige TS-04 wird als akzeptiertes Risiko [R-01](11-1-risiken.md#r-01--manuelle-zuordnung-von-importvarianten--akzeptiertes-risiko) separat geführt. Technische Schulden gelten nur bei ausdrücklicher Markierung als Risiken. Die übrigen Einträge sind offen; ihre beschriebenen Maßnahmen sind Zielzustände und noch nicht umgesetzt.

Die [Bausteinsicht](5-bausteinsicht.md) beschreibt die betroffenen Komponenten, die [Laufzeitsicht](6-laufzeitsicht.md) deren Zusammenspiel und das [Testkonzept](8-1-testkonzept.md) die vorhandenen Prüfungen. Das [Error-Handling-Konzept in Kapitel 8.3](8-3-error-handling.md) konkretisiert die offenen Maßnahmen; seine Dokumentation ist kein Implementierungsnachweis. Verzeichnisse namens `k8s` sind ausgeschlossen. Bewertungsmaßstab ist der lokale Podman-Betrieb eines Systems zum Vergleich von RAG-Strategien, kein bereits zugesagter Produktionsbetrieb.

## 11.2.1 Bewertung und Nachweisgrenzen

Die Priorität richtet sich zuerst nach Datenintegrität und Verlässlichkeit von Experimenten, danach nach Betriebsstabilität, Änderbarkeit und Performance.

| Priorität | Bedeutung |
|---|---|
| P1 | Zuerst abbauen: verfälschte Vergleiche, inkonsistente Daten oder bestätigte Fehler im regulären Verarbeitungspfad. |
| P2 | Anschließend abbauen: strukturelle Inkonsistenzen, Betriebsrisiken und fehlende Reproduzierbarkeit. |
| P3 | Nach Stabilisierung beziehungsweise bei entsprechendem Betriebsbedarf bearbeiten. |

Die Analyse umfasst Python-Code, SQL, Dockerfiles und Tests. Die 24 containerfreien Unit-Tests bestanden bei der Analyse. Ergänzende lokale Prüfungen mit gemockten HTTP-, Datenbank- und Modellabhängigkeiten bestätigten die unter TS-03, TS-08 und TS-14 beschriebenen Fehler. Podman-, Modell-, Parallelitäts- und Lasttests wurden dafür nicht ausgeführt. Aus Code abgeleitete Auswirkungen sind daher keine gemessenen Ausfälle oder Performancebefunde. Ein im Testkonzept dokumentierter früherer E2E-Lauf ersetzt diese Prüfungen nicht.

## 11.2.2 Schuldenregister

### TS-01 – Abweichende Import- und Retrievaldefaults · P1

- **Stand 21.11.2026:** Abgeschlossen: gemeinsame Defaults in `rag/embedding_config.py` fuer Import3, CLI und RAG; Modell und Set-Kennung sind unabhaengig konfigurierbar.
- **API und Migration:** `embedding_set_id` ersetzt die bisherige Spalte und den Vector-API-Parameter. `embedding` bleibt kompatibler Alias und Antwortfeld, `filter` bleibt RAG-Alias. Konflikte ergeben HTTP 400. Migration mit vorherigem geprueftem Backup ohne neue Vektorberechnung: `scripts/migrate_embedding_set_id.py`; Betrieb und Rueckweg im README.
- **Nachweis:** Unit-Vertragstest importiert mit Modell-Mocks und findet die Chunks per Standardanfrage. Podman-Test prueft unveraenderte Daten, Unique Constraint, wiederholte Migration und echte Backup-Wiederherstellung. Verifikation: 42 Unit-Tests bestanden; 6 Podman-Tests mit `--include-rag --include-ollama` bestanden, einschliesslich echtem Import mit Keywords und RAG-E2E. Reranker-Gruppe nicht aktiviert, da unabhaengig von TS-01. Architekturentscheidung: [9.1](9-architekturentscheidungen.md). Bestandsmigration: 10.378 Zeilen vor/nach Migration mit identischem SHA-256 ueber geordnete Zeilenpruefsummen; Backup `backups/20261121-143748-053410.dump`. Beide API-Aliase liefern 10.373 Zeilen des Standardsets; Standard-RAG-Anfrage ohne Filter liefert 5 Quellchunks.

### TS-02 – Wirkungslose Reranker-Modellwahl · P1

- **Stand 21.11.2026:** Implementiert: `POST /rerank` waehlt das CrossEncoder-Modell ueber `model`; ohne Parameter gilt `RERANK_MODEL`. Die CLI reicht `--reranker` weiter und zeigt das verwendete Modell aus der Antwort an.
- **Vertrag:** Antworten enthalten `model` und `ranked_documents`. Ungueltige Modellparameter liefern HTTP 400 vor dem Laden; Ladefehler liefern HTTP 503 ohne stillen Fallback. Bei leerer Dokumentliste wird kein Modell geladen. Ein Modell bleibt aktiv; Modellwechsel und Inferenz sind gemeinsam synchronisiert. Beim Wechsel wird das neue Modell zuerst geladen, sodass bei Ladefehlern das vorherige verfuegbar bleibt.
- **Nachweis:** Unit-Tests pruefen explizite Auswahl, Default, Wiederverwendung, Wechsel, Ladefehler und Wiederholung. Der Podman-Test prueft zwei echte Modelle und den Wechsel zurueck ohne Containerneustart. Verifikation am 21.11.2026: 57 Unit-Tests bestanden, einschliesslich paralleler Modellwahl und Health-Verhalten; isolierter Podman-Rerankertest mit zwei echten Modellen bestanden (1 Test). Andere Integrationsgruppen wurden fuer diese Aenderung nicht ausgefuehrt, da Import, Vector-API und RAG unveraendert sind. Einmaliges Ausrollen der geaenderten App ist erforderlich; danach sind Modellwechsel reine Requestparameter.

### TS-03 – Requestvalidierung und Fehlerverträge · P1 · Abgeschlossen

- **Stand 21.11.2026:** Frühe gemeinsame Validierung in `rag_common/http_errors.py` für RAG-, Vector- und Reranker-API umgesetzt. Ungültige JSON-Strukturen, Text-/Dokumentfelder, Aliase, Metriken, Trefferzahlen und Vektoren werden vor Modell- und Datenbankzugriffen zurückgewiesen. Vector-Poolinitialisierung erfolgt erst nach der Validierung.
- **Vertrag:** Zentrale Handler liefern RFC-9457-Problemobjekte mit `application/problem+json`, stabiler Typ-URI, HTTP-/Bodystatus, sicherem Fehlertext, Ereignis-URI und Request-ID gemäß [8.3.1–8.3.3](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten). HTTP-Fehler behalten Status und erforderliche Header. API-Clients mit Fehlerfeldzugriffen in Tests und Build-Kontexte sind angepasst; README beschreibt den Schnittstellenbruch.
- **Nachweis (21.11.2026):** 99 containerfreie Unit-Tests bestanden, einschließlich vier Prüfungen für Dateiauswahl und Bereinigung temporärer Build-Kontexte. Isolierte Podman-Integration mit `python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker --tb=short`: 6 Tests bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert. Nachgewiesen sind API-Image-Builds, Datenbankmigrationen, Vector-CRUD/Suche, RAG-Validierung, echter Reranker-Modellwechsel und RFC-9457-Vertrag aller drei APIs einschließlich Medientyp, Typ-URI, HTTP-/Bodystatus, Request-ID und Allow-Header. Das bisherige Buildhindernis ist durch explizite temporäre Kontexte in `scripts/build_image.py` behoben; gesperrte Workspace-Verzeichnisse werden nicht durchsucht. Bestehende manuell genutzte Daten und Volumes bleiben unberührt.
- **Ausrollen und Betriebsprüfung (21.11.2026):** Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` neu gebaut und die laufenden Container `vector-api`, `rag-api` und `reranker` daraus neu erstellt. Anschließend wurden HTTP 400 mit `application/problem+json`, Typ-URI, übereinstimmendem HTTP-/Bodystatus und Request-ID an allen drei APIs erfolgreich geprüft. `GET /chunks` lieferte 10.378 Datensätze; `/health` bestätigte das geladene Rerankermodell `cross-encoder/ms-marco-MiniLM-L6-v2`, und eine echte `/rerank`-Anfrage bewertete zwei Dokumente. Eine vollständige `/process`-Anfrage durchlief Embedding, Retrieval und Generierung erfolgreich und lieferte eine Antwort mit zwei Quellchunks (`pg3060-552`, `pg3061-301`). Diese Betriebsprüfungen ergänzen die isolierte Testsuite; sie sind kein erneuter vollständiger E2E-/Importtest.
- **Daten- und Konfigurationserhalt:** Der Datenbankcontainer `vectordb` blieb mit derselben Container-ID und Startzeit unverändert in Betrieb; das Volume `pgvector-data` blieb eingebunden. Die SQL-Zählung ergab vor und nach dem Update jeweils 10.378 Zeilen. API-Ports, Pod-Zuordnung, Startkommando, Benutzer, Arbeitsverzeichnis, Restart-Policy, Geräte und Mounts wurden gegen die bisherigen Container abgeglichen; insbesondere blieb die GPU-Einbindung des Rerankers erhalten. Umgebungsvariablen stimmen bis auf automatisch neu vergebene `HOSTNAME`-Werte der eigenständigen Container überein. Die bisherigen API-Container bleiben gestoppt unter den Namen `vector-api-before-ts03-20261121`, `rag-api-before-ts03-20261121` und `reranker-before-ts03-20261121` als Rückweg erhalten.
- **Abgrenzung:** TS-03 umfasst den Eingangs- und Fehlerausgabevertrag. Weitergehende Adapterklassifikation, Retrybudgets, Transaktionsbereinigung, Importabschluss und getrennte Readiness bleiben unter TS-05 bis TS-09, TS-12 und TS-13 offen. Das Querschnittskonzept ist weiterhin nur teilweise umgesetzt.

### TS-04 – Manuelle Zuordnung von Importvarianten · Akzeptiertes Risiko

- **Befund:** `embedding_set_id` ist eine frei gewählte Kennung. Import3 und Retrieval können Modell und Set unabhängig konfigurieren; die Datenbank speichert und prüft keine vollständige Verarbeitungskonfiguration. Eine Set-ID allein belegt daher weder Chunking, Anreicherung und Prompts noch das tatsächlich verwendete Modell und die Normalisierung.
- **Entscheidung vom 21.11.2026:** Keine zusätzliche technische Speicherung oder Absicherung dieser Konfiguration. Stattdessen wird die Zuordnung manuell im [Set-ID-Verzeichnis, arc42-Abschnitt 8.2](8-2-embedding-sets.md) gepflegt. Die [Architekturentscheidung 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026) ersetzt den bisherigen Vorschlag einer persistierten Variantenkonfiguration.
- **Manuelle Behandlung:** Vor einem Import die tatsächlichen Parameter zum Set dokumentieren; bei geänderter Verarbeitung eine neue Set-ID verwenden. Evaluationen nennen die verwendete Set-ID. Unbekannte historische Angaben bleiben ausdrücklich unbekannt; der aktuelle Codezustand ist kein vollständiger Herkunftsnachweis für Bestandsvektoren. Ein erneutes Embedding ist hierfür nicht erforderlich.
- **Akzeptiertes Restrisiko:** Eine falsche Kennung oder veraltete Dokumentation kann unterschiedliche Verarbeitungen unter derselben Set-ID vermischen. Gleiche `(chunk_id, embedding_set_id)` können überschrieben werden; Vergleiche werden dadurch schwer erklärbar oder nicht wiederholbar. Das Verzeichnis unterstützt die Nachvollziehbarkeit, verhindert solche Fehler aber nicht technisch. Es besteht kein offener Implementierungsauftrag für die ursprünglich vorgeschlagene Konfigurationspersistenz. Importlaufprobleme bleiben TS-05; Modellrevisionen und Buildstände behandelt TS-15.

### TS-05 – Kollidierende Chunk-IDs und unvollständige Wiederholungsimporte · P1

- **Befund:** [Import3](../Ingest/import3.py), `process_file`, erzeugt IDs aus `basename.split('.')[0]` und laufender Nummer. `rom.band1.txt` und `rom.band2.txt` kollidieren innerhalb derselben Variante. Kürzere Wiederholungsimporte entfernen keine alten überzähligen Chunks. Chunkfehler werden protokolliert; ein zusammenfassender Fehlerstatus fehlt.
- **Auswirkung:** Quellen werden vermischt; veraltete und neue Inhalte bleiben gemeinsam abrufbar. Ein Teilimport kann als erfolgreicher Lauf erscheinen.
- **Abbau und Abschluss:** Dokumentidentität, Inhaltsversion und Importlauf trennen. Abschluss und Aktivierung eines Imports sowie Fehlerstatus und Resume-Semantik festlegen. Tests prüfen Namenskollisionen, verkürzte Neuimporte, Abbruch und Wiederaufnahme. Bestehende Daten benötigen einen expliziten Migrations- oder Neuimportpfad.
- **Konkretisierung durch Kapitel 8.3:** Importabschluss gemäß [8.3.6](8-3-error-handling.md#836-fachliche-ergebnisse-und-importabschluss) umsetzen: standardmäßiger Abbruch, optionales Fortsetzen bei einzelnen Chunkfehlern, Abbruch bei systemischen Störungen, Laufzusammenfassung, Fehlerbericht und Exitcodes 0/1/2/3. Tests prüfen Teilfehler und gezielte Wiederaufnahme mit derselben Verarbeitungskonfiguration.

### TS-06 – Nebenläufigkeit und Schreibsemantik der Vector-API · P1

- **Befund:** [Vector](../Vector/app.py) verwendet `SimpleConnectionPool` und ersetzt Datensätze durch `DELETE` plus `INSERT`. Gleichzeitige Schreibzugriffe auf denselben bisher nicht vorhandenen Schlüssel können am Unique Constraint scheitern; Updates ändern die interne `id`. Der Pool ist nicht für die nebenläufige Nutzung ausgelegt.
- **Auswirkung:** Sporadische Schreibfehler und instabile interne Identitäten. Diese Auswirkung wurde aus dem Code abgeleitet, nicht durch Lasttests bestätigt.
- **Abbau und Abschluss:** Atomares `INSERT … ON CONFLICT DO UPDATE`, einen für Threads geeigneten Pool und eine definierte Behandlung von Poolauslastung verwenden. Transaktionsabschluss und Ressourcenrückgabe zentralisieren. Integrationstests prüfen konkurrierende Writes, SQL-Fehler und nachfolgende erfolgreiche Requests.
- **Präzisierung:** Die Anwendung führt kein explizites Rollback aus. Daraus allein folgt kein Nachweis dauerhaft beschädigter Poolverbindungen: Die Bereinigung durch die konkrete Poolimplementierung muss berücksichtigt werden.
- **Konkretisierung durch Kapitel 8.3:** Transaktionslebenszyklus gemäß [8.3.5](8-3-error-handling.md#835-datenbank-und-ressourcenbereinigung) zentralisieren: Abschluss auch bei Lesezugriffen, explizites Rollback bei Fehlern, Schließen defekter Verbindungen und sichere Poolrückgabe. Poolerschöpfung kontrolliert behandeln; Schreib-Retries erst bei gesicherter Idempotenz gemäß 8.3.4 zulassen.

### TS-07 – Fehlende Erholung nach gescheiterter DB-Initialisierung · P2

- **Befund:** [Vector](../Vector/app.py) erstellt den Pool beim Modulimport. Scheitert dies, bleibt `db_pool` ohne weiteren Initialisierungsversuch `None`.
- **Auswirkung:** Ein vorübergehender Startreihenfolgefehler erfordert einen Prozessneustart, obwohl PostgreSQL später bereit ist.
- **Abbau und Abschluss:** Expliziten Initialisierungslebenszyklus mit begrenzten Verbindungsversuchen und Readiness definieren. Ein isolierter Integrationstest startet PostgreSQL verzögert und weist die selbstständige Erholung nach.
- **Konkretisierung durch Kapitel 8.3:** Initialisierungsversuche und Zeitlimits gemäß [8.3.4–8.3.5](8-3-error-handling.md#834-timeouts-und-wiederholungen) sowie Readiness gemäß [8.3.7](8-3-error-handling.md#837-diagnose-und-betriebszustand) absichern. Nichtverfügbarkeit liefert 503 mit Problem Details; isolierte Tests weisen begrenzte Wartezeiten und Erholung ohne Prozessneustart nach.

### TS-08 – Ungesicherte Kontext- und Metrikverarbeitung · P1

- **Befund:** [RAG](../rag/app.py) prüft Suchantworten nur auf den äußeren Listentyp und erwartet danach textuelles `chunktext` sowie `chunk_id`. Auch bei leerer Trefferliste wird generiert. `generate_answer` dividiert bei `eval_duration: 0` durch null. Leerer Generierungskontext und `ZeroDivisionError` wurden lokal mit Mocks bestätigt.
- **Auswirkung:** Antworten ohne Quellenkontext; fehlerhafte Treffer oder optionale Metriken verhindern die Ausgabe einer vorhandenen Modellantwort.
- **Abbau und Abschluss:** Treffereinträge prüfen, einen expliziten Antwortpfad für fehlenden Kontext definieren und fehlende beziehungsweise nullwertige Laufzeiten robust behandeln. Regressionstests prüfen leere Treffer, ungültige Metadaten und Nullzeiten. Ein echter Modelltest ergänzt eine nicht beantwortbare Frage; eine reine Promptvorgabe garantiert keine Faktentreue.
- **Konkretisierung durch Kapitel 8.3:** Ungültige Upstreamantworten gemäß [8.3.3](8-3-error-handling.md#833-problemtypregister-und-statuszuordnung) als 502 behandeln. Leere Treffer folgen [8.3.6](8-3-error-handling.md#836-fachliche-ergebnisse-und-importabschluss): HTTP 200 mit status no_context, leeren Chunks und Ablehnungsantwort ohne Generierung. Nicht ausgeführte Metriken nicht als gemessene Nullwerte darstellen; Retrievalausfälle dürfen diesen Erfolgspfad nicht auslösen.

### TS-09 – Duplizierte Verarbeitung und auseinanderlaufende Konfiguration · P2

- **Befund:** [RAG](../rag/app.py), [CLI](../interact.py) und [Analyse](../analyze.py) implementieren Embedding, Suche, Prompt und Generierung mehrfach. Defaults für Modell, Metrik, Filter, Timeouts und Metrikdarstellung unterscheiden sich. Das CLI nutzt aktuell `gemma4:e4b`, die RAG-API `phi3:mini`. Import- und Analysewerkzeuge haben eigene feste Dienstadressen und teilweise keine HTTP-Timeouts.
- **Auswirkung:** Fehlerbehebungen erreichen nur einzelne Pfade; Vergleiche ändern unbemerkt mehrere Parameter. Dienststörungen können Werkzeuge unbegrenzt blockieren.
- **Abbau und Abschluss:** Gemeinsame Funktionen und Konfigurationsobjekte für die Verarbeitung nutzen; CLI und HTTP bleiben Adapter. Unterschiede werden explizite Versuchsparameter. Unterstützte Netzwerkaufrufe erhalten konfigurierte Timeouts. Vertragstests prüfen äquivalentes Verhalten bei gleicher Konfiguration. Keine zusätzliche Klassenhierarchie ohne konkreten Austauschbedarf einführen.
- **Konkretisierung durch Kapitel 8.3:** Gemeinsame Fehlerklassen und Adapter gemäß [8.3.1](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten) einschließlich Container-Bereitstellung verwenden. Konfigurierbare Zeitlimits, RAG-Gesamtbudget und begrenzte Retries gemäß [8.3.4](8-3-error-handling.md#834-timeouts-und-wiederholungen) absichern; Generierung zunächst nicht automatisch wiederholen. Korrelation und sichere strukturierte Logs folgen 8.3.7; Fallbacks bleiben explizit und sichtbar.

### TS-10 – Inkonsistentes Ressourcen- und Begriffsmodell · P2

- **Befund:** [Vector](../Vector/app.py) verwendet `/vectors` zum Schreiben, `/chunks/<id>` zum Lesen und `/chunk` zum Löschen; `/chunks` zählt Zeilen. Die Benennungen sind inzwischen präzisiert: `embedding_set_id` bezeichnet das Set, `chunktext` den Quelltext (zuvor `metadata`, Migration vom 21.11.2026). Lesen ohne Variantenfilter nutzt weiterhin `LIMIT 1` ohne eindeutige Auswahl; `/find` liefert IDs ohne Variantenkennung. TS-10 bleibt deshalb offen.
- **Auswirkung:** Mehrdeutige Identitäten und überraschende Clientsemantik, sobald mehrere Varianten existieren.
- **Abbau und Abschluss:** Ressourcen, Schlüssel und Feldbegriffe verbindlich beschreiben. Mehrdeutige Einzelabfragen entweder zurückweisen oder als Sammlung beantworten. Ein Umstellungsplan erhält bestehende Clients oder kennzeichnet einen Schnittstellenbruch. Tests decken dieselbe Chunk-ID in zwei Varianten ab.

### TS-11 – Widersprüchlicher und datenbanknaher Vektorvertrag · P2

- **Befund:** [Vector-Docstrings](../Vector/app.py) erwarten pgvector-Strings; aktuelle Clients senden Zahlenlisten. Dimension, endliche Zahlenwerte und Metadatentypen sind nicht vollständig abgesichert. Suchantworten enthalten auch die gespeicherten Vektoren; [analyze.py](../analyze.py) verarbeitet diese als JSON-Strings. Das [Schema](../Vector/init.sql) bindet alle Varianten an 1024 Dimensionen.
- **Auswirkung:** Clientkopplung an Datenbankdarstellung, späte SQL-Fehler und unnötige Nutzlasten. Weitere Embeddingmodelle sind nicht allein durch eine neue Variantenkennung anschließbar.
- **Abbau und Abschluss:** Kanonisches JSON-Format und Dimensionsvertrag festlegen. Vektorausgabe für Diagnose explizit anforderbar machen und den Analyseclient anpassen. Tests prüfen Typen, Dimension und nicht endliche Werte. Die Unterstützung weiterer Dimensionen bleibt eine gesonderte Architekturentscheidung.
- **Konkretisierung durch Kapitel 8.3:** Vektoren gemäß [8.3.1–8.3.3](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten) früh validieren: ungültige Clientvektoren ergeben 400 vor SQL-Zugriff, ungültige Embeddingantworten 502. Tests prüfen auch Nullnorm bei Normalisierung und den Problem-Details-Vertrag.

### TS-12 – Unvollständige Adapter und ungenutzte Konfiguration · P2

- **Befund:** [gateway.py](../Ingest/gateway.py) gibt rohe `requests.Response`-Objekte zurück; [keywords.py](../Ingest/keywords.py) kennt weiterhin die jeweiligen Providerformate. Der Gatewayparameter `chunk` wird nicht genutzt. Import3 verwirft die gelieferten Metriken und die Frage. In [RAG](../rag/app.py) definierte Ollama-Endpunktkonstanten steuern die echten Aufrufe nicht; diese verwenden den Resolver. Tests orientieren sich teilweise an den Konstanten. Auch `QUERY` und `NUM_RESULTS` sind dort ungenutzt.
- **Auswirkung:** Die scheinbar gemeinsame Abstraktion kapselt Providerdetails nicht; Änderungen und Tests können sich auf wirkungslose Konfiguration beziehen.
- **Abbau und Abschluss:** Einen kleinen gemeinsamen Ergebnistyp für Keyword-Provider einführen. Unbenutzte Argumente und Konstanten entfernen; benötigte Versuchsdaten strukturiert speichern. Tests prüfen die tatsächlich aufgelösten Adressen und das gemeinsame Providerergebnis.
- **Konkretisierung durch Kapitel 8.3:** Adapter übersetzen technische Fehler und verletzte Antwortverträge gemäß [8.3.1–8.3.3](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten) in gemeinsame Anwendungsfehler unter Erhalt der Ursache. Tests sichern die Übersetzung ab; rohe Providerantworten nicht als öffentliche Fehlertexte weiterreichen.

### TS-13 – Widersprüchlicher Modelllade- und Health-Lebenszyklus · P2

- **Befund:** Seit TS-02 werden Modellladen und Inferenz synchronisiert; ungueltige Rerank-Anfragen loesen kein Modellladen mehr aus. `/health` laedt bei noch ungeladenem Dienst weiterhin das Defaultmodell und wartet auf laufende Modelloperationen. Getrennte Liveness-/Readiness-Endpunkte fehlen.
- **Auswirkung:** Health-Aufrufe koennen durch Modellinitialisierung oder Inferenz blockieren; Prozesslebendigkeit und Modellbereitschaft sind nicht getrennt erkennbar.
- **Abbau und Abschluss:** Getrennte Liveness-/Readiness-Zustaende mit Fehler-, Zustands- und Neustarttests einfuehren. Die Synchronisierung ist mit TS-02 umgesetzt; TS-13 bleibt fuer den Health-Vertrag offen.
- **Konkretisierung durch Kapitel 8.3:** Health-Vertrag gemäß [8.3.7](8-3-error-handling.md#837-diagnose-und-betriebszustand) umsetzen: Liveness ohne Modellinitialisierung, zeitlich begrenzte Readiness und 503 mit Problem Details bei fehlender Bereitschaft. Tests berücksichtigen laufendes Laden und Inferenz.

### TS-14 – Fehlerhafte Analyse und unklare Alt-Einstiegspunkte · P1

- **Befund:** In [analyze.py](../analyze.py) umfasst `GOLDCHUNK` nur die Keyword-Zeile; die folgenden Stringliterale sind eigenständige Ausdrücke. Dies wurde per AST-Auswertung bestätigt. [import.py](../Ingest/import.py) verwendet `np` ohne Import und übergibt ein nicht unterstütztes Argument `metadata` an die Speicherfunktion. Der [lokale Reranker](../reranker/reranker-local.py) dupliziert Serverlogik mit anderem Standardmodell.
- **Auswirkung:** Irreführende Ähnlichkeitsmessungen und erst im Fehlerpfad sichtbare Defekte; unklarer Wartungsumfang.
- **Abbau und Abschluss:** Den Goldtext korrigieren und durch einen gezielten Regressionstest sichern. Unterstützte Einstiegspunkte festlegen; andere ausdrücklich archivieren oder entfernen. Für unterstützte Varianten Smoke- und Fehlerpfadtests vorsehen. P1 betrifft die Messkorrektheit; umfassende Codekonsolidierung folgt mit TS-09.

### TS-15 – Nicht reproduzierbare Builds und fehlende Schemamigrationen · P2

- **Befund:** Die Dockerfiles für [Vector](../Vector/Dockerfile), [RAG](../rag/Dockerfile) und [Reranker](../reranker/Dockerfile) fixieren Abhängigkeiten nicht vollständig. pgvector wird vom aktuellen Repositorystand gebaut. Modellrevisionen werden nicht durchgängig erfasst. `init.sql` wirkt nur bei leerem Datenverzeichnis; ein versionierter Migrationspfad fehlt.
- **Auswirkung:** Gleicher Projektcode erzeugt unterschiedliche Laufzeitstände; bestehende Volumes bleiben bei Schemaänderungen zurück.
- **Abbau und Abschluss:** Aufgelöste Paketstände, pgvector-Revision, Basisimages und Modellidentitäten festhalten. Einen versionierten Migrationsprozess vor Datenmodelländerungen bereitstellen und gegen eine ältere Testdatenbank prüfen. Wiederholte Builds müssen dieselben dokumentierten Abhängigkeitsstände verwenden; bitgleiche Modellantworten sind kein Abschlusskriterium.

### TS-16 – Indexstrategie passt nicht zu allen Suchmetriken · P3

- **Befund:** [init.sql](../Vector/init.sql) erstellt nur einen HNSW-Index mit `vector_l2_ops`; [interact.py](../interact.py) sucht standardmäßig mit Cosinus. Dieser Index unterstützt den Cosinus-Operator nicht.
- **Auswirkung:** Metrikvergleiche können zugleich unterschiedliche Zugriffspfade vergleichen. Ein konkretes Laufzeitproblem wurde nicht gemessen.
- **Abbau und Abschluss:** Repräsentative Datenmengen und gefilterte sowie ungefilterte Suchpläne messen. Metrikspezifische Indizes oder eine begründete gemeinsame Suchstrategie wählen. Indexänderungen über TS-15 migrieren; Laufzeit und Retrievalqualität gemeinsam dokumentieren.

### TS-17 – Testabdeckung umgeht relevante Verarbeitungspfade · P1, begleitend

- **Befund:** Der [E2E-Test](../tests/podman/test_rag_e2e.py) importiert selbst und umgeht Import3 samt Keywords. [Chunking-Tests](../tests/unit/test_chunking.py) prüfen keinen echten Mehrfachsplit mit Grenzen und Overlap. [Vector-Unit-Tests](../tests/unit/test_vector_api_unit.py) decken konkurrierendes Schreiben und die bestätigten fehlerhaften Eingaben nicht ab. Persistenz-, Wiederanlauf- und Lastnachweise fehlen teilweise.
- **Auswirkung:** Eine grüne Suite erkennt Fehler im tatsächlich benutzten Pfad nicht zuverlässig.
- **Abbau und Abschluss:** Regressionstests jeweils mit der zugehörigen Korrektur liefern. Zusätzlich den unterstützten Importpfad inklusive Keyword-Schritt, Variantenisolation und Resume prüfen; Chunking an einem real geteilten Text absichern. Echte Modelltests bleiben von schnellen deterministischen Tests getrennt. Testressourcen müssen isoliert sein; manuell genutzte Daten und Volumes bleiben erhalten.
- **Konkretisierung durch Kapitel 8.3:** Abnahmekriterien aus [8.3.8](8-3-error-handling.md#838-umsetzung-und-abnahmekriterien) mitführen: RFC-9457-Vertrag, HTTP-Status und Header, sichere Meldungen, Adapterfehler, Timeout-/Retrybudget, Korrelation, leeren Kontext und Import-Teilfehler prüfen. Isolierte Podman-Tests sichern Rollback, Poolwiederverwendung, parallele Upserts, verzögerten DB-Start und Readiness ab.

### TS-18 – Experimenteller Betriebsrahmen · P3, bedarfsabhängig

- **Befund:** Die APIs starten Flask-Entwicklungsserver; Authentifizierung fehlt, Beispiel-DB-Zugangsdaten sind fest vorbelegt. Ein einheitliches Readiness-Konzept fehlt. Siehe [Startanleitung](../README.md), [Vector](../Vector/app.py), [RAG](../rag/app.py) und [Reranker](../reranker/app.py).
- **Auswirkung:** Der dokumentierte lokale Experimentbetrieb ist nicht ohne weitere Maßnahmen auf Mehrbenutzer- oder exponierten Dauerbetrieb übertragbar.
- **Abbau und Abschluss:** Vor einer solchen Nutzung Betriebsgrenzen festlegen, geeigneten Serverbetrieb, Zugangskontrolle, externe Geheimniskonfiguration und Readiness umsetzen und prüfen. Bei unverändert lokalem Einsatz bleibt dies eine dokumentierte Einschränkung. Bei geplanter Exposition steigt die Priorität vor deren Freigabe auf P1.
- **Konkretisierung durch Kapitel 8.3:** Readiness und öffentliche Fehlerausgaben folgen [8.3.7](8-3-error-handling.md#837-diagnose-und-betriebszustand). Die lokale Betriebsabsicherung unter TS-07/TS-13 hängt nicht erst von einer späteren Exposition ab.

## 11.2.3 Priorisierte Reihenfolge für den Abbau

Die Reihenfolge ist ein Vorschlag für aufeinander aufbauende Arbeitspakete. P1 bezeichnet die Dringlichkeit, die Reihenfolge berücksichtigt zusätzlich Abhängigkeiten. TS-17 begleitet jedes Paket: Tests werden mit der Korrektur ergänzt, nicht erst nach dem gesamten Umbau. Die Pakete 1 bis 3 benötigen keine vorgelagerte Gesamtrefaktorierung und verändern keine Datenidentitäten.

| Reihenfolge | Paket und Schulden | Ergebnis / Freigabekriterium | Abhängigkeit |
|---|---|---|---|
| 1 | **Verfälschte Messungen verhindern:** TS-01, TS-02, unmittelbare Fehler aus TS-14 | Import-/Suchdefaults passen zusammen; Rerankermodell ist nachweisbar; Goldtext ist korrekt; defekte Alt-Einstiegspunkte sind gekennzeichnet oder korrigiert. | Keine. Kleine gezielte Änderungen vor strukturellem Umbau. |
| 2 | **Fehlerpfade verlässlich machen:** TS-03, TS-08 | RFC-9457-kompatible Problemantworten gemäß [8.3](8-3-error-handling.md), frühe Validierung, definierter Umgang mit leerem Kontext und robusten Metriken; Regressionstests bestehen. | Keine harte Abhängigkeit von 1. Bestehende API-Namen zunächst erhalten; Fehlerformat mit Clients, README und Tests gemeinsam umstellen. |
| 3 | **Datenbankzugriffe stabilisieren:** TS-06, TS-07 | Atomare Updates, geeigneter Pool, Erholung nach verzögertem DB-Start; isolierte Parallelitäts- und Fehlerpfadtests bestehen. | Bestehende Schlüssel bleiben erhalten; keine fachliche Datenmigration erforderlich. |
| 4 | **Reproduzierbare Änderungsbasis schaffen:** TS-15 | Versionierte Abhängigkeitsstände und getesteter Migrationsmechanismus stehen bereit. | Vor Umsetzung der Schemaänderungen aus 5 und gegebenenfalls 6. |
| 5 | **Importidentität sichern:** TS-05; manuelle Begleitpflege gemäß R-01 | Set-Zuordnung in Abschnitt 8.2 pflegen; keine technische Konfigurationspersistenz vorgesehen. Kollisionsfreie Dokumentidentität, eindeutiger Importabschluss und Resume; Migrations-/Neuimportweg für Bestandsdaten geprüft. | Paket 3 und Migrationsbasis aus 4 für technische Änderungen aus TS-05. |
| 6 | **Schnittstellen konsolidieren:** TS-10, TS-11 | Dokumentierter Ressourcen-, Identitäts- und JSON-Vertrag mit kompatibler Umstellung oder ausdrücklich versioniertem Bruch. | Identitätsentscheidungen aus 5; Migrationsbasis aus 4 bei Schemaänderungen. |
| 7 | **Gemeinsame Verarbeitung nutzen:** TS-09, TS-12, verbleibende Konsolidierung aus TS-14 | CLI, HTTP und Analyse verwenden denselben Kern bei expliziten Parametern; Providerdetails sind gekapselt, wirkungslose Optionen entfernt, Timeouts gesetzt. | Stabile Verträge aus 6. Bestehende Unterschiede zuerst durch Tests sichtbar machen. |
| 8 | **Dienstlebenszyklus abschließen:** TS-13 | Synchronisierte Modellinitialisierung und getrennte, getestete Liveness-/Readiness-Zustände. | Keine harte Abhängigkeit von 4 bis 7; bei Startproblemen vorziehbar. |
| 9 | **Performance und erweiterten Betrieb absichern:** TS-16, TS-18 | Gemessene und dokumentierte Indexstrategie; Betriebsmaßnahmen entsprechend dem tatsächlichen Einsatz. | Für belastbare Vergleiche stabile Varianten und Builds aus 4/5; Indexmigration über 4. Exponierter Betrieb darf TS-18 nicht aufschieben. |

Für R-01 gilt die manuelle Zuordnung aus Abschnitt 8.2: Historische Varianten dürfen nicht nachträglich mit unbekannten Konfigurationen als reproduzierbar ausgegeben werden. Unbekannte Herkunft wird im Verzeichnis ausdrücklich markiert; daraus folgt keine Pflicht zum Neuimport. Für technische Änderungen aus TS-05 bleibt ein gesonderter Umgang mit Bestandsdaten festzulegen. Keine Migration darf bestehende manuell genutzte Volumes stillschweigend löschen.

## 11.2.4 Verifikation und Fortschreibung

Zu jedem umgesetzten Paket werden betroffene Registereinträge mit Status, Implementierungsreferenz und Prüfnachweis aktualisiert. Ein Eintrag ist erst erledigt, wenn seine Abschlusskriterien erfüllt und die betroffenen Architektur- beziehungsweise Schnittstellenbeschreibungen angepasst sind. Offene Architekturentscheidungen sind mit der Umsetzung in arc42-Abschnitt 9 zu dokumentieren; die Fehlerverträge und Abnahmekriterien aus [Kapitel 8.3](8-3-error-handling.md) bilden den dokumentierten Zielzustand und bleiben bis zum Implementierungs- und Prüfnachweis offen.

| Änderung | Erforderlicher Nachweis |
|---|---|
| Validierung, Metriken, Konfiguration, Adapter | Betroffene containerfreie Unit- und Vertragstests. |
| SQL, Pool, Datenidentität, Migration | Isolierte Podman-Integration einschließlich Parallelität, Wiederanlauf oder Migration entsprechend der Änderung. |
| Import und RAG-Zusammenspiel | Test des tatsächlichen unterstützten Importpfads und E2E mit echten Embedding-/Antwortmodellen; Keyword-Schritt gesondert absichern. |
| Indexstrategie | Schema-/Indexprüfung, repräsentative Suchpläne und Messungen mit dokumentierter Datenmenge und Variantenkonfiguration. |
| Modellinitialisierung und Betrieb | Fehler-, Zustands- und Neustarttests; Last- beziehungsweise Zugangstests entsprechend dem Einsatz. |

Die ausführbaren Befehle und Voraussetzungen bleiben im [Testkonzept](8-1-testkonzept.md) und [README](../README.md). Nicht ausgeführte Prüfungen werden bei jedem Umsetzungsschritt mit Grund ausgewiesen.
