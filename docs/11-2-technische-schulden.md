# 11.2 Technische Schulden

Stand: 22.11.2026, nach Code- und Testbestandspruefung. Abgeschlossen: TS-01, TS-02, TS-03, TS-06, TS-07, TS-08 und TS-09. TS-04 bleibt das akzeptierte Risiko [R-01](11-1-risiken.md#r-01--manuelle-zuordnung-von-importvarianten--akzeptiertes-risiko). Offen: TS-05 und TS-10 bis TS-18, jeweils nur mit dem unten ausgewiesenen Restumfang. Historische Nachweise bleiben im [Changelog](../changelog.md). Technische Schulden gelten nur bei ausdruecklicher Markierung als Risiken.

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
- **Abgrenzung:** TS-03 umfasst den Eingangs- und Fehlerausgabevertrag. Verbleibende Adapter- und Betriebsaufgaben sowie Importabschluss bleiben unter TS-05, TS-12 und TS-13 offen; TS-06/TS-07 und die Konsolidierung unter TS-09 sind separat ausgewiesen. Das Querschnittskonzept ist weiterhin nur teilweise umgesetzt.

### TS-04 – Manuelle Zuordnung von Importvarianten · Akzeptiertes Risiko

- **Befund:** `embedding_set_id` ist eine frei gewählte Kennung. Import3 und Retrieval können Modell und Set unabhängig konfigurieren; die Datenbank speichert und prüft keine vollständige Verarbeitungskonfiguration. Eine Set-ID allein belegt daher weder Chunking, Anreicherung und Prompts noch das tatsächlich verwendete Modell und die Normalisierung.
- **Entscheidung vom 21.11.2026:** Keine zusätzliche technische Speicherung oder Absicherung dieser Konfiguration. Stattdessen wird die Zuordnung manuell im [Set-ID-Verzeichnis, arc42-Abschnitt 8.2](8-2-embedding-sets.md) gepflegt. Die [Architekturentscheidung 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026) ersetzt den bisherigen Vorschlag einer persistierten Variantenkonfiguration.
- **Manuelle Behandlung:** Vor einem Import die tatsächlichen Parameter zum Set dokumentieren; bei geänderter Verarbeitung eine neue Set-ID verwenden. Evaluationen nennen die verwendete Set-ID. Unbekannte historische Angaben bleiben ausdrücklich unbekannt; der aktuelle Codezustand ist kein vollständiger Herkunftsnachweis für Bestandsvektoren. Ein erneutes Embedding ist hierfür nicht erforderlich.
- **Akzeptiertes Restrisiko:** Eine falsche Kennung oder veraltete Dokumentation kann unterschiedliche Verarbeitungen unter derselben Set-ID vermischen. Gleiche `(chunk_id, embedding_set_id)` können überschrieben werden; Vergleiche werden dadurch schwer erklärbar oder nicht wiederholbar. Das Verzeichnis unterstützt die Nachvollziehbarkeit, verhindert solche Fehler aber nicht technisch. Es besteht kein offener Implementierungsauftrag für die ursprünglich vorgeschlagene Konfigurationspersistenz. Importlaufprobleme bleiben TS-05; Modellrevisionen und Buildstände behandelt TS-15.

### TS-05 – Kollidierende Chunk-IDs und unvollständige Wiederholungsimporte · P1 - Offen

- **Befund:** [Import3](../Ingest/import3.py), `process_file`, erzeugt IDs aus `basename.split('.')[0]` und laufender Nummer. `rom.band1.txt` und `rom.band2.txt` kollidieren innerhalb derselben Variante. Kürzere Wiederholungsimporte entfernen keine alten überzähligen Chunks. Chunkfehler werden protokolliert; ein zusammenfassender Fehlerstatus fehlt.
- **Auswirkung:** Quellen werden vermischt; veraltete und neue Inhalte bleiben gemeinsam abrufbar. Ein Teilimport kann als erfolgreicher Lauf erscheinen.
- **Abbau und Abschluss:** Dokumentidentität, Inhaltsversion und Importlauf trennen. Abschluss und Aktivierung eines Imports sowie Fehlerstatus und Resume-Semantik festlegen. Tests prüfen Namenskollisionen, verkürzte Neuimporte, Abbruch und Wiederaufnahme. Bestehende Daten benötigen einen expliziten Migrations- oder Neuimportpfad.
- **Konkretisierung durch Kapitel 8.3:** Importabschluss gemäß [8.3.6](8-3-error-handling.md#836-fachliche-ergebnisse-und-importabschluss) umsetzen: standardmäßiger Abbruch, optionales Fortsetzen bei einzelnen Chunkfehlern, Abbruch bei systemischen Störungen, Laufzusammenfassung, Fehlerbericht und Exitcodes 0/1/2/3. Tests prüfen Teilfehler und gezielte Wiederaufnahme mit derselben Verarbeitungskonfiguration.

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

### TS-09 - Duplizierte Verarbeitung und Konfiguration - Abgeschlossen

- **Umsetzung:** interact.py ist ein reiner RAG-HTTP-Client. `/process` uebernimmt Embedding, Retrieval, optionales Reranking und Generierung. Modellwahl, Metrik, Set und Treffergrenzen sind explizite Parameter. CLI und API verwenden gemma4:e4b als gemeinsamen Antwortmodellstandard; bestehende API-Clients erhalten ohne top_k weiterhin kein Reranking. Urspruengliche und ausgewaehlte Treffer werden getrennt zurueckgegeben.
- **Gemeinsamer Kern:** analyze.py verwendet Providerfunktionen und Prompt aus rag/app.py statt eigener Implementierungen. Import3 hat begrenzte konfigurierbare Verbindungs-/Lesezeitlimits. Historische, nicht unterstuetzte Varianten verbleiben unter TS-14.
- **Fehler und Zeitlimits:** Gemeinsame RAG-Transportfunktion mit konfigurierbaren Zeitlimits, Request-ID-Weitergabe, Restbudget und maximal einem Retry mit kurzer Zufallswartezeit bei Transportfehlern sicher wiederholbarer Operationen. Generierung und Writes werden nicht wiederholt. Ungueltige Providerantworten ergeben 502, Ausfaelle 503. Socket-Aufrufe werden nicht hart unterbrochen; das Budget wird vor/nach Aufrufen geprueft. Importabschluss bleibt TS-05, weitergehende Betriebsabsicherung TS-13.
- **Betrieb:** Neues RAG-Image am 22.11.2026 ausgerollt; CLI mit und ohne Reranking am laufenden System erfolgreich geprueft. Nachweis im Changelog.
- **Pruefung:** Vertragstests pruefen CLI-Delegation, gleiche Verarbeitung bei expliziter Konfiguration, Reranking-Zuordnung, leeren Kontext, Modellwahl, Providervertraege und Retry-/Budgetgrenzen. Isolierte Tests pruefen echte RAG-Verarbeitung mit und ohne Reranking. Aktueller Pruefnachweis im [Changelog](../changelog.md).

### TS-10 – Inkonsistentes Ressourcen- und Begriffsmodell · P2 - Offen

- **Befund:** [Vector](../Vector/app.py) verwendet `/vectors` zum Schreiben, `/chunks/<id>` zum Lesen und `/chunk` zum Löschen; `/chunks` zählt Zeilen. Die Benennungen sind inzwischen präzisiert: `embedding_set_id` bezeichnet das Set, `chunktext` den Quelltext (zuvor `metadata`, Migration vom 21.11.2026). Lesen ohne Variantenfilter nutzt weiterhin `LIMIT 1` ohne eindeutige Auswahl; `/find` liefert IDs ohne Variantenkennung. TS-10 bleibt deshalb offen.
- **Auswirkung:** Mehrdeutige Identitäten und überraschende Clientsemantik, sobald mehrere Varianten existieren.
- **Abbau und Abschluss:** Ressourcen, Schlüssel und Feldbegriffe verbindlich beschreiben. Mehrdeutige Einzelabfragen entweder zurückweisen oder als Sammlung beantworten. Ein Umstellungsplan erhält bestehende Clients oder kennzeichnet einen Schnittstellenbruch. Tests decken dieselbe Chunk-ID in zwei Varianten ab.

### TS-11 – Widersprüchlicher und datenbanknaher Vektorvertrag · P2 - Offen

- **Bereits erledigt:** [rag_common/http_errors.py](../rag_common/http_errors.py), vector/search_options, prueft vor SQL auf 1024 endliche Zahlen, erlaubt Listen und JSON-Listenstrings und verbietet Nullnorm bei Cosine. chunktext ist String/null. [RAG](../rag/app.py), generate_embedding, prueft Form, Zahlen und endliche positive Norm; verletzte Providervertraege ergeben 502. Diese Validierung nicht neu einplanen.
- **Restbefund:** Vector-Docstrings beschreiben pgvector-Strings; Suchantworten liefern Vektoren ohne Diagnose-Opt-in in datenbanknaher Darstellung. analyze.py verwendet json.loads; init.sql bleibt VECTOR(1024). generate_embedding prueft nicht die erwartete Dimension; endliche falsch dimensionierte Providervektoren scheitern erst beim Retrieval. Import3 normalisiert ohne gleichwertige Norm-/Endlichkeitspruefung.
- **Abbau und Abschluss:** Kanonischen JSON-Ausgabevertrag und Vektor-Opt-in festlegen, Analyseclient/Docstrings anpassen. Providerdimension vor Retrieval mit 502 absichern und Importvalidierung ergaenzen. Vorhandene Eingangsvalidierung erhalten. Andere Dimensionen sind eine gesonderte Architekturentscheidung, keine Voraussetzung dieser Bereinigung.

### TS-12 – Unvollständige Adapter und ungenutzte Konfiguration · P2 - Offen

- **Befund:** [gateway.py](../Ingest/gateway.py) gibt rohe `requests.Response`-Objekte zurück; [keywords.py](../Ingest/keywords.py) kennt weiterhin die jeweiligen Providerformate. Der Gatewayparameter `chunk` wird nicht genutzt. Import3 verwirft die gelieferten Metriken und die Frage. In [RAG](../rag/app.py) definierte Ollama-Endpunktkonstanten steuern die echten Aufrufe nicht; diese verwenden den Resolver. Tests orientieren sich teilweise an den Konstanten. Auch `QUERY` und `NUM_RESULTS` sind dort ungenutzt.
- **Auswirkung:** Die scheinbar gemeinsame Abstraktion kapselt Providerdetails nicht; Änderungen und Tests können sich auf wirkungslose Konfiguration beziehen.
- **Abbau und Abschluss:** Einen kleinen gemeinsamen Ergebnistyp für Keyword-Provider einführen. Unbenutzte Argumente und Konstanten entfernen; benötigte Versuchsdaten strukturiert speichern. Tests prüfen die tatsächlich aufgelösten Adressen und das gemeinsame Providerergebnis.
- **Konkretisierung durch Kapitel 8.3:** Adapter übersetzen technische Fehler und verletzte Antwortverträge gemäß [8.3.1–8.3.3](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten) in gemeinsame Anwendungsfehler unter Erhalt der Ursache. Tests sichern die Übersetzung ab; rohe Providerantworten nicht als öffentliche Fehlertexte weiterreichen.

- **Aktuelle Abgrenzung:** RAG-Transportadapter kapseln bereits Timeout/Verbindungsfehler als 503, pruefen Providerantworten und reichen Request-IDs weiter; /evaluate nutzt dieselben Funktionen. Offen bleiben Import-/Keyword-Adapter, sichere Logs und wirkungslose Konstanten. Der Ollama-Resolver scheitert vor upstream_post mit RuntimeError (generische 500); seine Probes werden nicht mit dem Restbudget begrenzt. Socket-Zeitlimits erlauben keinen harten Abbruch. Diese Grenzen gezielt pruefen, keinen zweiten RAG-Kern bauen.

### TS-13 – Widersprüchlicher Modelllade- und Health-Lebenszyklus · P2 - Offen

- **Befund:** Seit TS-02 werden Modellladen und Inferenz synchronisiert; ungueltige Rerank-Anfragen loesen kein Modellladen mehr aus. `/health` laedt bei noch ungeladenem Dienst weiterhin das Defaultmodell und wartet auf laufende Modelloperationen. Getrennte Liveness-/Readiness-Endpunkte fehlen.
- **Auswirkung:** Health-Aufrufe koennen durch Modellinitialisierung oder Inferenz blockieren; Prozesslebendigkeit und Modellbereitschaft sind nicht getrennt erkennbar.
- **Abbau und Abschluss:** Getrennte Liveness-/Readiness-Zustaende mit Fehler-, Zustands- und Neustarttests einfuehren. Die Synchronisierung ist mit TS-02 umgesetzt; TS-13 bleibt fuer den Health-Vertrag offen.
- **Konkretisierung durch Kapitel 8.3:** Health-Vertrag gemäß [8.3.7](8-3-error-handling.md#837-diagnose-und-betriebszustand) umsetzen: Liveness ohne Modellinitialisierung, zeitlich begrenzte Readiness und 503 mit Problem Details bei fehlender Bereitschaft. Tests berücksichtigen laufendes Laden und Inferenz.

### TS-14 – Fehlerhafte Analyse und unklare Alt-Einstiegspunkte · P1 - Offen

- **Befund:** In [analyze.py](../analyze.py) umfasst `GOLDCHUNK` nur die Keyword-Zeile; die folgenden Stringliterale sind eigenständige Ausdrücke. Dies wurde per AST-Auswertung bestätigt. [import.py](../Ingest/import.py) verwendet `np` ohne Import und übergibt ein nicht unterstütztes Argument `metadata` an die Speicherfunktion. Der [lokale Reranker](../reranker/reranker-local.py) dupliziert Serverlogik mit anderem Standardmodell.
- **Auswirkung:** Irreführende Ähnlichkeitsmessungen und erst im Fehlerpfad sichtbare Defekte; unklarer Wartungsumfang.
- **Abbau und Abschluss:** Den Goldtext korrigieren und durch einen gezielten Regressionstest sichern. Unterstützte Einstiegspunkte festlegen; andere ausdrücklich archivieren oder entfernen. Für unterstützte Varianten Smoke- und Fehlerpfadtests vorsehen. P1 betrifft die Messkorrektheit; die Providerkonsolidierung aus TS-09 ist bereits umgesetzt.

- **Codepruefung 22.11.2026:** AST bestaetigt weiterhin GOLDCHUNK mit nur 46 Zeichen und 14 eigenstaendigen Stringausdruecken. Providerkonsolidierung aus TS-09 ist inzwischen erledigt; Goldtext und defekte Alt-Einstiege bleiben davon unberuehrt. /evaluate liefert die technische Schrittzerlegung, aber noch keinen Goldvergleich oder geprueften Goldkorpus.

### TS-15 – Nicht reproduzierbare Builds und fehlende Schemamigrationen · P2 - Offen

- **Bereits erledigt:** [Vector/migrations](../Vector/migrations) enthaelt 001_embedding_set_id.sql und 002_chunktext.sql. [Migrationsskript](../scripts/migrate_embedding_set_id.py) erstellt vor Ausfuehrung einen Dump und prueft ihn mit pg_restore --list. [Integrationstests](../tests/podman/test_embedding_migration.py) pruefen alte Teststruktur, Wiederholbarkeit, Daten-/Constraint-Erhalt und Backup-Wiederherstellung. Die bisherige Aussage, ein versionierter Migrationspfad fehle, ist ueberholt.
- **Restbefund:** Pakete/Basisimages nicht vollstaendig fixiert; Vector/Dockerfile baut pgvector vom aktuellen Git-Stand. Modellrevisionen sind nicht durchgaengig erfasst. Einzelne Migrationen werden explizit ausgewaehlt; allgemeine Versionserkennung und automatische Reihenfolge fehlen.
- **Abbau und Abschluss:** Abhaengigkeiten, Basisimages, pgvector-Commit und Modellrevisionen nachvollziehbar fixieren. Vor weiteren Schemaaenderungen den vorhandenen Backup-/Migrationspfad erweitern und testen; bei wachsender Anzahl Versionserkennung/Reihenfolge absichern. Vorhandene Migrationen nicht neu implementieren; bitgleiche Modellantworten bleiben kein Abschlusskriterium.

### TS-16 – Indexstrategie passt nicht zu allen Suchmetriken · P3 - Offen

- **Befund:** [init.sql](../Vector/init.sql) erstellt nur einen HNSW-Index mit `vector_l2_ops`; [interact.py](../interact.py) sucht standardmäßig mit Cosinus. Dieser Index unterstützt den Cosinus-Operator nicht.
- **Auswirkung:** Metrikvergleiche können zugleich unterschiedliche Zugriffspfade vergleichen. Ein konkretes Laufzeitproblem wurde nicht gemessen.
- **Abbau und Abschluss:** Repräsentative Datenmengen und gefilterte sowie ungefilterte Suchpläne messen. Metrikspezifische Indizes oder eine begründete gemeinsame Suchstrategie wählen. Indexänderungen über TS-15 migrieren; Laufzeit und Retrievalqualität gemeinsam dokumentieren.

### TS-17 – Testabdeckung umgeht relevante Verarbeitungspfade · P1, begleitend - Offen

- **Bereits erledigt:** [Chunkingtests](../tests/unit/test_chunking.py) pruefen echte Mehrfachsplits mit Grenzen und Overlap. [Importintegration](../tests/podman/test_import3_integration.py) verwendet process_file inklusive echter Keywords, Embeddings, Speicherung und Ruecksuche im isolierten Set. [Vectorintegration](../tests/podman/test_vector_api.py) prueft parallele Upserts, stabile IDs, SQL-Rollback/Poolwiederverwendung sowie verzoegerten DB-Start und Erholung ohne API-Neustart. Eingangsvalidierung, Problem Details, no_context, Reranking und Metriken sind getestet. [RAG-E2E](../tests/podman/test_rag_e2e.py) prueft echte Verarbeitung mit/ohne Reranking und die Evaluationskette. Ein separat vorbereiteter RAG-E2E-Test ist neben der eigenen Importintegration keine pauschale Import-Abdeckungsluecke mehr.
- **Restumfang:** Importfehler, Namenskollisionen, kuerzere Neuimporte und fachlich abgesicherter Resume fehlen passend zu TS-05; --start allein ist kein Resume-Nachweis. Goldtextkorrektheit/Alt-Einstiege (TS-14), Reranker-Health bei Laden/Inferenz (TS-13), Persistenz nach DB-Neuerstellung mit demselben Testvolume sowie repraesentative Last-/Suchplannachweise bleiben offen. Der TS-07-Test mit tmpfs belegt Erholung, keine Volume-Persistenz.
- **Abbau und Abschluss:** Resttests jeweils mit TS-05/10/11/12/13/14/15/16 liefern; deterministische und echte Modelltests getrennt halten. Fuer geplante Qualitaetsmessungen Gold-Antworten, erwartete Treffer, Bewertungsmetriken und Versuchsmatrizen definieren. /evaluate stellt bislang die technische Schnittstelle bereit, keinen Qualitaetsnachweis. Manuell genutzte Daten und Volumes erhalten.

### TS-18 – Experimenteller Betriebsrahmen · P3, bedarfsabhängig - Offen

- **Befund:** Die APIs starten Flask-Entwicklungsserver; Authentifizierung fehlt, Beispiel-DB-Zugangsdaten sind fest vorbelegt. Ein einheitliches Readiness-Konzept fehlt. Siehe [Startanleitung](../README.md), [Vector](../Vector/app.py), [RAG](../rag/app.py) und [Reranker](../reranker/app.py).
- **Auswirkung:** Der dokumentierte lokale Experimentbetrieb ist nicht ohne weitere Maßnahmen auf Mehrbenutzer- oder exponierten Dauerbetrieb übertragbar.
- **Abbau und Abschluss:** Vor einer solchen Nutzung Betriebsgrenzen festlegen, geeigneten Serverbetrieb, Zugangskontrolle, externe Geheimniskonfiguration und Readiness umsetzen und prüfen. Bei unverändert lokalem Einsatz bleibt dies eine dokumentierte Einschränkung. Bei geplanter Exposition steigt die Priorität vor deren Freigabe auf P1.
- **Konkretisierung durch Kapitel 8.3:** Readiness und öffentliche Fehlerausgaben folgen [8.3.7](8-3-error-handling.md#837-diagnose-und-betriebszustand). Die lokale Betriebsabsicherung unter TS-07/TS-13 hängt nicht erst von einer späteren Exposition ab.

- **Aktuelle Abgrenzung:** Vector hat getrennte Liveness/Readiness (TS-07). RAG hat keine Health-Endpunkte; Reranker-/health kann weiterhin beim Modellzugriff blockieren. Fehlende Authentifizierung, Entwicklungsserver und Beispielzugangsdaten sind unveraendert. Die lokalen Health-Restarbeiten nicht erst bei Exposition bearbeiten.

## 11.2.3 Priorisierte Reihenfolge für den Abbau

Nur offene Restarbeiten werden eingeplant. Abgeschlossene TS-01/02/03/06/07/08/09 nicht erneut umsetzen. TS-17 begleitet die jeweilige Korrektur mit Tests; Codepruefung ersetzt keine Last- oder Betriebsabnahme.

| Reihenfolge | Offenes Paket | Freigabekriterium | Abhaengigkeit |
|---|---|---|---|
| 1 | **Messkorrektheit: TS-14 (P1)** | Goldtext vollstaendig und regressionstestgesichert; unterstuetzte Analyse-/Importeinstiege benannt, defekte Altvarianten korrigiert oder archiviert. | Keine; gemeinsamer Providerkern und /evaluate existieren bereits. |
| 2 | **Importidentitaet/Abschluss: TS-05 (P1), TS-17** | Kollisionsfreie Dokument-/Versionsidentitaet, kuerzere Neuimporte ohne Altlasten, eindeutige Fehlerberichte/Exitcodes, Abbruch und Resume getestet; Bestandsdatenpfad festgelegt. | Vor Schemaaenderung vorhandene Migrationsbasis aus TS-15 gezielt erweitern. Vollstaendiges Build-Pinning ist keine Voraussetzung der fachlichen Korrektur. R-01 manuell pflegen. |
| 3 | **Health: TS-13 (P2), RAG-Rest aus TS-18** | Reranker-Liveness ohne Modellladen, begrenzte Readiness auch bei Inferenz/Laden; RAG-Bereitschaft explizit und getestet. | Unabhaengig vorziehbar; Vector-Lebenszyklus aus TS-07 erhalten. |
| 4 | **Identitaets-/Vektorvertraege: TS-10/11 (P2)** | Keine mehrdeutigen Einzelchunkantworten; Set-Identitaet bei ID-Suche; kanonische Vektorausgabe/Opt-in; Providerdimension und Importvektoren frueh validiert. | API-Umstellung explizit planen; Migrationsanpassung nur bei Schemaaenderung. Vorhandene Eingangsvalidierung erhalten. |
| 5 | **Adapterreste: TS-12 (P2)** | Gemeinsames Keyword-Ergebnis, keine wirkungslosen Parameter/Konstanten, sichere Logs; Resolverfehler und Restbudgetgrenzen getestet. | Gemeinsamer RAG-Kern existiert; keine Gesamtrefaktorierung oder harte Abhaengigkeit von 2/4. |
| parallel | **Builds/Migrationserweiterung: TS-15 (P2)** | Paket-/Image-/pgvector-/Modellrevisionen festgehalten; vorhandene Backup-/Migrationstests fuer neue Schemata erweitert. | Fuer belastbare Vergleiche und vor neuen Schemamigrationen; vorhandene Migrationen als Basis nutzen. |
| danach | **Suchplaene/Performance: TS-16 (P3), TS-17** | Repraesentative L2-/Cosine-Plaene und Messungen mit Datenmenge/Set/Build; begruendete Indexwahl migriert. Persistenz-/Lastnachweise getrennt ausweisen. | Stabile Datenidentitaet und dokumentierte Builds; keine unbelegte Performanceoptimierung. |
| bedarfsabhaengig | **Erweiterter Betrieb: TS-18 (P3, bei Exposition P1)** | Serverbetrieb, Zugangskontrolle und externe Geheimnisse passend zum realen Einsatz getestet. | Vor Mehrbenutzer-/exponiertem Betrieb; lokale Health-Arbeit nicht aufschieben. |

Die geplante Gold-Antwort-Evaluation baut auf /evaluate auf: Goldkorpus, erwartete Retrievaltreffer, Antwortbewertung und Versuchskonfiguration muessen noch definiert werden. Erfolgreiche Live-Verkettung ist kein Qualitaetsnachweis. Fuer R-01 gilt weiter die manuelle Set-Zuordnung aus Abschnitt 8.2; unbekannte Herkunft bleibt unbekannt. Bestandsdatenmigrationen aus TS-05 gesondert festlegen; keine manuell genutzten Volumes stillschweigend loeschen.

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
