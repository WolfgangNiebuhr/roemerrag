# 11 Risiken und technische Schulden

Stand: 15.11.2026. Dieses Kapitel nach arc42 dokumentiert die im Projekt untersuchten technischen Schulden und einen vorgeschlagenen Abbauplan. Alle Einträge sind offen; die beschriebenen Maßnahmen sind Zielzustände und noch nicht umgesetzt.

Die [Bausteinsicht](5-bausteinsicht.md) beschreibt die betroffenen Komponenten, die [Laufzeitsicht](6-laufzeitsicht.md) deren Zusammenspiel und das [Testkonzept](8-1-testkonzept.md) die vorhandenen Prüfungen. Verzeichnisse namens `k8s` sind ausgeschlossen. Bewertungsmaßstab ist der lokale Podman-Betrieb eines Systems zum Vergleich von RAG-Strategien, kein bereits zugesagter Produktionsbetrieb.

## 11.1 Bewertung und Nachweisgrenzen

Die Priorität richtet sich zuerst nach Datenintegrität und Verlässlichkeit von Experimenten, danach nach Betriebsstabilität, Änderbarkeit und Performance.

| Priorität | Bedeutung |
|---|---|
| P1 | Zuerst abbauen: verfälschte Vergleiche, inkonsistente Daten oder bestätigte Fehler im regulären Verarbeitungspfad. |
| P2 | Anschließend abbauen: strukturelle Inkonsistenzen, Betriebsrisiken und fehlende Reproduzierbarkeit. |
| P3 | Nach Stabilisierung beziehungsweise bei entsprechendem Betriebsbedarf bearbeiten. |

Die Analyse umfasst Python-Code, SQL, Dockerfiles und Tests. Die 24 containerfreien Unit-Tests bestanden bei der Analyse. Ergänzende lokale Prüfungen mit gemockten HTTP-, Datenbank- und Modellabhängigkeiten bestätigten die unter TS-03, TS-08 und TS-14 beschriebenen Fehler. Podman-, Modell-, Parallelitäts- und Lasttests wurden dafür nicht ausgeführt. Aus Code abgeleitete Risiken sind daher keine gemessenen Ausfälle oder Performancebefunde. Ein im Testkonzept dokumentierter früherer E2E-Lauf ersetzt diese Prüfungen nicht.

## 11.2 Schuldenregister

### TS-01 – Abweichende Import- und Retrievaldefaults · P1

- **Befund:** [Import3](../Ingest/import3.py) schreibt `snowflake-arctic-embed2-v2`; [RAG](../rag/app.py), Funktion `process_request`, sucht standardmäßig `snowflake-arctic-embed2`. Der Workaround steht im README.
- **Risiko:** Erfolgreich importierte Daten bleiben für Standardanfragen unsichtbar. Eine Antwort kann trotzdem erzeugt werden, siehe TS-08.
- **Abbau und Abschluss:** Modell und Variantenkennung explizit trennen und die Defaults gemeinsam konfigurieren. Ein Vertragstest weist nach, dass ein Standardimport mit einer Standardanfrage gefunden wird; bewusst abweichende Varianten bleiben gezielt auswählbar.

### TS-02 – Wirkungslose Reranker-Modellwahl · P1

- **Befund:** [interact.py](../interact.py), `rerank_results`, sendet den CLI-Parameter `--reranker` als `model`. [reranker/app.py](../reranker/app.py) ignoriert ihn und verwendet ausschließlich `RERANK_MODEL`.
- **Risiko:** Vergleichsläufe behaupten unterschiedliche Modelle, führen aber dasselbe Modell aus.
- **Abbau und Abschluss:** Einen verbindlichen Vertrag wählen: serverseitig festgelegtes Modell mit entfernten beziehungsweise zurückgewiesenen Auswahlparametern oder tatsächlich unterstützte Modellwahl. Antworten und Versuchsergebnisse nennen das verwendete Modell; ein Vertragstest prüft Abweichungen.

### TS-03 – Lückenhafte Requestvalidierung und Fehlerverträge · P1

- **Befund:** [Vector](../Vector/app.py) liest Pflichtfelder und konvertiert `num_results` teilweise vor dem Fehlerhandler. [Reranker](../reranker/app.py) setzt ein geeignetes äußeres JSON-Objekt voraus. [RAG](../rag/app.py) prüft das äußere Objekt, aber nicht alle Feldtypen und Wertebereiche. Lokal bestätigt: `/vectors` mit `{}`, `/search` mit `num_results: "abc"` und `/rerank` mit JSON `123` liefern HTTP 500 mit HTML. Ein Suchfehler 400 wird über RAG zum Fehler 500; die Embeddingberechnung erfolgt vorher.
- **Risiko:** Eingabefehler erscheinen als Serverdefekte; Clients können Fehler nicht einheitlich auswerten. Ungültige Anfragen verursachen vermeidbare Modellarbeit.
- **Abbau und Abschluss:** Gemeinsame Regeln für JSON-Objekte, Textfelder, Dokumentelemente, Metriken und begrenzte Trefferzahlen dokumentieren und vor Dienstaufrufen prüfen. Fehler liefern ein stabiles JSON-Schema mit vereinbarten 4xx-/5xx-Statuscodes. Regressionstests decken die genannten Fälle sowie ungültiges JSON ab.

### TS-04 – Unzureichende Identität von Importvarianten · P1

- **Befund:** [Import3](../Ingest/import3.py) schreibt die feste Kennung `snowflake-arctic-embed2-v2`, ohne Modell- und Promptkonfiguration vollst?ndig abzubilden. Das [Schema](../Vector/init.sql) speichert keine vollständige Verarbeitungskonfiguration.
- **Risiko:** Inhaltlich verschiedene Verfahren überschreiben dieselben Schlüssel. Ergebnisse lassen sich Chunking, Prompts und Modellständen nicht zuverlässig zuordnen.
- **Abbau und Abschluss:** Eine persistierte Variantenkonfiguration für Chunking, Keyword-Verfahren, Prompts, Modelle und Normalisierung einführen. Konfigurationsänderungen erzeugen eine andere Identität; Versuchsergebnisse referenzieren sie. Tests weisen die Isolation zweier Varianten nach. Modellrevisionen und Buildstände ergänzt TS-15.

### TS-05 – Kollidierende Chunk-IDs und unvollständige Wiederholungsimporte · P1

- **Befund:** [Import3](../Ingest/import3.py), `process_file`, erzeugt IDs aus `basename.split('.')[0]` und laufender Nummer. `rom.band1.txt` und `rom.band2.txt` kollidieren innerhalb derselben Variante. Kürzere Wiederholungsimporte entfernen keine alten überzähligen Chunks. Chunkfehler werden protokolliert; ein zusammenfassender Fehlerstatus fehlt.
- **Risiko:** Quellen werden vermischt; veraltete und neue Inhalte bleiben gemeinsam abrufbar. Ein Teilimport kann als erfolgreicher Lauf erscheinen.
- **Abbau und Abschluss:** Dokumentidentität, Inhaltsversion und Importlauf trennen. Abschluss und Aktivierung eines Imports sowie Fehlerstatus und Resume-Semantik festlegen. Tests prüfen Namenskollisionen, verkürzte Neuimporte, Abbruch und Wiederaufnahme. Bestehende Daten benötigen einen expliziten Migrations- oder Neuimportpfad.

### TS-06 – Nebenläufigkeit und Schreibsemantik der Vector-API · P1

- **Befund:** [Vector](../Vector/app.py) verwendet `SimpleConnectionPool` und ersetzt Datensätze durch `DELETE` plus `INSERT`. Gleichzeitige Schreibzugriffe auf denselben bisher nicht vorhandenen Schlüssel können am Unique Constraint scheitern; Updates ändern die interne `id`. Der Pool ist nicht für die nebenläufige Nutzung ausgelegt.
- **Risiko:** Sporadische Schreibfehler und instabile interne Identitäten. Dieses Risiko wurde aus dem Code abgeleitet, nicht durch Lasttests bestätigt.
- **Abbau und Abschluss:** Atomares `INSERT … ON CONFLICT DO UPDATE`, einen für Threads geeigneten Pool und eine definierte Behandlung von Poolauslastung verwenden. Transaktionsabschluss und Ressourcenrückgabe zentralisieren. Integrationstests prüfen konkurrierende Writes, SQL-Fehler und nachfolgende erfolgreiche Requests.
- **Präzisierung:** Die Anwendung führt kein explizites Rollback aus. Daraus allein folgt kein Nachweis dauerhaft beschädigter Poolverbindungen: Die Bereinigung durch die konkrete Poolimplementierung muss berücksichtigt werden.

### TS-07 – Fehlende Erholung nach gescheiterter DB-Initialisierung · P2

- **Befund:** [Vector](../Vector/app.py) erstellt den Pool beim Modulimport. Scheitert dies, bleibt `db_pool` ohne weiteren Initialisierungsversuch `None`.
- **Risiko:** Ein vorübergehender Startreihenfolgefehler erfordert einen Prozessneustart, obwohl PostgreSQL später bereit ist.
- **Abbau und Abschluss:** Expliziten Initialisierungslebenszyklus mit begrenzten Verbindungsversuchen und Readiness definieren. Ein isolierter Integrationstest startet PostgreSQL verzögert und weist die selbstständige Erholung nach.

### TS-08 – Ungesicherte Kontext- und Metrikverarbeitung · P1

- **Befund:** [RAG](../rag/app.py) prüft Suchantworten nur auf den äußeren Listentyp und erwartet danach textuelles `metadata` sowie `chunk_id`. Auch bei leerer Trefferliste wird generiert. `generate_answer` dividiert bei `eval_duration: 0` durch null. Leerer Generierungskontext und `ZeroDivisionError` wurden lokal mit Mocks bestätigt.
- **Risiko:** Antworten ohne Quellenkontext; fehlerhafte Treffer oder optionale Metriken verhindern die Ausgabe einer vorhandenen Modellantwort.
- **Abbau und Abschluss:** Treffereinträge prüfen, einen expliziten Antwortpfad für fehlenden Kontext definieren und fehlende beziehungsweise nullwertige Laufzeiten robust behandeln. Regressionstests prüfen leere Treffer, ungültige Metadaten und Nullzeiten. Ein echter Modelltest ergänzt eine nicht beantwortbare Frage; eine reine Promptvorgabe garantiert keine Faktentreue.

### TS-09 – Duplizierte Verarbeitung und auseinanderlaufende Konfiguration · P2

- **Befund:** [RAG](../rag/app.py), [CLI](../interact.py) und [Analyse](../analyze.py) implementieren Embedding, Suche, Prompt und Generierung mehrfach. Defaults für Modell, Metrik, Filter, Timeouts und Metrikdarstellung unterscheiden sich. Das CLI nutzt aktuell `gemma4:e4b`, die RAG-API `phi3:mini`. Import- und Analysewerkzeuge haben eigene feste Dienstadressen und teilweise keine HTTP-Timeouts.
- **Risiko:** Fehlerbehebungen erreichen nur einzelne Pfade; Vergleiche ändern unbemerkt mehrere Parameter. Dienststörungen können Werkzeuge unbegrenzt blockieren.
- **Abbau und Abschluss:** Gemeinsame Funktionen und Konfigurationsobjekte für die Verarbeitung nutzen; CLI und HTTP bleiben Adapter. Unterschiede werden explizite Versuchsparameter. Unterstützte Netzwerkaufrufe erhalten konfigurierte Timeouts. Vertragstests prüfen äquivalentes Verhalten bei gleicher Konfiguration. Keine zusätzliche Klassenhierarchie ohne konkreten Austauschbedarf einführen.

### TS-10 – Inkonsistentes Ressourcen- und Begriffsmodell · P2

- **Befund:** [Vector](../Vector/app.py) verwendet `/vectors` zum Schreiben, `/chunks/<id>` zum Lesen und `/chunk` zum Löschen; `/chunks` zählt Zeilen. `embedding` ist eine Variantenkennung, `metadata` überwiegend Quelltext. Lesen ohne Variantenfilter nutzt `LIMIT 1` ohne eindeutige Auswahl; `/find` liefert IDs ohne Variantenkennung.
- **Risiko:** Mehrdeutige Identitäten und überraschende Clientsemantik, sobald mehrere Varianten existieren.
- **Abbau und Abschluss:** Ressourcen, Schlüssel und Feldbegriffe verbindlich beschreiben. Mehrdeutige Einzelabfragen entweder zurückweisen oder als Sammlung beantworten. Ein Umstellungsplan erhält bestehende Clients oder kennzeichnet einen Schnittstellenbruch. Tests decken dieselbe Chunk-ID in zwei Varianten ab.

### TS-11 – Widersprüchlicher und datenbanknaher Vektorvertrag · P2

- **Befund:** [Vector-Docstrings](../Vector/app.py) erwarten pgvector-Strings; aktuelle Clients senden Zahlenlisten. Dimension, endliche Zahlenwerte und Metadatentypen sind nicht vollständig abgesichert. Suchantworten enthalten auch die gespeicherten Vektoren; [analyze.py](../analyze.py) verarbeitet diese als JSON-Strings. Das [Schema](../Vector/init.sql) bindet alle Varianten an 1024 Dimensionen.
- **Risiko:** Clientkopplung an Datenbankdarstellung, späte SQL-Fehler und unnötige Nutzlasten. Weitere Embeddingmodelle sind nicht allein durch eine neue Variantenkennung anschließbar.
- **Abbau und Abschluss:** Kanonisches JSON-Format und Dimensionsvertrag festlegen. Vektorausgabe für Diagnose explizit anforderbar machen und den Analyseclient anpassen. Tests prüfen Typen, Dimension und nicht endliche Werte. Die Unterstützung weiterer Dimensionen bleibt eine gesonderte Architekturentscheidung.

### TS-12 – Unvollständige Adapter und ungenutzte Konfiguration · P2

- **Befund:** [gateway.py](../Ingest/gateway.py) gibt rohe `requests.Response`-Objekte zurück; [keywords.py](../Ingest/keywords.py) kennt weiterhin die jeweiligen Providerformate. Der Gatewayparameter `chunk` wird nicht genutzt. Import3 verwirft die gelieferten Metriken und die Frage. In [RAG](../rag/app.py) definierte Ollama-Endpunktkonstanten steuern die echten Aufrufe nicht; diese verwenden den Resolver. Tests orientieren sich teilweise an den Konstanten. Auch `QUERY` und `NUM_RESULTS` sind dort ungenutzt.
- **Risiko:** Die scheinbar gemeinsame Abstraktion kapselt Providerdetails nicht; Änderungen und Tests können sich auf wirkungslose Konfiguration beziehen.
- **Abbau und Abschluss:** Einen kleinen gemeinsamen Ergebnistyp für Keyword-Provider einführen. Unbenutzte Argumente und Konstanten entfernen; benötigte Versuchsdaten strukturiert speichern. Tests prüfen die tatsächlich aufgelösten Adressen und das gemeinsame Providerergebnis.

### TS-13 – Widersprüchlicher Modelllade- und Health-Lebenszyklus · P2

- **Befund:** [Reranker](../reranker/app.py) lädt in `before_request`, auch vor `/health` und ungültigen Requests. Der Health-Zweig `initializing` ist dadurch im normalen Ablauf praktisch unerreichbar. Gleichzeitige erste Requests sind nicht gegen mehrfaches Laden abgesichert.
- **Risiko:** Health-Aufrufe blockieren auf Modellinitialisierung; potenziell mehrfacher Speicherverbrauch und unklarer Bereitschaftszustand.
- **Abbau und Abschluss:** Initialisierung synchronisieren und Liveness von Readiness trennen. Tests prüfen Ladefehler, parallele erste Requests und beobachtbare Zustände vor und nach dem Laden.

### TS-14 – Fehlerhafte Analyse und unklare Alt-Einstiegspunkte · P1

- **Befund:** In [analyze.py](../analyze.py) umfasst `GOLDCHUNK` nur die Keyword-Zeile; die folgenden Stringliterale sind eigenständige Ausdrücke. Dies wurde per AST-Auswertung bestätigt. [import.py](../Ingest/import.py) verwendet `np` ohne Import und übergibt ein nicht unterstütztes Argument `metadata` an die Speicherfunktion. Der [lokale Reranker](../reranker/reranker-local.py) dupliziert Serverlogik mit anderem Standardmodell.
- **Risiko:** Irreführende Ähnlichkeitsmessungen und erst im Fehlerpfad sichtbare Defekte; unklarer Wartungsumfang.
- **Abbau und Abschluss:** Den Goldtext korrigieren und durch einen gezielten Regressionstest sichern. Unterstützte Einstiegspunkte festlegen; andere ausdrücklich archivieren oder entfernen. Für unterstützte Varianten Smoke- und Fehlerpfadtests vorsehen. P1 betrifft die Messkorrektheit; umfassende Codekonsolidierung folgt mit TS-09.

### TS-15 – Nicht reproduzierbare Builds und fehlende Schemamigrationen · P2

- **Befund:** Die Dockerfiles für [Vector](../Vector/Dockerfile), [RAG](../rag/Dockerfile) und [Reranker](../reranker/Dockerfile) fixieren Abhängigkeiten nicht vollständig. pgvector wird vom aktuellen Repositorystand gebaut. Modellrevisionen werden nicht durchgängig erfasst. `init.sql` wirkt nur bei leerem Datenverzeichnis; ein versionierter Migrationspfad fehlt.
- **Risiko:** Gleicher Projektcode erzeugt unterschiedliche Laufzeitstände; bestehende Volumes bleiben bei Schemaänderungen zurück.
- **Abbau und Abschluss:** Aufgelöste Paketstände, pgvector-Revision, Basisimages und Modellidentitäten festhalten. Einen versionierten Migrationsprozess vor Datenmodelländerungen bereitstellen und gegen eine ältere Testdatenbank prüfen. Wiederholte Builds müssen dieselben dokumentierten Abhängigkeitsstände verwenden; bitgleiche Modellantworten sind kein Abschlusskriterium.

### TS-16 – Indexstrategie passt nicht zu allen Suchmetriken · P3

- **Befund:** [init.sql](../Vector/init.sql) erstellt nur einen HNSW-Index mit `vector_l2_ops`; [interact.py](../interact.py) sucht standardmäßig mit Cosinus. Dieser Index unterstützt den Cosinus-Operator nicht.
- **Risiko:** Metrikvergleiche können zugleich unterschiedliche Zugriffspfade vergleichen. Ein konkretes Laufzeitproblem wurde nicht gemessen.
- **Abbau und Abschluss:** Repräsentative Datenmengen und gefilterte sowie ungefilterte Suchpläne messen. Metrikspezifische Indizes oder eine begründete gemeinsame Suchstrategie wählen. Indexänderungen über TS-15 migrieren; Laufzeit und Retrievalqualität gemeinsam dokumentieren.

### TS-17 – Testabdeckung umgeht relevante Verarbeitungspfade · P1, begleitend

- **Befund:** Der [E2E-Test](../tests/podman/test_rag_e2e.py) importiert selbst und umgeht Import3 samt Keywords. [Chunking-Tests](../tests/unit/test_chunking.py) prüfen keinen echten Mehrfachsplit mit Grenzen und Overlap. [Vector-Unit-Tests](../tests/unit/test_vector_api_unit.py) decken konkurrierendes Schreiben und die bestätigten fehlerhaften Eingaben nicht ab. Persistenz-, Wiederanlauf- und Lastnachweise fehlen teilweise.
- **Risiko:** Eine grüne Suite erkennt Fehler im tatsächlich benutzten Pfad nicht zuverlässig.
- **Abbau und Abschluss:** Regressionstests jeweils mit der zugehörigen Korrektur liefern. Zusätzlich den unterstützten Importpfad inklusive Keyword-Schritt, Variantenisolation und Resume prüfen; Chunking an einem real geteilten Text absichern. Echte Modelltests bleiben von schnellen deterministischen Tests getrennt. Testressourcen müssen isoliert sein; manuell genutzte Daten und Volumes bleiben erhalten.

### TS-18 – Experimenteller Betriebsrahmen · P3, bedarfsabhängig

- **Befund:** Die APIs starten Flask-Entwicklungsserver; Authentifizierung fehlt, Beispiel-DB-Zugangsdaten sind fest vorbelegt. Ein einheitliches Readiness-Konzept fehlt. Siehe [Startanleitung](../README.md), [Vector](../Vector/app.py), [RAG](../rag/app.py) und [Reranker](../reranker/app.py).
- **Risiko:** Der dokumentierte lokale Experimentbetrieb ist nicht ohne weitere Maßnahmen auf Mehrbenutzer- oder exponierten Dauerbetrieb übertragbar.
- **Abbau und Abschluss:** Vor einer solchen Nutzung Betriebsgrenzen festlegen, geeigneten Serverbetrieb, Zugangskontrolle, externe Geheimniskonfiguration und Readiness umsetzen und prüfen. Bei unverändert lokalem Einsatz bleibt dies eine dokumentierte Einschränkung. Bei geplanter Exposition steigt die Priorität vor deren Freigabe auf P1.

## 11.3 Priorisierte Reihenfolge für den Abbau

Die Reihenfolge ist ein Vorschlag für aufeinander aufbauende Arbeitspakete. P1 bezeichnet die Dringlichkeit, die Reihenfolge berücksichtigt zusätzlich Abhängigkeiten. TS-17 begleitet jedes Paket: Tests werden mit der Korrektur ergänzt, nicht erst nach dem gesamten Umbau. Die Pakete 1 bis 3 benötigen keine vorgelagerte Gesamtrefaktorierung und verändern keine Datenidentitäten.

| Reihenfolge | Paket und Schulden | Ergebnis / Freigabekriterium | Abhängigkeit |
|---|---|---|---|
| 1 | **Verfälschte Messungen verhindern:** TS-01, TS-02, unmittelbare Fehler aus TS-14 | Import-/Suchdefaults passen zusammen; Rerankermodell ist nachweisbar; Goldtext ist korrekt; defekte Alt-Einstiegspunkte sind gekennzeichnet oder korrigiert. | Keine. Kleine gezielte Änderungen vor strukturellem Umbau. |
| 2 | **Fehlerpfade verlässlich machen:** TS-03, TS-08 | Einheitliche JSON-Fehler, frühe Validierung, definierter Umgang mit leerem Kontext und robusten Metriken; Regressionstests bestehen. | Keine harte Abhängigkeit von 1. Bestehende API-Namen zunächst erhalten. |
| 3 | **Datenbankzugriffe stabilisieren:** TS-06, TS-07 | Atomare Updates, geeigneter Pool, Erholung nach verzögertem DB-Start; isolierte Parallelitäts- und Fehlerpfadtests bestehen. | Bestehende Schlüssel bleiben erhalten; keine fachliche Datenmigration erforderlich. |
| 4 | **Reproduzierbare Änderungsbasis schaffen:** TS-15 | Versionierte Abhängigkeitsstände und getesteter Migrationsmechanismus stehen bereit. | Vor Umsetzung der Schemaänderungen aus 5 und gegebenenfalls 6. |
| 5 | **Experiment- und Importidentität sichern:** TS-04, TS-05 | Variantenkonfiguration, kollisionsfreie Dokumentidentität, eindeutiger Importabschluss und Resume; Migrations-/Neuimportweg für Bestandsdaten geprüft. | Paket 3 und Migrationsbasis aus 4. Vorher entscheiden, wie Bestandsvarianten zugeordnet werden. |
| 6 | **Schnittstellen konsolidieren:** TS-10, TS-11 | Dokumentierter Ressourcen-, Identitäts- und JSON-Vertrag mit kompatibler Umstellung oder ausdrücklich versioniertem Bruch. | Identitätsentscheidungen aus 5; Migrationsbasis aus 4 bei Schemaänderungen. |
| 7 | **Gemeinsame Verarbeitung nutzen:** TS-09, TS-12, verbleibende Konsolidierung aus TS-14 | CLI, HTTP und Analyse verwenden denselben Kern bei expliziten Parametern; Providerdetails sind gekapselt, wirkungslose Optionen entfernt, Timeouts gesetzt. | Stabile Verträge aus 6. Bestehende Unterschiede zuerst durch Tests sichtbar machen. |
| 8 | **Dienstlebenszyklus abschließen:** TS-13 | Synchronisierte Modellinitialisierung und getrennte, getestete Liveness-/Readiness-Zustände. | Keine harte Abhängigkeit von 4 bis 7; bei Startproblemen vorziehbar. |
| 9 | **Performance und erweiterten Betrieb absichern:** TS-16, TS-18 | Gemessene und dokumentierte Indexstrategie; Betriebsmaßnahmen entsprechend dem tatsächlichen Einsatz. | Für belastbare Vergleiche stabile Varianten und Builds aus 4/5; Indexmigration über 4. Exponierter Betrieb darf TS-18 nicht aufschieben. |

Für Paket 5 ist vor der Umsetzung eine Entscheidung über die Behandlung vorhandener Daten nötig: Historische Varianten dürfen nicht nachträglich mit unbekannten Konfigurationen als reproduzierbar ausgegeben werden. Unbekannte Herkunft wird explizit markiert oder durch einen kontrollierten Neuimport ersetzt. Keine Migration darf bestehende manuell genutzte Volumes stillschweigend löschen.

## 11.4 Verifikation und Fortschreibung

Zu jedem umgesetzten Paket werden betroffene Registereinträge mit Status, Implementierungsreferenz und Prüfnachweis aktualisiert. Ein Eintrag ist erst erledigt, wenn seine Abschlusskriterien erfüllt und die betroffenen Architektur- beziehungsweise Schnittstellenbeschreibungen angepasst sind. Offene Architekturentscheidungen sind mit der Umsetzung in arc42-Abschnitt 9 zu dokumentieren; dieses Kapitel beschreibt noch keine beschlossenen Zielverträge.

| Änderung | Erforderlicher Nachweis |
|---|---|
| Validierung, Metriken, Konfiguration, Adapter | Betroffene containerfreie Unit- und Vertragstests. |
| SQL, Pool, Datenidentität, Migration | Isolierte Podman-Integration einschließlich Parallelität, Wiederanlauf oder Migration entsprechend der Änderung. |
| Import und RAG-Zusammenspiel | Test des tatsächlichen unterstützten Importpfads und E2E mit echten Embedding-/Antwortmodellen; Keyword-Schritt gesondert absichern. |
| Indexstrategie | Schema-/Indexprüfung, repräsentative Suchpläne und Messungen mit dokumentierter Datenmenge und Variantenkonfiguration. |
| Modellinitialisierung und Betrieb | Fehler-, Zustands- und Neustarttests; Last- beziehungsweise Zugangstests entsprechend dem Einsatz. |

Die ausführbaren Befehle und Voraussetzungen bleiben im [Testkonzept](8-1-testkonzept.md) und [README](../README.md). Nicht ausgeführte Prüfungen werden bei jedem Umsetzungsschritt mit Grund ausgewiesen.
