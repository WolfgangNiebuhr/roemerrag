<!--

purpose: "Bestehende technische Schulden, ihre Auswirkungen, Schweregrade und verbleibenden Arbeiten im Römer-RAG-Projekt."
agent_instructions:
  - "Einträge anhand der bestehenden Schweregrade nach ihrer Auswirkung priorisieren. Konkrete betroffene Schnittstellen, Bausteine oder Qualitätsziele benennen und bei Bedarf verlinken. Ausdrücklich erfasste Risiken gehören in Kapitel 11.1."
  - "Jeder Eintrag hat eine stabile TS-ID und genau einen Status: offen, teilweise behoben, behoben oder abgelehnt."
  - "Neben Titel und Status sind die ursprüngliche Problembeschreibung, eine Bewertung nach Schweregrad und ein Lösungsvorschlag zulässig."
  - "Bei Statusänderungen die ursprüngliche Problembeschreibung unverändert erhalten."
  - "Bei Status teilweise behoben einen eigenen Abschnitt Noch offen mit den verbleibenden Arbeiten führen."
  - "Bei jeder weiteren Teilbehebung den bestehenden Abschnitt Noch offen aktualisieren. Abgearbeitete Punkte daraus entfernen und keinen weiteren Abschnitt anlegen."
  - "Sobald ein Eintrag behoben oder abgelehnt ist, den Abschnitt Noch offen entfernen."
  - "Hier nur den aktuellen Status führen. Änderungshistorie, Prüf- und Ausrollnachweise ausschließlich in ../changelog.md pflegen."

-->

# 11.2 Technische Schulden

Das Register enthält den aktuellen Status. Historische Änderungen und Prüfnachweise stehen im [Changelog](../changelog.md). Akzeptierte Risiken stehen in [Kapitel 11.1](11-1-risiken.md).

## 11.2.1 Schweregrade

| Schweregrad | Bedeutung |
|---|---|
| P1 | Datenintegrität, verfälschte Experimente oder Fehler im regulären Verarbeitungspfad |
| P2 | Strukturelle Inkonsistenzen, Betriebsstabilität oder fehlende Reproduzierbarkeit |
| P3 | Nach Stabilisierung oder bei entsprechendem Betriebsbedarf zu bearbeiten |

Für die Erweiterbarkeit sind die Befunde TS-23 bis TS-26 nach abnehmender Auswirkung geordnet. Vorrang haben Änderungen, die mehrere Dienste und Bestandsdaten berühren, gefolgt von Änderungen an mehreren RAG-Verarbeitungspfaden und Kopplungen innerhalb eines Bausteins.

## 11.2.2 Schuldenregister

### TS-01 – Abweichende Import- und Retrievaldefaults

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

Import3, CLI und RAG verwendeten unterschiedliche Defaults für Embeddingmodell und Variantenkennung. Beim Retrieval konnte dadurch ein anderes Set als beim Import ausgewählt werden.

### TS-02 – Wirkungslose Reranker-Modellwahl

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

Die Wahl des Reranker-Modells in der CLI hatte keine Wirkung auf das tatsächlich im Reranker-Dienst verwendete Modell.

### TS-03 – Requestvalidierung und Fehlerverträge

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

RAG-, Vector- und Reranker-API validierten JSON-Struktur, Feldtypen und Wertebereiche uneinheitlich. Ungültige Anfragen konnten HTML-Fehler mit HTTP 500 und vermeidbare Modellarbeit auslösen. Clients erhielten keinen einheitlich auswertbaren Fehlervertrag.

### TS-04 – Manuelle Zuordnung von Importvarianten

**Status** · abgelehnt

**Problembeschreibung**

Eine frei vergebene `embedding_set_id` belegt weder die Chunking- und Anreicherungsparameter noch Prompt, Modell oder Normalisierung. Ohne technische Prüfung können unterschiedliche Verarbeitungen im selben Set landen und Chunks überschreiben. Das verbleibende Risiko wird als [R-01](11-1-risiken.md#r-01--manuelle-zuordnung-von-importvarianten--akzeptiertes-risiko) geführt. Die Set-Zuordnung erfolgt manuell gemäß [Architekturentscheidung 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026).

### TS-05 – Chunk-Identität und Importabschluss

**Status** · behoben


**Schweregrad** · P1

**Problembeschreibung**

[Import3](../Ingest/import3.py), `process_file`, erzeugt IDs aus `basename.split('.')[0]` und laufender Nummer. `rom.band1.txt` und `rom.band2.txt` kollidieren innerhalb derselben Variante. Kürzere Wiederholungsimporte entfernen keine alten überzähligen Chunks. Chunkfehler werden protokolliert; ein zusammenfassender Fehlerstatus fehlt. Quellen werden vermischt; veraltete und neue Inhalte bleiben gemeinsam abrufbar. Ein Teilimport kann als erfolgreicher Lauf erscheinen.

### TS-06 – Nebenläufigkeit und Schreibsemantik der Vector-API

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

Die Vector-API verwendete einen für parallele Zugriffe ungeeigneten `SimpleConnectionPool` und ersetzte Datensätze per `DELETE` und `INSERT`. Konkurrierende Schreibzugriffe konnten am Unique Constraint scheitern. Updates änderten die interne ID.

### TS-07 – Datenbankinitialisierung und Readiness

**Status** · behoben

**Schweregrad** · P2

**Problembeschreibung**

[Vector](../Vector/app.py) erstellt den Pool beim Modulimport. Scheitert dies, bleibt `db_pool` ohne weiteren Initialisierungsversuch `None`. Ein vorübergehender Startreihenfolgefehler erfordert einen Prozessneustart, obwohl PostgreSQL später bereit ist.

### TS-08 – Kontext- und Metrikverarbeitung

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

Die RAG-API prüfte Suchantworten nur auf den äußeren Listentyp und generierte auch bei leerer Trefferliste. Eine `eval_duration` von null konnte zur Division durch null führen. Fehlerhafte Treffer oder optionale Metriken konnten die Ausgabe einer vorhandenen Antwort verhindern.

### TS-09 – Duplizierte Verarbeitung und Konfiguration

**Status** · behoben

**Schweregrad** · P2

**Problembeschreibung**

[RAG](../rag/app.py), [CLI](../interact.py) und [Analyse](../analyze.py) implementieren Embedding, Suche, Prompt und Generierung mehrfach. Defaults für Modell, Metrik, Filter, Timeouts und Metrikdarstellung unterscheiden sich. Das CLI nutzt aktuell `gemma4:e4b`, die RAG-API `phi3:mini`. Import- und Analysewerkzeuge haben eigene feste Dienstadressen und teilweise keine HTTP-Timeouts. Fehlerbehebungen erreichen nur einzelne Pfade; Vergleiche ändern unbemerkt mehrere Parameter. Dienststörungen können Werkzeuge unbegrenzt blockieren.

### TS-10 – Inkonsistentes Ressourcen- und Begriffsmodell

**Status** · behoben

**Schweregrad** · P2

**Problembeschreibung**

Die Vector-API verteilt Schreiben, Einzelabruf, Zählen und Löschen auf unterschiedliche Ressourcenpfade. Feldbegriffe und Set-Identität sind nicht durchgängig einheitlich. Eine Chunk-ID kann in mehreren Sets vorkommen, während Einzelabruf und ID-Suche ohne eindeutige Set-Zuordnung mehrdeutig sein können.

**Umsetzung**

Einzelabruf, Text- und Vektorsuche verlangen eine Set-ID. Fehlt sie, melden diese Endpunkte HTTP 400. `GET /chunks` zählt wahlweise ein Set oder alle Datensätze. Tests verwenden dieselbe Chunk-ID in zwei Sets.

### TS-11 – Widersprüchlicher und datenbanknaher Vektorvertrag

**Status** · behoben

**Schweregrad** · P2

**Problembeschreibung**

[Vector-Docstrings](../Vector/app.py) erwarten pgvector-Strings; aktuelle Clients senden Zahlenlisten. Dimension, endliche Zahlenwerte und Metadatentypen sind nicht vollständig abgesichert. Suchantworten enthalten auch die gespeicherten Vektoren; [analyze.py](../analyze.py) verarbeitet diese als JSON-Strings. Das [Schema](../Vector/init.sql) bindet alle Varianten an 1024 Dimensionen. Clientkopplung an Datenbankdarstellung, späte SQL-Fehler und unnötige Nutzlasten. Weitere Embeddingmodelle sind nicht allein durch eine neue Variantenkennung anschließbar.

### TS-12 – Unvollständige Adapter und ungenutzte Konfiguration

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

[gateway.py](../Ingest/utils/gateway.py) gibt rohe `requests.Response`-Objekte zurück; [keywords.py](../Ingest/utils/keywords.py) kennt weiterhin die jeweiligen Providerformate. Der Gatewayparameter `chunk` wird nicht genutzt. Import3 verwirft die gelieferten Metriken und die Frage. In [RAG](../rag/app.py) definierte Ollama-Endpunktkonstanten steuern die echten Aufrufe nicht; diese verwenden den Resolver. Tests orientieren sich teilweise an den Konstanten. Auch `QUERY` und `NUM_RESULTS` sind dort ungenutzt. Die scheinbar gemeinsame Abstraktion kapselt Providerdetails nicht; Änderungen und Tests können sich auf wirkungslose Konfiguration beziehen.

#### Noch offen

Import- und Keyword-Adapter mit einem gemeinsamen Ergebnistyp versehen. Den ungenutzten Gatewayparameter `chunk` sowie `QUERY` und die ungenutzten Ollama-Endpunktkonstanten in der RAG-API bereinigen. Fehler des Ollama-Resolvers einheitlich übersetzen, dessen Probes ans Restbudget binden und sichere Fehlerausgaben prüfen.

**Lösungsvorschlag**

Die Schnittstellen auf die gemeinsame Fehlerübersetzung aus [Kapitel 8.3](8-3-error-handling.md) stützen und Tests auf tatsächlich aufgelöste Dienstadressen beziehen.

### TS-13 – Widersprüchlicher Modelllade- und Health-Lebenszyklus

**Status** · offen

**Schweregrad** · P2

**Problembeschreibung**

Der Reranker kann über `/health` das Defaultmodell laden oder auf laufende Modelloperationen warten. Prozesslebendigkeit und Modellbereitschaft lassen sich dadurch nicht unabhängig abfragen.

**Lösungsvorschlag**

Liveness ohne Modellinitialisierung und zeitlich begrenzte Readiness einführen. Fehlende Bereitschaft als HTTP 503 mit Problem Details melden. Laden, laufende Inferenz und Neustart prüfen.

### TS-14 – Fehlerhafte Analyse und unklare Alt-Einstiegspunkte

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

In [analyze.py](../analyze.py) umfasst `GOLDCHUNK` nur die Keyword-Zeile; die folgenden Stringliterale sind eigenständige Ausdrücke. Dies wurde per AST-Auswertung bestätigt. `Ingest/import.py` verwendet `np` ohne Import und übergibt ein nicht unterstütztes Argument `metadata` an die Speicherfunktion. Der [lokale Reranker](../archive/reranker-local.py) dupliziert Serverlogik mit anderem Standardmodell. Irreführende Ähnlichkeitsmessungen und erst im Fehlerpfad sichtbare Defekte; unklarer Wartungsumfang.

**Unterstützte Einstiegspunkte**

[`analyze.py`](../analyze.py) ist die unterstützte Analyse-CLI und übergibt den vollständigen Gold-Chunk an die RAG-API. 

### TS-15 – Nicht reproduzierbare Builds und Testumgebungen

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

Die Dockerfiles für [Vector](../Vector/Dockerfile), [RAG](../rag/Dockerfile) und [Reranker](../reranker/Dockerfile) fixieren Abhängigkeiten nicht vollständig. pgvector wird vom aktuellen Repositorystand gebaut. Modellrevisionen werden nicht durchgängig erfasst. `init.sql` wirkt nur bei leerem Datenverzeichnis; ein versionierter Migrationspfad fehlt. Gleicher Projektcode erzeugt unterschiedliche Laufzeitstände; bestehende Volumes bleiben bei Schemaänderungen zurück.

#### Noch offen

Abhängigkeiten, Basisimages, pgvector-Commit und Modellrevisionen fixieren. Die dokumentierte Testinstallation in einer frischen Umgebung prüfen. Bei weiteren Migrationen Versionserkennung und Reihenfolge absichern.

### TS-16 – Indexstrategie passt nicht zu allen Suchmetriken

**Status** · offen

**Schweregrad** · P3

**Problembeschreibung**

Das Datenbankschema legt einen HNSW-Index für euklidische Distanz an, während die CLI standardmäßig Cosinus nutzt. Die Suchmetriken können dadurch unterschiedliche Zugriffspfade verwenden. Bei normierten Vektoren entspricht die exakte Rangfolge beider Metriken einander.

**Lösungsvorschlag**

Repräsentative Suchpläne für setgebundene Abfragen messen, Treffer gegen eine exakte Referenz abgleichen und daraus eine begründete Indexstrategie ableiten.

### TS-17 – Testabdeckung umgeht relevante Verarbeitungspfade

**Status** · teilweise behoben

**Schweregrad** · P1, begleitend

**Problembeschreibung**

Der [E2E-Test](../tests/podman/test_rag_e2e.py) importiert selbst und umgeht Import3 samt Keywords. [Chunking-Tests](../tests/unit/test_chunking.py) prüfen keinen echten Mehrfachsplit mit Grenzen und Overlap. [Vector-Unit-Tests](../tests/unit/test_vector_api_unit.py) decken konkurrierendes Schreiben und die bestätigten fehlerhaften Eingaben nicht ab. Persistenz-, Wiederanlauf- und Lastnachweise fehlen teilweise. Eine grüne Suite erkennt Fehler im tatsächlich benutzten Pfad nicht zuverlässig.

#### Noch offen

Regressionstests zu den offenen Verträgen aus TS-12/13/15/21 ergänzen. Repräsentative Last und Suchpläne prüfen sowie Goldantworten und erwartete Retrievaltreffer über einen breiteren Korpus absichern.

**Lösungsvorschlag**

Deterministische Vertragstests und echte Modelltests getrennt halten. Goldkorpus, erwartete Treffer, Antwortbewertung und Versuchsparameter gemeinsam definieren.

### TS-18 – Experimenteller Betriebsrahmen

**Status** · teilweise behoben

**Schweregrad** · P3 im lokalen Betrieb, P1 vor einer Exposition

**Problembeschreibung**

Die APIs starten Flask-Entwicklungsserver; Authentifizierung fehlt, Beispiel-DB-Zugangsdaten sind fest vorbelegt. Ein einheitliches Readiness-Konzept fehlt. Siehe [Startanleitung](../README.md), [Vector](../Vector/app.py), [RAG](../rag/app.py) und [Reranker](../reranker/app.py). Der dokumentierte lokale Experimentbetrieb ist nicht ohne weitere Maßnahmen auf Mehrbenutzer- oder exponierten Dauerbetrieb übertragbar.

#### Noch offen

RAG-Readiness und den Reranker-Health-Vertrag ergänzen. Für Mehrbenutzer- oder exponierten Betrieb fehlen geeigneter Serverbetrieb, Zugangskontrolle und externe Geheimniskonfiguration.

**Lösungsvorschlag**

Serverbetrieb, Zugangskontrolle und externe Geheimnisse vor einer Exposition umsetzen und prüfen. Lokale Health-Arbeiten begleiten TS-13 unabhängig davon.

### TS-19 – Stiller Trefferverlust beim Reranking

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

Der Reranker koppelt Dokumente und Modell-Scores per `zip`. Bei zu wenigen Scores fallen Dokumente still aus der Antwort. Die RAG-API prüft die vorhandenen Indizes, aber keine vollständige Zuordnung. Leere oder unvollständige Modellergebnisse können daher als reguläres Ergebnis erscheinen. Die Prüfung nicht endlicher Scores unterscheidet sich zwischen den RAG-Pfaden.

Der [Reranker](../reranker/app.py) prüft Modellscores vor der Sortierung. Der gemeinsame [RAG-Adapter](../rag/app.py) prüft alle zurückgegebenen Scores und Indizes vor der `top_k`-Auswahl. Ungültige Scores führen zu HTTP 502 im Schritt `reranking`. Leere Eingaben werden separat behandelt und getestet. Fehlende und überzählige Scores sind für den Betrieb mit dem Standardmodell als [Risiko R-04](11-1-risiken.md#r-04--fehlende-oder-überzählige-scores-beim-reranking) akzeptiert.

### TS-20 – Widersprüchlicher Vertrag für fehlenden Chunktext

**Status** · behoben

**Schweregrad** · P1

**Problembeschreibung**

Die Vector-API akzeptiert fehlenden oder nullwertigen `chunktext` und kann `null` in Suchtreffern zurückgeben. Der RAG-Adapter verlangt pro Treffer einen String. Dadurch kann ein Treffer ohne Text im Schritt `retrieval` die gesamte Antwort mit HTTP 502 abbrechen, obwohl gültige Nachbartreffer vorliegen.

**Lösungsvorschlag**

Die Vector-API verlangt beim Schreiben einen nichtleeren String. Die Datenbank erzwingt denselben Vertrag mit `NOT NULL` und einem Check-Constraint für leere Strings und reine Kombinationen aus Leerzeichen, LF und CR. Die [Migration für Bestandsdatenbanken](../README.md) prüft vorhandene Zeilen beim Anlegen der Constraints.

### TS-21 – Überschrittene Chunkgröße bei langen Passagen

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

Absatz- und Satztrennung ohne Zeichen-Fallback kann bei langen, ungetrennten Passagen die konfigurierte Chunkgröße überschreiten. Die tatsächlichen Eingabelängen können dadurch von den Versuchsparametern abweichen. Betroffen ist die [Pipeline-Beispielkonfiguration ohne Fallback](../Ingest/experiments/snowflake-arctic-embed-v2.json).

#### Noch offen

Für Strategien ohne Zeichen-Fallback eine explizite Größenregel festlegen. Bei Versuchen die tatsächlich erzeugten Chunklängen ausweisen.

**Lösungsvorschlag**

Für Strategien mit garantierter Obergrenze einen Fallback samt Regressionstest für ungetrennte Passagen vorsehen. Bei geänderter Verarbeitung eine eigene Set-ID gemäß R-01 verwenden.

### TS-22 – Veraltete Angaben in der Bausteinsicht

**Status** · behoben

**Schweregrad** · P2

**Problembeschreibung**

Die Bausteinsicht nennt noch `snowflake-arctic-embed2` als RAG-Standardfilter und beschreibt das Schreiben als Löschen und Einfügen. Der Code verwendet standardmäßig das Set `snowflake-arctic-embed2-v2` und einen atomaren Upsert. Die Übersicht führt die alte Abweichung der Defaults noch als offenen Punkt. Die Ergänzung zu TS-03 bezeichnet die Transaktions- und Poolnebenläufigkeit weiterhin als offen, obwohl TS-06 abgeschlossen ist. [Bausteinsicht](5-bausteinsicht.md)

### TS-23 – Dokumentzugehörigkeit an das Format der Chunk-ID gekoppelt

**Status** · abgelehnt

**Schweregrad** · P2

**Problembeschreibung**

`make_chunks()` im [Import](../Ingest/pipeline.py) erzeugt IDs aus Dateistamm und laufender Nummer. `delete_chunks()` in der [Vector-API](../Vector/app.py) leitet Dokumentzugehörigkeit und Chunknummer aus dem Präfix und dem kanonischen numerischen Suffix dieser IDs ab. Neue Importstrategien mit einem anderen ID-Format erfordern dadurch Anpassungen am Import, an der Löschabfrage und gegebenenfalls am Umgang mit Bestandsdaten. [TS-05](#ts-05--chunk-identität-und-importabschluss) erfasst den bereits umgesetzten Importabschluss, [R-02](11-1-risiken.md#r-02-dateistamm-als-dokumentidentitaet) das akzeptierte Kollisionsrisiko bei gleichen Dateistämmen.

**Lösungsvorschlag**

Dokumentzugehörigkeit und Chunkreihenfolge als explizite Merkmale im Speicher- und Löschvertrag modellieren. Bei einer Umstellung vorhandene IDs und Set-Zuordnungen berücksichtigen und die Bereinigung für beide Datenstände absichern.

Das bestehende Format ist eine bewusste [Architekturentscheidung](9-architekturentscheidungen.md#95-herkunft-und-reihenfolge-in-der-chunk-id-abbilden-27112026-ts-23).

### TS-24 – Treffer- und Kontextregeln in mehreren RAG-HTTP-Handlern

**Status** · offen

**Schweregrad** · P2

**Problembeschreibung**

In der [RAG-API](../rag/app.py) filtern `process_request()`, `evaluate_rerank()` und `evaluate_generate()` leere Treffertexte separat. `process_request()` und `evaluate_generate()` bilden jeweils den Kontext und behandeln fehlenden Kontext im HTTP-Handler. Die Providerfunktionen werden bereits gemeinsam genutzt. Eine neue Auswahl- oder Kontextstrategie muss trotzdem in mehreren Endpunkten eingearbeitet werden. Das erschwert konsistente Vergleiche zwischen dem regulären Ablauf und der schrittweisen Evaluation.

**Lösungsvorschlag**

Gemeinsame Trefferaufbereitung und Kontextbildung unabhängig von Flask ausführen. HTTP-Handler übernehmen Eingabe und Ausgabe entsprechend ihrem jeweiligen Vertrag.

### TS-25 – Importablauf mit Transport, Artefakten und CLI-Ausgabe verflochten

**Status** · offen

**Schweregrad** · P2

**Problembeschreibung**

`run()` in der [Importpipeline](../Ingest/pipeline.py) steuert Anreicherung, Embedding, Speicherung und Wiederaufnahme. Dieselbe Funktion liest Zeitlimits aus der Umgebung, schreibt lokale Artefakte, sendet Vector-HTTP-Anfragen, prüft deren konkrete Antwortfelder und formatiert die Wiederaufnahmeanweisung für `stderr`. Änderungen am Speichervertrag, Artefaktziel oder an der Bedienung greifen damit direkt in die Orchestrierung ein. [TS-12](#ts-12--unvollständige-adapter-und-ungenutzte-konfiguration) erfasst Provideradapter und deren Ergebnistypen.

**Lösungsvorschlag**

Speicherzugriff, Artefaktausgabe und CLI-Darstellung über eigene Schnittstellen anbinden. Der Importablauf bestimmt die Reihenfolge und liefert die Wiederaufnahmeinformationen als Ergebnis.

### TS-26 – Vector-Suchhandler vermischt HTTP-Vertrag und Persistenz

**Status** · offen

**Schweregrad** · P2

**Problembeschreibung**

`search_vectors()` in der [Vector-API](../Vector/app.py) verarbeitet HTTP-Eingaben, wählt den pgvector-Operator, führt SQL aus und formt die Treffer zur JSON-Antwort mit Kompatibilitätsalias. Die Transaktion ist bereits gekapselt. Weitere Suchstrategien oder Änderungen am Rückgabeformat betreffen trotzdem dieselbe Funktion. Der nach außen sichtbare Vektorvertrag ist bereits in [TS-11](#ts-11--widersprüchlicher-und-datenbanknaher-vektorvertrag) erfasst.

**Lösungsvorschlag**

Suchoperation und SQL hinter einer internen Schnittstelle bündeln. Der HTTP-Handler übersetzt Anfrage und Treffer in das öffentliche Format.
