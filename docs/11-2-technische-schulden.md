<!--

purpose: "Aktueller Status technischer Schulden im Römer-RAG-Projekt."
agent_instructions:
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

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

Die Vector-API verteilt Schreiben, Einzelabruf, Zählen und Löschen auf unterschiedliche Ressourcenpfade. Feldbegriffe und Set-Identität sind nicht durchgängig einheitlich. Eine Chunk-ID kann in mehreren Sets vorkommen, während Einzelabruf und ID-Suche ohne eindeutige Set-Zuordnung mehrdeutig sein können.

#### Noch offen

Set-Identität bei Einzelabruf und `/find` eindeutig machen. Einzelabrufe ohne Set verwenden `LIMIT 1`; `/find` gibt IDs ohne Set-Kennung aus. Den Ressourcenvertrag konsistent beschreiben.

**Lösungsvorschlag**

Mehrdeutige Einzelabfragen zurückweisen oder als Sammlung beantworten. Die Semantik mit derselben Chunk-ID in zwei Sets testen und einen Schnittstellenbruch ausdrücklich dokumentieren.

### TS-11 – Widersprüchlicher und datenbanknaher Vektorvertrag

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

[Vector-Docstrings](../Vector/app.py) erwarten pgvector-Strings; aktuelle Clients senden Zahlenlisten. Dimension, endliche Zahlenwerte und Metadatentypen sind nicht vollständig abgesichert. Suchantworten enthalten auch die gespeicherten Vektoren; [analyze.py](../analyze.py) verarbeitet diese als JSON-Strings. Das [Schema](../Vector/init.sql) bindet alle Varianten an 1024 Dimensionen. Clientkopplung an Datenbankdarstellung, späte SQL-Fehler und unnötige Nutzlasten. Weitere Embeddingmodelle sind nicht allein durch eine neue Variantenkennung anschließbar.

#### Noch offen

Vektorausgabe und Opt-in für Diagnosevektoren vereinheitlichen. Docstrings und Analyseclient anpassen. Erwartete Providervektordimension vor dem Retrieval prüfen und die Norm- und Endlichkeitsprüfung in Import3 ergänzen.

### TS-12 – Unvollständige Adapter und ungenutzte Konfiguration

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

[gateway.py](../Ingest/utils/gateway.py) gibt rohe `requests.Response`-Objekte zurück; [keywords.py](../Ingest/utils/keywords.py) kennt weiterhin die jeweiligen Providerformate. Der Gatewayparameter `chunk` wird nicht genutzt. Import3 verwirft die gelieferten Metriken und die Frage. In [RAG](../rag/app.py) definierte Ollama-Endpunktkonstanten steuern die echten Aufrufe nicht; diese verwenden den Resolver. Tests orientieren sich teilweise an den Konstanten. Auch `QUERY` und `NUM_RESULTS` sind dort ungenutzt. Die scheinbar gemeinsame Abstraktion kapselt Providerdetails nicht; Änderungen und Tests können sich auf wirkungslose Konfiguration beziehen.

#### Noch offen

Import- und Keyword-Adapter mit einem gemeinsamen Ergebnistyp versehen. Ungenutzte Parameter und Konstanten bereinigen. Fehler des Ollama-Resolvers einheitlich übersetzen, dessen Probes ans Restbudget binden und sichere Fehlerausgaben prüfen.

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

**Status** · teilweise behoben

**Schweregrad** · P1

**Problembeschreibung**

In [analyze.py](../analyze.py) umfasst `GOLDCHUNK` nur die Keyword-Zeile; die folgenden Stringliterale sind eigenständige Ausdrücke. Dies wurde per AST-Auswertung bestätigt. `Ingest/import.py` verwendet `np` ohne Import und übergibt ein nicht unterstütztes Argument `metadata` an die Speicherfunktion. Der [lokale Reranker](../reranker/reranker-local.py) dupliziert Serverlogik mit anderem Standardmodell. Irreführende Ähnlichkeitsmessungen und erst im Fehlerpfad sichtbare Defekte; unklarer Wartungsumfang.

#### Noch offen

`GOLDCHUNK` korrigieren und die vollständige Eingabe durch einen Regressionstest absichern. Die verbleibenden Alt-Einstiegspunkte einschließlich des lokalen Rerankers nach Unterstützung einordnen.

**Lösungsvorschlag**

Unterstützte Einstiegspunkte festlegen und ihre Fehlerpfade testen. Andere Varianten archivieren oder entfernen.

### TS-15 – Nicht reproduzierbare Builds und Testumgebungen

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

Die Dockerfiles für [Vector](../Vector/Dockerfile), [RAG](../rag/Dockerfile) und [Reranker](../reranker/Dockerfile) fixieren Abhängigkeiten nicht vollständig. pgvector wird vom aktuellen Repositorystand gebaut. Modellrevisionen werden nicht durchgängig erfasst. `init.sql` wirkt nur bei leerem Datenverzeichnis; ein versionierter Migrationspfad fehlt. Gleicher Projektcode erzeugt unterschiedliche Laufzeitstände; bestehende Volumes bleiben bei Schemaänderungen zurück.

#### Noch offen

Abhängigkeiten, Basisimages, pgvector-Commit und Modellrevisionen fixieren. Die dokumentierte Testinstallation um SciPy ergänzen und in einer frischen Umgebung prüfen. Bei weiteren Migrationen Versionserkennung und Reihenfolge absichern.

### TS-16 – Indexstrategie passt nicht zu allen Suchmetriken

**Status** · offen

**Schweregrad** · P3

**Problembeschreibung**

Das Datenbankschema legt einen HNSW-Index für euklidische Distanz an, während die CLI standardmäßig Cosinus nutzt. Die Suchmetriken können dadurch unterschiedliche Zugriffspfade verwenden. Bei normierten Vektoren entspricht die exakte Rangfolge beider Metriken einander.

**Lösungsvorschlag**

Repräsentative gefilterte und ungefilterte Suchpläne messen, Treffer gegen eine exakte Referenz abgleichen und daraus eine begründete Indexstrategie ableiten.

### TS-17 – Testabdeckung umgeht relevante Verarbeitungspfade

**Status** · teilweise behoben

**Schweregrad** · P1, begleitend

**Problembeschreibung**

Der [E2E-Test](../tests/podman/test_rag_e2e.py) importiert selbst und umgeht Import3 samt Keywords. [Chunking-Tests](../tests/unit/test_chunking.py) prüfen keinen echten Mehrfachsplit mit Grenzen und Overlap. [Vector-Unit-Tests](../tests/unit/test_vector_api_unit.py) decken konkurrierendes Schreiben und die bestätigten fehlerhaften Eingaben nicht ab. Persistenz-, Wiederanlauf- und Lastnachweise fehlen teilweise. Eine grüne Suite erkennt Fehler im tatsächlich benutzten Pfad nicht zuverlässig.

#### Noch offen

Regressionstests zu den offenen Verträgen aus TS-10/11/12/13/14/15/19/20/21 ergänzen. Wiederverwendung desselben Testvolumes nach DB-Neuerstellung, repräsentative Last und Suchpläne sowie Goldantworten und erwartete Retrievaltreffer absichern.

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

**Status** · offen

**Schweregrad** · P1

**Problembeschreibung**

Der Reranker koppelt Dokumente und Modell-Scores per `zip`. Bei zu wenigen Scores fallen Dokumente still aus der Antwort. Die RAG-API prüft die vorhandenen Indizes, aber keine vollständige Zuordnung. Leere oder unvollständige Modellergebnisse können daher als reguläres Ergebnis erscheinen. Die Prüfung nicht endlicher Scores unterscheidet sich zwischen den RAG-Pfaden.

**Lösungsvorschlag**

Genau einen endlichen Score pro Eingabedokument verlangen. Unvollständige Zuordnung, überzählige Scores, ungültige Indizes und nicht endliche Scores in beiden RAG-Pfaden mit HTTP 502 im Schritt `reranking` abweisen. Leere Eingaben separat testen.

### TS-20 – Widersprüchlicher Vertrag für fehlenden Chunktext

**Status** · offen

**Schweregrad** · P1

**Problembeschreibung**

Die Vector-API akzeptiert fehlenden oder nullwertigen `chunktext` und kann `null` in Suchtreffern zurückgeben. Der RAG-Adapter verlangt pro Treffer einen String. Dadurch kann ein Treffer ohne Text im Schritt `retrieval` die gesamte Antwort mit HTTP 502 abbrechen, obwohl gültige Nachbartreffer vorliegen.

**Lösungsvorschlag**

Einen einheitlichen Vertrag für Schreiben, Suche und Kontextbildung festlegen, der vorhandene Datensätze berücksichtigt und gültige Nachbartreffer nutzbar hält. Gemischte Treffer und leeren Kontext gezielt testen.

### TS-21 – Überschrittene Chunkgröße bei langen Passagen

**Status** · teilweise behoben

**Schweregrad** · P2

**Problembeschreibung**

Absatz- und Satztrennung ohne Zeichen-Fallback kann bei langen, ungetrennten Passagen die konfigurierte Chunkgröße überschreiten. Die tatsächlichen Eingabelängen können dadurch von den Versuchsparametern abweichen. Betroffen sind [Import3](../Ingest/import3.py) und die [Pipeline-Beispielkonfiguration ohne Fallback](../Ingest/experiments/snowflake-arctic-embed-v2.json).

#### Noch offen

Für Strategien ohne Zeichen-Fallback eine explizite Größenregel festlegen. Bei Versuchen die tatsächlich erzeugten Chunklängen ausweisen.

**Lösungsvorschlag**

Für Strategien mit garantierter Obergrenze einen Fallback samt Regressionstest für ungetrennte Passagen vorsehen. Bei geänderter Verarbeitung eine eigene Set-ID gemäß R-01 verwenden.

### TS-22 – Veraltete Angaben in der Bausteinsicht

**Status** · behoben

**Schweregrad** · P2

**Problembeschreibung**

Die Bausteinsicht nennt noch `snowflake-arctic-embed2` als RAG-Standardfilter und beschreibt das Schreiben als Löschen und Einfügen. Der Code verwendet standardmäßig das Set `snowflake-arctic-embed2-v2` und einen atomaren Upsert. Die Übersicht führt die alte Abweichung der Defaults noch als offenen Punkt. Die Ergänzung zu TS-03 bezeichnet die Transaktions- und Poolnebenläufigkeit weiterhin als offen, obwohl TS-06 abgeschlossen ist. [Bausteinsicht](5-bausteinsicht.md)
