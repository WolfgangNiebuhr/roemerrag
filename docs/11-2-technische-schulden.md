# 11.2 Technische Schulden

Stand 25.11.2026. Abgeschlossen sind TS-01, TS-02, TS-03, TS-05 für die Importpipeline, TS-06, TS-07, TS-08 und TS-09. TS-04 bleibt das akzeptierte Risiko [R-01](11-1-risiken.md#r-01--manuelle-zuordnung-von-importvarianten--akzeptiertes-risiko). Offen sind TS-10 bis TS-22. Historische Nachweise stehen im [Changelog](../changelog.md). Technische Schulden gelten nur bei ausdrücklicher Markierung als Risiken.

Die [Bausteinsicht](5-bausteinsicht.md) beschreibt die betroffenen Komponenten, die [Laufzeitsicht](6-laufzeitsicht.md) deren Zusammenspiel und das [Testkonzept](8-1-testkonzept.md) die vorhandenen Prüfungen. Das [Error-Handling-Konzept in Kapitel 8.3](8-3-error-handling.md) konkretisiert die offenen Maßnahmen; seine Dokumentation ist kein Implementierungsnachweis. Verzeichnisse namens `k8s` sind ausgeschlossen. Bewertungsmaßstab ist der lokale Podman-Betrieb eines Systems zum Vergleich von RAG-Strategien, kein bereits zugesagter Produktionsbetrieb.

## 11.2.1 Bewertung und Nachweisgrenzen

Die Priorität richtet sich zuerst nach Datenintegrität und Verlässlichkeit von Experimenten, danach nach Betriebsstabilität, Änderbarkeit und Performance.

| Priorität | Bedeutung |
|---|---|
| P1 | Zuerst abbauen: verfälschte Vergleiche, inkonsistente Daten oder bestätigte Fehler im regulären Verarbeitungspfad. |
| P2 | Anschließend abbauen: strukturelle Inkonsistenzen, Betriebsrisiken und fehlende Reproduzierbarkeit. |
| P3 | Nach Stabilisierung beziehungsweise bei entsprechendem Betriebsbedarf bearbeiten. |

Historische Ergebnisse und Grenzen einzelner Analyseläufe stehen im [Changelog](../changelog.md). Aktuelle Befunde und offene Nachweislücken werden weiterhin im jeweiligen Fachkapitel beschrieben.

## 11.2.2 Schuldenregister

### TS-01 – Abweichende Import- und Retrievaldefaults · P1 - Abgeschlossen

- **Stand 21.11.2026:** Abgeschlossen: gemeinsame Defaults in `rag/embedding_config.py` fuer Import3, CLI und RAG; Modell und Set-Kennung sind unabhaengig konfigurierbar.
- **API und Migration:** `embedding_set_id` ersetzt die bisherige Spalte und den Vector-API-Parameter. `embedding` bleibt kompatibler Alias und Antwortfeld, `filter` bleibt RAG-Alias. Konflikte ergeben HTTP 400. Migration mit vorherigem geprueftem Backup ohne neue Vektorberechnung: `scripts/migrate_embedding_set_id.py`; Betrieb und Rueckweg im README.

### TS-02 – Wirkungslose Reranker-Modellwahl · P1 - Abgeschlossen

- **Stand 21.11.2026:** Implementiert: `POST /rerank` waehlt das CrossEncoder-Modell ueber `model`; ohne Parameter gilt `RERANK_MODEL`. Die CLI reicht `--reranker` weiter und zeigt das verwendete Modell aus der Antwort an.
- **Vertrag:** Antworten enthalten `model` und `ranked_documents`. Ungueltige Modellparameter liefern HTTP 400 vor dem Laden; Ladefehler liefern HTTP 503 ohne stillen Fallback. Bei leerer Dokumentliste wird kein Modell geladen. Ein Modell bleibt aktiv; Modellwechsel und Inferenz sind gemeinsam synchronisiert. Beim Wechsel wird das neue Modell zuerst geladen, sodass bei Ladefehlern das vorherige verfuegbar bleibt.

### TS-03 – Requestvalidierung und Fehlerverträge · P1 · Abgeschlossen

- **Stand 21.11.2026:** Frühe gemeinsame Validierung in `rag_common/http_errors.py` für RAG-, Vector- und Reranker-API umgesetzt. Ungültige JSON-Strukturen, Text-/Dokumentfelder, Aliase, Metriken, Trefferzahlen und Vektoren werden vor Modell- und Datenbankzugriffen zurückgewiesen. Vector-Poolinitialisierung erfolgt erst nach der Validierung.
- **Vertrag:** Zentrale Handler liefern RFC-9457-Problemobjekte mit `application/problem+json`, stabiler Typ-URI, HTTP-/Bodystatus, sicherem Fehlertext, Ereignis-URI und Request-ID gemäß [8.3.1–8.3.3](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten). HTTP-Fehler behalten Status und erforderliche Header. API-Clients mit Fehlerfeldzugriffen in Tests und Build-Kontexte sind angepasst; README beschreibt den Schnittstellenbruch.
- **Abgrenzung:** TS-03 umfasst den Eingangs- und Fehlerausgabevertrag. Verbleibende Adapter- und Betriebsaufgaben bleiben unter TS-12 und TS-13 offen; TS-06/TS-07 und die Konsolidierung unter TS-09 sind separat ausgewiesen. Das Querschnittskonzept ist weiterhin nur teilweise umgesetzt.

### TS-04 – Manuelle Zuordnung von Importvarianten · Akzeptiertes Risiko

- **Befund:** `embedding_set_id` ist eine frei gewählte Kennung. Import3 und Retrieval können Modell und Set unabhängig konfigurieren; die Datenbank speichert und prüft keine vollständige Verarbeitungskonfiguration. Eine Set-ID allein belegt daher weder Chunking, Anreicherung und Prompts noch das tatsächlich verwendete Modell und die Normalisierung.
- **Entscheidung vom 21.11.2026:** Keine zusätzliche technische Speicherung oder Absicherung dieser Konfiguration. Stattdessen wird die Zuordnung manuell im [Set-ID-Verzeichnis, arc42-Abschnitt 8.2](8-2-embedding-sets.md) gepflegt. Die [Architekturentscheidung 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026) ersetzt den bisherigen Vorschlag einer persistierten Variantenkonfiguration.
- **Manuelle Behandlung:** Vor einem Import die tatsächlichen Parameter zum Set dokumentieren; bei geänderter Verarbeitung eine neue Set-ID verwenden. Evaluationen nennen die verwendete Set-ID. Unbekannte historische Angaben bleiben ausdrücklich unbekannt; der aktuelle Codezustand ist kein vollständiger Herkunftsnachweis für Bestandsvektoren. Ein erneutes Embedding ist hierfür nicht erforderlich.
- **Akzeptiertes Restrisiko:** Eine falsche Kennung oder veraltete Dokumentation kann unterschiedliche Verarbeitungen unter derselben Set-ID vermischen. Gleiche `(chunk_id, embedding_set_id)` können überschrieben werden; Vergleiche werden dadurch schwer erklärbar oder nicht wiederholbar. Das Verzeichnis unterstützt die Nachvollziehbarkeit, verhindert solche Fehler aber nicht technisch. Es besteht kein offener Implementierungsauftrag für die ursprünglich vorgeschlagene Konfigurationspersistenz. Modellrevisionen und Buildstände behandelt TS-15.

### TS-05 – Chunk-Identität und Importabschluss · Abgeschlossen für Ingest.pipeline

- **Entscheidung.** Bestätigte Chunks bleiben bei einem Abbruch in der Datenbank. Der vorübergehend gemischte Stand ist im Sinne von Eventual Consistency akzeptiert.
- **Wiederaufnahme.** Beim Abbruch zeigt die Pipeline die erste unbestätigte Chunknummer an. `--start` startet ab einer vorgegebenen Nummer und lässt niedrigere Nummern unangetastet.
- **Bereinigung.** Ein erfolgreicher Lauf entfernt überzählige kanonische IDs des Dokuments im Zielset. Erste-Punkt-IDs werden nach gesicherter Zuordnung manuell bereinigt. Die Eindeutigkeit des Dateistamms pro Set bleibt das akzeptierte Risiko [R-02](11-1-risiken.md#r-02-dateistamm-als-dokumentidentitaet).
- **Geltungsbereich.** Die Umsetzung betrifft `Ingest.pipeline`. Ablauf und Eingaben stehen im [Importkonzept](8-4-importkonzept.md).

### TS-06 – Nebenläufigkeit und Schreibsemantik der Vector-API · P1 - Abgeschlossen

- **Status:** Abgeschlossen; isolierte Podman-Abnahme und alle optionalen Integrationstests erfolgreich; im laufenden Vector-API-Container ausgerollt (22.11.2026, Nachweise im Changelog).
- **Umsetzung:** Atomare Upserts auf `(chunk_id, embedding_set_id)` erhalten bestehende IDs. `ThreadedConnectionPool` begrenzt die parallelen Verbindungen auf zehn; Erschoepfung ergibt 503 ohne automatische Wiederholung.
- **Transaktionen:** Zentraler Context Manager schliesst auch Lesezugriffe mit Commit ab, rollt Fehler zurueck und verwirft defekte oder nicht bereinigbare Verbindungen. Rueckgabefehler verdecken den urspruenglichen Fehler nicht.
- **Pruefung:** Unit-Tests fuer Commit, Rollback, Bereinigungsfehler und Poolerschoepfung; isolierte Podman-Tests fuer parallele Upserts und stabile IDs. Pruefnachweis im Changelog.

### TS-07 - Datenbankinitialisierung und Readiness - P2 - Abgeschlossen

- **Umsetzung:** Die Vector-API trennt `/health/live` ohne DB-Zugriff und `/health/ready` mit Schema-Pruefung. Nichtbereitschaft liefert 503 Problem Details. Initialisierung erfolgt bei Bedarf; fehlgeschlagene Versuche werden durch spaetere Requests wiederholt. Parallele Requests warten nicht auf den Initialisierungslock. Verbindungs-, Statement- und Lock-Wartezeit sind jeweils auf drei Sekunden begrenzt; kein Gesamtbudget und keine automatischen Schreib-Retries.
- **Abnahme:** 174 Unit-Tests und vier isolierte Vector-Integrationstests bestanden. Ein eigener Pod ohne regulaere Volumes prueft API-Start vor PostgreSQL, 503 bis zum Datenbankstart, anschliessende Bereitschaft sowie Ausfall und Wiederanlauf der Datenbank bei unveraendertem API-Container ohne Neustart. Historische und aktuelle Pruefergebnisse stehen im [Changelog](../changelog.md).

### TS-08 – Kontext- und Metrikverarbeitung · P1 · Abgeschlossen

- **Stand 22.11.2026:** Die RAG-API validiert Retrievalantworten als Liste von Objekten mit nichtleerer String-Chunk-ID und textuellem `chunktext`. Ungültiges JSON oder verletzte Trefferverträge ergeben RFC-9457-Problemantworten mit HTTP 502 und Verarbeitungsschritt `retrieval`; fehlerhafte Treffer werden nicht still übersprungen. Retrievalausfälle bleiben technische Fehler.
- **Fachlicher Vertrag:** Leere Trefferlisten und ausschließlich leere/Whitespace-Texte liefern HTTP 200 mit `status: no_context`, `chunks: []`, `metrics: null` und kontrollierter Ablehnungsantwort ohne Generierung. Bei gemischten Treffern werden leere Texte und ihre IDs nicht in den Kontext übernommen. Erfolgreiche Antworten mit Kontext behalten ihre bisherige Struktur.
- **Metriken:** Fehlende, negative, nichtnumerische oder nicht endliche Werte ergeben `null`, ohne eine vorhandene Modellantwort zu verlieren. Tokenzahlen erfordern nichtnegative ganze Zahlen ohne Booleans. Laufzeiten werden weiterhin in Sekunden ausgegeben; bei fehlender oder nullwertiger `eval_duration` ist `answer_rate` null. Gemessene Nullwerte bleiben erhalten; null Tokens bei positiver Dauer ergeben Rate 0.
- **Abschlussnachweis:** [rag_common/rag_results.py](../rag_common/rag_results.py) und [RAG-Vertragstests](../tests/unit/test_rag_components.py) sichern TS-08 ab; aktuelle Unit-Suite erfolgreich, historische E2E-/Live-Nachweise im Changelog. timings und der Generierungsdauer-Alias sind additive Erweiterungen, kein offener TS-08-Rest.
- Der Umgang mit fehlendem Chunktext an der Vector-RAG-Grenze ist unter TS-20 erfasst.

### TS-09 - Duplizierte Verarbeitung und Konfiguration - Abgeschlossen

- **Umsetzung:** interact.py ist ein reiner RAG-HTTP-Client. `/process` uebernimmt Embedding, Retrieval, optionales Reranking und Generierung. Modellwahl, Metrik, Set und Treffergrenzen sind explizite Parameter. CLI und API verwenden gemma4:e4b als gemeinsamen Antwortmodellstandard; bestehende API-Clients erhalten ohne top_k weiterhin kein Reranking. Urspruengliche und ausgewaehlte Treffer werden getrennt zurueckgegeben.
- **Gemeinsamer Kern:** analyze.py verwendet Providerfunktionen und Prompt aus rag/app.py statt eigener Implementierungen. Import3 hat begrenzte konfigurierbare Verbindungs-/Lesezeitlimits. Historische, nicht unterstuetzte Varianten verbleiben unter TS-14.
- **Fehler und Zeitlimits:** Gemeinsame RAG-Transportfunktion mit konfigurierbaren Zeitlimits, Request-ID-Weitergabe, Restbudget und maximal einem Retry mit kurzer Zufallswartezeit bei Transportfehlern sicher wiederholbarer Operationen. Generierung und Writes werden nicht wiederholt. Erkannte Vertragsverletzungen in Providerantworten ergeben 502, Ausfälle 503. Socket-Aufrufe werden nicht hart unterbrochen; das Budget wird vor/nach Aufrufen geprueft. Offene Vertragslücken stehen unter TS-11, TS-19 und TS-20. Importabschluss ist für die Pipeline unter TS-05 umgesetzt, weitergehende Betriebsabsicherung TS-13.
- **Betrieb:** Neues RAG-Image am 22.11.2026 ausgerollt; CLI mit und ohne Reranking am laufenden System erfolgreich geprueft. Nachweis im Changelog.
- **Pruefung:** Vertragstests pruefen CLI-Delegation, gleiche Verarbeitung bei expliziter Konfiguration, Reranking-Zuordnung, leeren Kontext, Modellwahl, Providervertraege und Retry-/Budgetgrenzen. Isolierte Tests pruefen echte RAG-Verarbeitung mit und ohne Reranking. Aktueller Pruefnachweis im [Changelog](../changelog.md).

### TS-10 – Inkonsistentes Ressourcen- und Begriffsmodell · P2 - Offen

- **Befund:** [Vector](../Vector/app.py) verwendet `/vectors` zum Schreiben, `/chunks/<id>` zum Lesen und `/chunks` zum Löschen; `/chunks` zählt Zeilen. Die Benennungen sind inzwischen präzisiert: `embedding_set_id` bezeichnet das Set, `chunktext` den Quelltext (zuvor `metadata`, Migration vom 21.11.2026). Lesen ohne Variantenfilter nutzt weiterhin `LIMIT 1` ohne eindeutige Auswahl; `/find` liefert IDs ohne Variantenkennung. TS-10 bleibt deshalb offen.
- **Auswirkung:** Mehrdeutige Identitäten und überraschende Clientsemantik, sobald mehrere Varianten existieren.
- **Abbau und Abschluss:** Ressourcen, Schlüssel und Feldbegriffe verbindlich beschreiben. Mehrdeutige Einzelabfragen entweder zurückweisen oder als Sammlung beantworten. Ein Umstellungsplan erhält bestehende Clients oder kennzeichnet einen Schnittstellenbruch. Tests decken dieselbe Chunk-ID in zwei Varianten ab.

### TS-11 – Widersprüchlicher und datenbanknaher Vektorvertrag · P2 - Offen

- **Bereits erledigt:** [rag_common/http_errors.py](../rag_common/http_errors.py), vector/search_options, prueft vor SQL auf 1024 endliche Zahlen, erlaubt Listen und JSON-Listenstrings und verbietet Nullnorm bei Cosine. chunktext ist String/null. [RAG](../rag/app.py), generate_embedding, prueft Form, Zahlen und endliche positive Norm; verletzte Providervertraege ergeben 502. Diese Validierung nicht neu einplanen.
- **Restbefund:** Vector-Docstrings beschreiben pgvector-Strings; Suchantworten liefern Vektoren ohne Diagnose-Opt-in in datenbanknaher Darstellung. analyze.py verwendet json.loads; init.sql bleibt VECTOR(1024). generate_embedding prueft nicht die erwartete Dimension; endliche falsch dimensionierte Providervektoren scheitern erst beim Retrieval. Import3 normalisiert ohne gleichwertige Norm-/Endlichkeitspruefung.
- Im simulierten Fehlerfall erreichte ein dreidimensionales Ollama-Embedding die Vector-API. Diese antwortete vor dem Datenbankzugriff mit HTTP 400. Nach außen meldete die RAG-API HTTP 503 im Schritt `retrieval` und erschwerte damit die Zuordnung zum Embedding-Provider. [RAG-Adapter](../rag/app.py), [Vector-Validierung](../rag_common/http_errors.py)
- **Abbau und Abschluss:** Kanonischen JSON-Ausgabevertrag und Vektor-Opt-in festlegen, Analyseclient/Docstrings anpassen. Providerdimension vor Retrieval mit 502 absichern und Importvalidierung ergaenzen. Vorhandene Eingangsvalidierung erhalten. Andere Dimensionen sind eine gesonderte Architekturentscheidung, keine Voraussetzung dieser Bereinigung.

### TS-12 – Unvollständige Adapter und ungenutzte Konfiguration · P2 - Offen

- **Befund:** [gateway.py](../Ingest/utils/gateway.py) gibt rohe `requests.Response`-Objekte zurück; [keywords.py](../Ingest/utils/keywords.py) kennt weiterhin die jeweiligen Providerformate. Der Gatewayparameter `chunk` wird nicht genutzt. Import3 verwirft die gelieferten Metriken und die Frage. In [RAG](../rag/app.py) definierte Ollama-Endpunktkonstanten steuern die echten Aufrufe nicht; diese verwenden den Resolver. Tests orientieren sich teilweise an den Konstanten. Auch `QUERY` und `NUM_RESULTS` sind dort ungenutzt.
- **Auswirkung:** Die scheinbar gemeinsame Abstraktion kapselt Providerdetails nicht; Änderungen und Tests können sich auf wirkungslose Konfiguration beziehen.
- **Teilweise umgesetzt (24.11.2026):** Die Pipeline nutzt denselben Keyword-Prompt wie Import3, validiert Keyword- und Embeddingantworten, setzt explizite Timeouts und protokolliert keine Providerantworten. Altes Gateway und gemeinsamer Provider-Ergebnistyp bleiben offen.
- **Abbau und Abschluss:** Einen kleinen gemeinsamen Ergebnistyp für Keyword-Provider einführen. Unbenutzte Argumente und Konstanten entfernen; benötigte Versuchsdaten strukturiert speichern. Tests prüfen die tatsächlich aufgelösten Adressen und das gemeinsame Providerergebnis.
- **Konkretisierung durch Kapitel 8.3:** Adapter übersetzen technische Fehler und verletzte Antwortverträge gemäß [8.3.1–8.3.3](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten) in gemeinsame Anwendungsfehler unter Erhalt der Ursache. Tests sichern die Übersetzung ab; rohe Providerantworten nicht als öffentliche Fehlertexte weiterreichen.

- **Aktuelle Abgrenzung:** RAG-Transportadapter kapseln bereits Timeout/Verbindungsfehler als 503, pruefen Providerantworten und reichen Request-IDs weiter; /evaluate nutzt dieselben Funktionen. Offen bleiben Import-/Keyword-Adapter, sichere Logs und wirkungslose Konstanten. Der Ollama-Resolver scheitert vor upstream_post mit RuntimeError (generische 500); seine Probes werden nicht mit dem Restbudget begrenzt. Socket-Zeitlimits erlauben keinen harten Abbruch. Diese Grenzen gezielt pruefen, keinen zweiten RAG-Kern bauen.

### TS-13 – Widersprüchlicher Modelllade- und Health-Lebenszyklus · P2 - Offen

- **Befund:** Seit TS-02 werden Modellladen und Inferenz synchronisiert; ungueltige Rerank-Anfragen loesen kein Modellladen mehr aus. `/health` laedt bei noch ungeladenem Dienst weiterhin das Defaultmodell und wartet auf laufende Modelloperationen. Getrennte Liveness-/Readiness-Endpunkte fehlen.
- **Auswirkung:** Health-Aufrufe koennen durch Modellinitialisierung oder Inferenz blockieren; Prozesslebendigkeit und Modellbereitschaft sind nicht getrennt erkennbar.
- **Abbau und Abschluss:** Getrennte Liveness-/Readiness-Zustaende mit Fehler-, Zustands- und Neustarttests einfuehren. Die Synchronisierung ist mit TS-02 umgesetzt; TS-13 bleibt fuer den Health-Vertrag offen.
- **Konkretisierung durch Kapitel 8.3:** Health-Vertrag gemäß [8.3.7](8-3-error-handling.md#837-diagnose-und-betriebszustand) umsetzen: Liveness ohne Modellinitialisierung, zeitlich begrenzte Readiness und 503 mit Problem Details bei fehlender Bereitschaft. Tests berücksichtigen laufendes Laden und Inferenz.

### TS-14 – Fehlerhafte Analyse und unklare Alt-Einstiegspunkte · P1 - Offen

- **Teilweise umgesetzt (24.11.2026):** README und Kapitel 8.4 dokumentieren den gemeinsamen Import und benennen Import3 als separaten Einstieg. Die fehlerhafte alte Importvariante wurde entfernt. Der Goldtext und die Einordnung der uebrigen Alt-Einstiegspunkte bleiben offen.

- **Befund:** In [analyze.py](../analyze.py) umfasst `GOLDCHUNK` nur die Keyword-Zeile; die folgenden Stringliterale sind eigenständige Ausdrücke. Dies wurde per AST-Auswertung bestätigt. Der [lokale Reranker](../reranker/reranker-local.py) dupliziert Serverlogik mit anderem Standardmodell.
- **Auswirkung:** Irreführende Ähnlichkeitsmessungen und erst im Fehlerpfad sichtbare Defekte; unklarer Wartungsumfang.
- **Abbau und Abschluss:** Den Goldtext korrigieren und durch einen gezielten Regressionstest sichern. Unterstützte Einstiegspunkte festlegen; andere ausdrücklich archivieren oder entfernen. Für unterstützte Varianten Smoke- und Fehlerpfadtests vorsehen. P1 betrifft die Messkorrektheit; die Providerkonsolidierung aus TS-09 ist bereits umgesetzt.

- **Codepruefung 22.11.2026:** AST bestaetigt weiterhin GOLDCHUNK mit nur 46 Zeichen und 14 eigenstaendigen Stringausdruecken. Providerkonsolidierung aus TS-09 ist inzwischen erledigt; Goldtext und defekte Alt-Einstiege bleiben davon unberuehrt. /evaluate liefert die technische Schrittzerlegung, aber noch keinen Goldvergleich oder geprueften Goldkorpus.

### TS-15 – Nicht reproduzierbare Builds und Testumgebungen · P2 - Offen

- **Bereits erledigt:** [Vector/migrations](../Vector/migrations) enthaelt 001_embedding_set_id.sql und 002_chunktext.sql. [Migrationsskript](../scripts/migrate_embedding_set_id.py) erstellt vor Ausfuehrung einen Dump und prueft ihn mit pg_restore --list. [Integrationstests](../tests/podman/test_embedding_migration.py) pruefen alte Teststruktur, Wiederholbarkeit, Daten-/Constraint-Erhalt und Backup-Wiederherstellung. Die bisherige Aussage, ein versionierter Migrationspfad fehle, ist ueberholt.
- **Restbefund:** Pakete/Basisimages nicht vollstaendig fixiert; Vector/Dockerfile baut pgvector vom aktuellen Git-Stand. Modellrevisionen sind nicht durchgaengig erfasst. Einzelne Migrationen werden explizit ausgewaehlt; allgemeine Versionserkennung und automatische Reihenfolge fehlen.
- In den dokumentierten Testabhängigkeiten fehlt SciPy. Ein Unit-Test importiert `analyze.py` und benötigt dadurch `scipy.spatial.distance`. In einer Umgebung ohne zusätzlich installiertes SciPy schlägt der Import fehl. [Testabhängigkeiten](../tests/podman/requirements.txt), [Unit-Test](../tests/unit/test_rag_components.py), [Analyse](../analyze.py)
- **Abbau und Abschluss:** Abhaengigkeiten, Basisimages, pgvector-Commit und Modellrevisionen nachvollziehbar fixieren. Vor weiteren Schemaaenderungen den vorhandenen Backup-/Migrationspfad erweitern und testen; bei wachsender Anzahl Versionserkennung/Reihenfolge absichern. Vorhandene Migrationen nicht neu implementieren; bitgleiche Modellantworten bleiben kein Abschlusskriterium.
- Die dokumentierte Testinstallation muss alle benötigten Abhängigkeiten bereitstellen. Die Unit-Suite in einer frisch eingerichteten Umgebung mit diesen Abhängigkeiten prüfen.

### TS-16 – Indexstrategie passt nicht zu allen Suchmetriken · P3 - Offen

- **Befund:** [init.sql](../Vector/init.sql) erstellt nur einen HNSW-Index mit `vector_l2_ops`; [interact.py](../interact.py) sucht standardmäßig mit Cosinus. Dieser Index unterstützt den Cosinus-Operator nicht.
- Für einheitsnormalisierte Anfrage- und Korpusvektoren ergeben L2 und Cosinus mathematisch dieselbe exakte Rangfolge. Unterschiedliche Zugriffspfade wie eine approximative Indexsuche können Treffer und Laufzeiten beeinflussen. Ein konkretes Laufzeitproblem wurde nicht gemessen.
- **Abbau und Abschluss:** Repräsentative Datenmengen und gefilterte sowie ungefilterte Suchpläne messen. Treffer gegen eine exakte Referenzsuche abgleichen. Metrikspezifische Indizes oder eine begründete gemeinsame Suchstrategie wählen. Indexänderungen über TS-15 migrieren; Laufzeit und Retrievalqualität gemeinsam dokumentieren.

### TS-17 – Testabdeckung umgeht relevante Verarbeitungspfade · P1, begleitend - Offen

- **Pipeline (24.11.2026):** [Unit-Tests](../tests/unit/test_import_pipeline.py) pruefen rekursive Grenzen, Artefaktwiederverwendung, Textgleichheit, Konfiguration und Fehlerabbruch. Die [Integration](../tests/podman/test_import_pipeline_integration.py) deckt Keywords, Embedding, Speicherung und Ruecksuche ab.
- **Bereits erledigt:** [Chunkingtests](../tests/unit/test_chunking.py) pruefen echte Mehrfachsplits mit Grenzen und Overlap. [Importintegration](../tests/podman/test_import3_integration.py) verwendet process_file inklusive echter Keywords, Embeddings, Speicherung und Ruecksuche im isolierten Set. [Vectorintegration](../tests/podman/test_vector_api.py) prueft parallele Upserts, stabile IDs, SQL-Rollback/Poolwiederverwendung sowie verzoegerten DB-Start und Erholung ohne API-Neustart. Eingangsvalidierung, Problem Details, no_context, Reranking und Metriken sind getestet. [RAG-E2E](../tests/podman/test_rag_e2e.py) prueft echte Verarbeitung mit/ohne Reranking und die Evaluationskette. Ein separat vorbereiteter RAG-E2E-Test ist neben der eigenen Importintegration keine pauschale Import-Abdeckungsluecke mehr.
- **Restumfang:** Goldtextkorrektheit/Alt-Einstiege (TS-14), Reranker-Health bei Laden/Inferenz (TS-13), Persistenz nach DB-Neuerstellung mit demselben Testvolume sowie repraesentative Last-/Suchplannachweise bleiben offen. Der TS-07-Test mit tmpfs belegt Erholung, keine Volume-Persistenz.
- Fuer TS-19 und TS-20 fehlen gezielte Regressionstests fuer unvollstaendige Reranker-Ergebnisse und gemischte Treffer mit fehlendem Text. Ein Pipeline-Regressionstest deckt lange Passagen ohne passende Trennzeichen ab (TS-21).
- **Abbau und Abschluss:** Resttests jeweils mit TS-10/11/12/13/14/15/16/19/20/21 liefern; deterministische und echte Modelltests getrennt halten. Fuer geplante Qualitaetsmessungen Gold-Antworten, erwartete Treffer, Bewertungsmetriken und Versuchsmatrizen definieren. /evaluate stellt bislang die technische Schnittstelle bereit, keinen Qualitaetsnachweis. Manuell genutzte Daten und Volumes erhalten.

### TS-18 – Experimenteller Betriebsrahmen · P3, bedarfsabhängig - Offen

- **Befund:** Die APIs starten Flask-Entwicklungsserver; Authentifizierung fehlt, Beispiel-DB-Zugangsdaten sind fest vorbelegt. Ein einheitliches Readiness-Konzept fehlt. Siehe [Startanleitung](../README.md), [Vector](../Vector/app.py), [RAG](../rag/app.py) und [Reranker](../reranker/app.py).
- **Auswirkung:** Der dokumentierte lokale Experimentbetrieb ist nicht ohne weitere Maßnahmen auf Mehrbenutzer- oder exponierten Dauerbetrieb übertragbar.
- **Abbau und Abschluss:** Vor einer solchen Nutzung Betriebsgrenzen festlegen, geeigneten Serverbetrieb, Zugangskontrolle, externe Geheimniskonfiguration und Readiness umsetzen und prüfen. Bei unverändert lokalem Einsatz bleibt dies eine dokumentierte Einschränkung. Bei geplanter Exposition steigt die Priorität vor deren Freigabe auf P1.
- **Konkretisierung durch Kapitel 8.3:** Readiness und öffentliche Fehlerausgaben folgen [8.3.7](8-3-error-handling.md#837-diagnose-und-betriebszustand). Die lokale Betriebsabsicherung unter TS-07/TS-13 hängt nicht erst von einer späteren Exposition ab.

- **Aktuelle Abgrenzung:** Vector hat getrennte Liveness/Readiness (TS-07). RAG hat keine Health-Endpunkte; Reranker-/health kann weiterhin beim Modellzugriff blockieren. Fehlende Authentifizierung, Entwicklungsserver und Beispielzugangsdaten sind unveraendert. Die lokalen Health-Restarbeiten nicht erst bei Exposition bearbeiten.

### TS-19 – Stiller Trefferverlust beim Reranking · P1 - Offen

- Der Reranker koppelt Dokumente und Modell-Scores per `zip`. Bei zu wenigen Scores entfallen Dokumente aus der HTTP-200-Antwort. Die RAG-API prüft die vorhandenen Indizes auf Gültigkeit und Eindeutigkeit. Die Vollständigkeit der Zuordnung bleibt ungeprüft. [Reranker](../reranker/app.py), [RAG-Adapter](../rag/app.py)
- Im Test mit zwei gültigen Dokumenten und einer simulierten leeren Scoreliste meldeten `/process` und `/evaluate/rerank` HTTP 200 mit `no_context`. Bei nur einem Score blieb der Trefferverlust ebenfalls ungemeldet. `/process` akzeptierte im Test einen nicht endlichen Score. `/evaluate/rerank` wies ihn bei Auswahl des Treffers mit HTTP 502 zurück.
- Für jedes übergebene Dokument muss genau eine Zuordnung mit endlichem Score vorliegen. Beide RAG-Pfade müssen gegen unvollständige oder ungültige Providerergebnisse abgesichert sein, einschließlich HTTP 502 mit Schritt `reranking` bei Vertragsverletzungen. Tests prüfen fehlende, überzählige und nicht endliche Scores, ungültige Indizes und den legitimen Fall ohne Eingabedokumente.

### TS-20 – Widersprüchlicher Vertrag für fehlenden Chunktext · P1 - Offen

- Die Vector-API akzeptiert `chunktext: null` oder ein fehlendes Feld und gibt `null` in Suchtreffern zurück. Der RAG-Adapter verlangt für jeden Treffer einen String. In einem simulierten Abruf mit einem gültigen Text und einem Treffer mit `null` endete die gesamte RAG-Abfrage mit HTTP 502 im Schritt `retrieval`. [Vector-Schema](../Vector/init.sql), [Eingangsvalidierung](../rag_common/http_errors.py), [RAG-Trefferprüfung](../rag_common/rag_results.py)
- Schreiben, Suche und Kontextbildung brauchen einen gemeinsamen Vertrag für fehlende Texte mit einer Regel für vorhandene Datensätze. Gültige Nachbartreffer müssen nutzbar bleiben. Vertragsprüfungen sichern gemischte Treffer, rein leeren Kontext und weiterhin ungültige Providerantworten ab.

### TS-21 – Überschrittene Chunkgröße bei langen Passagen · P2 - Offen

- Die Pipeline begrenzt lange Passagen standardmaessig durch einen Zeichen-Fallback. Der folgende Befund gilt fuer Import3 und die Pipeline-Beispielkonfiguration `snowflake-arctic-embed-v2.json` mit deaktiviertem Fallback.
- Der Splitter verwendet Absatz- und Satztrennzeichen ohne Fallback für lange Passagen. Bei einer Konfiguration von 1.000 Zeichen und 150 Zeichen Überlappung waren im lesenden Durchlauf über die sechs Beispieldateien 34 von 10.373 Chunks länger als 1.000 Zeichen. Der größte Chunk hatte 1.790 Zeichen. [Chunking](../Ingest/utils/chunking.py), [Import3-Standardwerte](../Ingest/import3.py)
- Versuche zur Chunkgröße brauchen einen expliziten Größenvertrag pro Strategie und Angaben zu den tatsächlich erzeugten Längen. Für Strategien mit garantierter Obergrenze einen Fallback und Regressionstests mit langen Passagen ohne Trennzeichen vorsehen. Ändert sich die Verarbeitung, die neue Variante gemäß R-01 einer eigenen Set-ID zuordnen.

### TS-22 – Veraltete Angaben in der Bausteinsicht · P2 - Offen

- Die Bausteinsicht nennt noch `snowflake-arctic-embed2` als RAG-Standardfilter und beschreibt das Schreiben als Löschen und Einfügen. Der Code verwendet standardmäßig das Set `snowflake-arctic-embed2-v2` und einen atomaren Upsert. Die Übersicht führt die alte Abweichung der Defaults noch als offenen Punkt. Die Ergänzung zu TS-03 bezeichnet die Transaktions- und Poolnebenläufigkeit weiterhin als offen, obwohl TS-06 abgeschlossen ist. [Bausteinsicht](5-bausteinsicht.md), [Set-Konfiguration](../rag/embedding_config.py), [Vector-API](../Vector/app.py)
- Die Bausteinsicht soll Default, Schreibsemantik und Status der abgeschlossenen Arbeiten konsistent mit Code, README und Register wiedergeben. Das verhindert unnötige Filterwechsel und Fehlannahmen über stabile IDs bei wiederholten Schreibzugriffen.

## 11.2.3 Priorisierte Reihenfolge für den Abbau

Nur offene Restarbeiten werden eingeplant. Abgeschlossene TS-01/02/03/06/07/08/09 nicht erneut umsetzen. TS-17 begleitet die jeweilige Korrektur mit Tests; Codepruefung ersetzt keine Last- oder Betriebsabnahme.

| Reihenfolge | Offenes Paket | Freigabekriterium | Abhaengigkeit |
|---|---|---|---|
| 2 | **Vollständige und nutzbare Treffer (TS-19/20, P1)** | Vollständige Reranking-Zuordnung und einheitliche Behandlung fehlender Texte. Vertragstests decken fehlerhafte und leere Ergebnisse ab. | Parallel zum Import bearbeitbar. Für TS-20 vorhandene Datensätze und den Vertrag der Vector-API berücksichtigen. |
| 3 | **Messkorrektheit (TS-14, P1)** | Vollständiger und regressionstestgesicherter Goldtext. Unterstützte Einstiege benannt, Altvarianten korrigiert oder archiviert. | Kann parallel beginnen. Gemeinsamer Providerkern und `/evaluate` sind vorhanden. |
| 4 | **Chunkgrößenvertrag (TS-21, P2)** | Größenverhalten explizit beschrieben und für lange, schwer teilbare Texte getestet. | Vor Vergleichen der Chunkgröße abschließen. Bei geänderter Verarbeitung eine neue Set-ID verwenden. |
| 5 | **Identitäts- und Vektorverträge (TS-10/11, P2)** | Eindeutige Einzelchunkantworten, Set-Identität bei ID-Suche, kanonische Vektorausgabe mit Opt-in, frühe Prüfung der Providerdimension und Importvektoren. | API-Umstellung explizit planen. Änderungen am Textvertrag mit TS-20 abstimmen. |
| 6 | **Health (TS-13, P2, und RAG-Rest aus TS-18)** | Reranker-Liveness ohne Modellladen, begrenzte Readiness bei Inferenz und Laden, RAG-Bereitschaft explizit und getestet. | Unabhängig vorziehbar. Vector-Lebenszyklus aus TS-07 erhalten. |
| 7 | **Adapterreste (TS-12, P2)** | Gemeinsames Keyword-Ergebnis, wirksame Konfiguration, sichere Logs, getestete Resolverfehler und Restbudgetgrenzen. | Der gemeinsame RAG-Kern kann weiterverwendet werden. |
| parallel | **Reproduzierbarkeit (TS-15, P2)** | Paket-, Image-, pgvector- und Modellrevisionen festgehalten, Testinstallation aus frischer Umgebung geprüft, Backup- und Migrationstests bei Schemaänderungen erweitert. | Vor belastbaren Build-Vergleichen und weiteren Schemamigrationen. |
| parallel | **Bausteinsicht (TS-22, P2)** | Set-Default, Upsert und Status der betroffenen Einträge entsprechen Code, README und Register. | Dokumentationskorrektur anhand des aktuellen Implementierungsstands. |
| danach | **Suchpläne und Performance (TS-16, P3)** | Repräsentative L2- und Cosinus-Pläne mit exakter Referenzsuche, Datenmenge, Set und Build dokumentiert. Begründete Indexwahl migriert. | Stabile Datenidentität und dokumentierte Builds. Persistenz- und Lastnachweise separat führen. |
| bedarfsabhaengig | **Erweiterter Betrieb: TS-18 (P3, bei Exposition P1)** | Serverbetrieb, Zugangskontrolle und externe Geheimnisse passend zum realen Einsatz getestet. | Vor Mehrbenutzer-/exponiertem Betrieb; lokale Health-Arbeit nicht aufschieben. |

Die geplante Gold-Antwort-Evaluation baut auf /evaluate auf: Goldkorpus, erwartete Retrievaltreffer, Antwortbewertung und Versuchskonfiguration muessen noch definiert werden. Erfolgreiche Live-Verkettung ist kein Qualitaetsnachweis. Fuer R-01 gilt weiter die manuelle Set-Zuordnung aus Abschnitt 8.2; unbekannte Herkunft bleibt unbekannt. Bestandsdatenwechsel nach Kapitel 8.4 durchführen.

## 11.2.4 Verifikation und Fortschreibung

Zu jedem umgesetzten Paket werden betroffene Registereinträge mit Status, Implementierungsreferenz und Verweis auf die Prüfnachweise im [Changelog](../changelog.md) aktualisiert. Ein Eintrag ist erst erledigt, wenn seine Abschlusskriterien erfüllt und die betroffenen Architektur- beziehungsweise Schnittstellenbeschreibungen angepasst sind. Offene Architekturentscheidungen sind mit der Umsetzung in arc42-Abschnitt 9 zu dokumentieren; die Fehlerverträge und Abnahmekriterien aus [Kapitel 8.3](8-3-error-handling.md) bilden den dokumentierten Zielzustand und bleiben bis zum Implementierungs- und Prüfnachweis offen.

| Änderung | Erforderlicher Nachweis |
|---|---|
| Validierung, Metriken, Konfiguration, Adapter | Betroffene containerfreie Unit- und Vertragstests. |
| SQL, Pool, Datenidentität, Migration | Isolierte Podman-Integration einschließlich Parallelität, Wiederanlauf oder Migration entsprechend der Änderung. |
| Import und RAG-Zusammenspiel | Test des tatsächlichen unterstützten Importpfads und E2E mit echten Embedding-/Antwortmodellen; Keyword-Schritt gesondert absichern. |
| Indexstrategie | Schema-/Indexprüfung, repräsentative Suchpläne und Messungen mit dokumentierter Datenmenge und Variantenkonfiguration. |
| Modellinitialisierung und Betrieb | Fehler-, Zustands- und Neustarttests; Last- beziehungsweise Zugangstests entsprechend dem Einsatz. |

Die ausführbaren Befehle und Voraussetzungen bleiben im [Testkonzept](8-1-testkonzept.md) und [README](../README.md). Nicht ausgeführte Prüfungen werden bei jedem Umsetzungsschritt mit Grund ausgewiesen.

Historische Aenderungs- und Pruefnachweise: [Changelog](../changelog.md).

Das [Importkonzept in Kapitel 8.4](8-4-importkonzept.md) konkretisiert den gemeinsamen Importablauf, Strategien, Artefakte und den Importabschluss aus TS-05 sowie die Restarbeiten aus TS-12/14/17. Es ist ein Zielkonzept und kein Abschlussnachweis; R-01 und der vorhandene Abbauplan bleiben massgeblich.
