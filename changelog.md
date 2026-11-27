<!--
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
-->

# Changelog

Aus README und docs übernommene Änderungshistorie. Gleichdatierte Einträge folgen der umgekehrten Reihenfolge der dortigen Nachträge. Nicht datierbare Einträge stehen am Ende. Anleitungen: [README](README.md). Fachkonzepte: [Testkonzept](docs/8-1-testkonzept.md) und [Error-Handling](docs/8-3-error-handling.md).

## 2026-11-27

### RAG-Set-ID-Alias entfernt

`/process` und die Evaluationsendpunkte verwenden `embedding_set_id`. Der frühere Parameter `filter` führt vor Providerzugriff zu HTTP 400. Bei fehlender Set-ID greift das konfigurierte Standard-Set. Dokumentationsbeispiele und Vertragstests verwenden die aktuelle Benennung.

313 Unit-Tests und alle 21 Podman-Integrationstests einschließlich RAG, Reranker und Ollama bestanden.

### Alten Set-ID-Alias entfernt

Die Vector-API nimmt `embedding_set_id` entgegen und gibt diese Kennung in Einzelchunk- und Suchantworten aus. Der frühere Set-Parameter `embedding` führt auch bei Zählabfragen vor dem Datenbankzugriff zu HTTP 400. Die CLI verwendet `--embedding-set-id`. Interne Aufrufe und Tests verwenden den aktuellen Namen.

306 Unit-Tests und alle 21 Podman-Integrationstests einschließlich RAG, Reranker und Ollama bestanden. Das manuelle PowerShell-Skript wurde nicht gegen den laufenden Stack ausgeführt.

### Set-ID für Einzelabruf und Suche verpflichtend

TS-10 ist behoben. Die Vector-API verlangt bei Einzelabruf, `/find` und `/search` eine Set-ID und meldet bei fehlender Angabe HTTP 400 vor dem Datenbankzugriff. `GET /chunks` zählt weiterhin mit oder ohne Set-ID. Der Alias `embedding` bleibt gültig. Regressionstests prüfen dieselbe Chunk-ID in zwei Sets.

306 Unit-Tests und neun Standard-Podman-Integrationstests bestanden. Beim ergänzenden RAG-Lauf bestand der Ende-zu-Ende-Test. Zwei früh gestartete API-Tests meldeten Verbindungsabbrüche. Im Wiederholungslauf mit dem Ende-zu-Ende-Test zuerst bestanden alle drei RAG-Tests. Die übrigen optionalen Integrationsfälle wurden für diese Änderung nicht ausgeführt.

### RAG-Importpfad und Persistenz bei Container-Neuerstellung getestet

Der RAG-Ende-zu-Ende-Test importiert den Korpus über `Ingest.pipeline` mit Keyword-Anreicherung. Der PostgreSQL-Wiederanlauftest erstellt den Datenbankcontainer mit demselben eigenen Testvolume neu und prüft Abruf und Suche des zuvor gespeicherten Chunks. Beide Tests verwenden isolierte Podman-Ressourcen. TS-17 und das Testkonzept führen die verbleibenden Testlücken.

303 Unit-Tests und beide gezielt ausgeführten Podman-Integrationstests bestanden. Die übrigen Integrationsfälle wurden für diese beiden Teständerungen nicht erneut ausgeführt.

### Unterstützte Analyse- und Import-Einstiegspunkte festgelegt

TS-14 ist behoben. `analyze.py` bleibt die unterstützte Analyse-CLI. `Ingest/import3.py` bleibt bis zum persönlichen Test der Pipeline durch den Projektverantwortlichen als Fallback verfügbar. Die lokale Reranker-Demo und die explorative Vektoranalyse wurden nach `archive/` verschoben. Die Bausteinsicht zeigt die unterstützten Aufrufpfade.

303 Unit-Tests bestanden. Podman- und Modellintegrationstests wurden ausgelassen, da die Verschiebung keine aktiven Dienst- oder Importpfade ändert.

### Chunk-ID-Format als Architekturentscheidung dokumentiert

Kapitel 9.5 hält fest, warum Dateistamm und Chunknummer Teil der ID sind. TS-23 ist als abgelehnt vermerkt. Die Änderungen betreffen ausschließlich die Dokumentation.

### Leere Chunker-Ausgaben vor der Nummerierung entfernt

`make_chunks` filtert `None`, leere Strings und Texte aus ausschließlich Leerzeichen, LF oder CR. Gültige Chunks werden unverändert und lückenlos nummeriert. Bleibt kein Chunk übrig, bricht die Verarbeitung mit dem bestehenden Eingabefehler ab. Die Prüfung gespeicherter Chunk-Artefakte verwendet dieselbe Definition.

303 Unit-Tests und im gemeinsamen Podman-Lauf 7 Integrationsprüfungen für Migrationen und Importpipeline einschließlich Ollama bestanden. Zwei frühere Läufe mit der Importpipeline als erstem Testmodul meldeten beim ersten Schreibzugriff einen Verbindungsfehler. RAG- und Reranker-Tests wurden für diese Importänderung nicht ausgeführt.

### Gültigen Chunktext an der laufenden Vector-API geprüft

`POST /vectors` lieferte HTTP 201. Das Zurücklesen per Chunk-ID und Set-Kennung bestätigte den exakten Text einschließlich Umlaut, Leerzeichen, LF und CR. `DELETE /chunks` meldete genau einen gelöschten Testeintrag. Der anschließende Abruf lieferte HTTP 404.

### Vector-API mit Chunktext-Validierung ausgerollt

Der Container `vector-api` läuft im bestehenden Pod mit Image `14c79543895a`. `GET /health/ready` lieferte HTTP 200. `POST /vectors` lieferte für fehlenden Chunktext, `null`, einen leeren String, reine Leerzeichen und eine Mischung aus Leerzeichen, LF und CR jeweils HTTP 400 mit Problem Details für `/chunktext`. Der vorherige Container bleibt gestoppt unter `vector-api-before-ts20-20261127-103748` verfügbar.

### Migration 003 auf der laufenden Datenbank angewendet

PostgreSQL hat Migration 003 auf `vectordb/vector_db` mit `COMMIT` abgeschlossen. `NOT NULL` und der validierte Check-Constraint `vectors_chunktext_nonblank` sind aktiv. Alle 11.243 Zeilen erfüllen die Regel. Direkte Inserts und Updates mit `NULL`, leerem String, reinen Leerzeichen und einer Kombination aus Leerzeichen, LF und CR wurden jeweils abgewiesen. Die Prüftransaktion wurde zurückgerollt.

Backup vor der Migration: `backups/20261127-103511-000482.dump`. Nach einer Podman-Transportmeldung beim Migrationslauf wurde das Archiv erneut mit `pg_restore --list` geprüft. Es enthält den Tabellendateneintrag für `public.vectors`.

### Pflichtregel für Chunktext implementiert

TS-20. PostgreSQL weist bei Inserts und Updates `NULL`, leere Strings und reine Kombinationen aus Leerzeichen, LF und CR ab. Die Vector-API meldet ungültigen oder fehlenden Chunktext mit HTTP 400 vor dem Datenbankzugriff. Migration 003 prüft den Bestand transaktional und bricht bei ungültigen Werten ab. Die laufende Datenbank wurde für diese Änderung nicht migriert.

302 Unit-Tests und 9 Standard-Podman-Integrationstests bestanden. Die Migrationstests prüften auch das Zurückrollen bei leeren Bestandswerten, das Ablehnen ungültiger Inserts und Updates sowie die Backup-Wiederherstellung. Die 12 optionalen Tests für RAG, Reranker und Ollama wurden für diese Schreibvalidierung nicht aktiviert.

### Datenbestand auf leere Chunktexte geprüft

Eine lesende PostgreSQL-Abfrage über alle 11.243 Zeilen in `vector_db.public.vectors` fand keine `NULL`-Werte, leeren Strings oder Texte, die ausschließlich aus Leerzeichen, LF oder CR bestehen.

### Vector-API in der vollständigen Podman-Suite geprüft

`python -B -m pytest -c tests/pytest.ini tests/podman --all -ra --tb=short` ergab 20 bestandene Tests ohne Überspringen in 284,81 Sekunden. Enthalten waren direkte Vector-API-Aufrufe, Migrationen, Import3 und Importpipeline, Ollama, die RAG-API und alle drei RAG-Ende-zu-Ende-Fälle. Der isolierte Teststack verwendete für die Vector-API dieselbe Image-ID `d69ad515b1424` wie der laufende Dienst und eigene Testdaten.

### Aktuelle Vector-API im laufenden Podman-System gestartet

Der ältere Container `vector-api-before-ts06` belegte im gemeinsamen Pod Port 5500. Nach seinem Stopp startete `vector-api` mit dem aktuellen lokalen Image `d69ad515b1424`. `/health/ready` meldete Bereitschaft. Die Hannibal-Anfrage lieferte über `/evaluate/retrieve` dieselben fünf Chunk-IDs in derselben Reihenfolge. Der alte Container bleibt gestoppt verfügbar.

### Treffer der Hannibal-Anfrage geprüft

Eine Wiederholung mit denselben Suchparametern lieferte fünf Treffer und dieselbe Reranking-Auswahl wie der vorherige Lauf. `pg3062-659` blieb auf Rang 1 und enthielt einen indirekten Hinweis auf den für Rom günstigen Friedensschluss. Die fünf Treffer enthielten weder die Entscheidungsschlacht noch die konkreten Friedensbedingungen. Die erste generierte Antwort ließ den im Kontext vorhandenen Hinweis auf den Friedensschluss aus, die Wiederholung griff ihn auf.

### /process im laufenden Podman-System geprüft

Die Frage „Welche Rolle spielte Hannibal im Zweiten Punischen Krieg, und wie endete der Krieg?“ ergab `status=ok`. Die Cosine-Suche lieferte fünf Treffer, der Reranker `cross-encoder/ms-marco-MiniLM-L6-v2` wählte drei Chunks für die Antwortgenerierung aus (`pg3062-659`, `pg3062-487`, `pg3062-505`). Die Pipeline dauerte 22,79 Sekunden, davon 0,11 Sekunden für Reranking und 20,36 Sekunden für Generierung. Die Antwort beschrieb Hannibals Rolle, beantwortete den Ausgang des Krieges jedoch nur unvollständig.

### Score-Validierung im laufenden Podman-System ausgerollt

RAG-API und Reranker laufen mit den Images `54509badc90a` und `0a163e95549a`. Beim Standardbuild des Rerankers blieb der Modell-Download hängen. Das ausgerollte Image übernimmt Modellgewichte und Abhängigkeiten aus dem bisherigen Image und enthält den aktuellen Anwendungscode. Ports, Netzwerk und GPU-Konfiguration wurden übernommen. Die vorherigen Container sind gestoppt und unter Namen mit dem Suffix `before-ts19-20261127-100919` für eine Rückkehr verfügbar.

Der Reranker meldete über `/health` das geladene Standardmodell. Ein Aufruf von `/evaluate/rerank` auf der laufenden RAG-API bewertete zwei Passagen und lieferte bei `top_k=1` einen Treffer mit endlichem Score. Vector-API und Datenbank wurden bei der Umschaltung nicht angefasst.

### Podman-Integration für RAG und Reranker nachgeholt

Mit erweiterten Berechtigungen konnte Podman den lokalen Verbindungsschlüssel verwenden. Der isolierte Lauf mit `--include-rag --include-reranker` ergab 12 bestandene Tests und acht übersprungene Ollama-Fälle. Die drei RAG-Ende-zu-Ende-Fälle wurden mit zusätzlichem `--include-ollama` gezielt nachgeholt und bestanden. Die übrigen fünf Ollama-Fälle für Import und Embeddings waren außerhalb dieses Prüfumfangs.

### Score-Validierung beim Reranking umgesetzt

Der Reranker prüft Modellscores vor der Sortierung. Beide RAG-Pfade prüfen die Scores aller zurückgegebenen Treffer vor `top_k` und melden ungültige Scores mit HTTP 502 im Schritt `reranking`. TS-19 ist behoben. Die akzeptierte Abweichung der Score-Anzahl nach R-04 gilt weiter.

296 Unit-Tests bestanden. Die Regressionstests decken unter anderem `NaN` hinter der `top_k`-Grenze in beiden RAG-Pfaden, abweichende Score-Anzahlen und leere Eingaben ab. Die Podman-Integration entfiel wegen verweigerten Zugriffs auf den Verbindungsschlüssel. `git diff --check` geprüft.

### R-04 um überzählige Scores erweitert

R-04 umfasst für das Standardmodell auch überzählige Scores. TS-19 führt die bereits vorhandene Prüfung ungültiger und doppelter Indizes im gemeinsamen RAG-Adapter auf. Offen bleiben die Prüfung nicht endlicher Scores und der separate Test leerer Eingaben.

Linkziele und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Offene Validierungsarbeiten zu TS-19 präzisiert

Die Prüfung auf fehlende Scores entfällt wegen des akzeptierten Risikos R-04. TS-19 bleibt für überzählige Scores, ungültige oder doppelte Indizes und nicht endliche Scores offen. Der separate Test leerer Eingaben bleibt vorgesehen.

`git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Fehlende Reranker-Scores als Risiko akzeptiert

Kapitel 11.1 erfasst den möglichen stillen Trefferverlust beim Betrieb mit dem Standardmodell als R-04. R-04 und TS-19 sind wechselseitig verlinkt.

Linkziele und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### TS-19 mit dem Standardmodell geprüft

Der lokale Flask-Testclient prüfte `cross-encoder/ms-marco-MiniLM-L6-v2` mit Sentence Transformers 4.1.0 und Transformers 4.53.0 auf CUDA. Bei 1, 5, 31, 32, 33, 65 und 129 Dokumenten sowie bei parallelen Anfragen waren alle Indizes vorhanden und alle Scores endlich. Die Eingaben umfassten Duplikate, mehrere Schriftsysteme und Texte oberhalb des Tokenlimits. Auch eine lange Anfrage mit langem Dokument lieferte einen Score. Leere Eingaben lieferten die erwartete leere Liste.

Gezieltes Kürzen der echten Modellausgabe auf drei bzw. null Scores für fünf Dokumente bestätigte den stillen Trefferverlust mit HTTP 200. Ein simulierter Speichermangel im zweiten Batch ergab HTTP 500 ohne Teilergebnis. Der Podman-Lauf entfiel wegen verweigerten Zugriffs auf den Verbindungsschlüssel.

### Restarbeiten im Schuldenregister präzisiert

TS-05 bleibt für den regulären Import über die Pipeline behoben. Import3 bleibt bis zum persönlichen Test der Pipeline durch den Projektverantwortlichen als Fallback verfügbar. Das Importkonzept hält diese Rolle fest. Bei TS-11, TS-12 und TS-15 sind die Anpassung des Analyseclients, `NUM_RESULTS` und die Ergänzung von SciPy aus den Restarbeiten gestrichen.

Geänderte Abschnitte und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Stand der technischen Schulden geprüft

TS-01 bis TS-26 mit Quellcode, Konfiguration und Testbestand abgeglichen. TS-05 ist für die Importpipeline umgesetzt. Der eigenständige Import3-Einstieg bereinigt kürzere Neuimporte weiterhin nicht und meldet Chunkfehler nicht im Rückgabestatus. Bei TS-11 entfällt die Anpassung des Analyseclients, bei TS-12 ist NUM_RESULTS in Verwendung und bei TS-15 besteht für die aktuelle Testsuite kein erkennbarer SciPy-Bedarf. Die übrigen Restarbeiten dieser Einträge bestehen fort.

273 containerfreie Unit-Tests bestanden. Ein isolierter Import3-Aufruf mit Testdoubles bestätigte das Weiterlaufen nach einem Chunkfehler ohne Fehlerstatus. Ein Chunking-Aufruf ohne Zeichen-Fallback erzeugte bei einer Zielgröße von 1000 einen Chunk mit 1500 Zeichen. Podman- und Ollama-Integrationstests wurden für diesen Abgleich nicht erneut ausgeführt. Das Schuldenregister wurde bei dieser Bestandsaufnahme nicht geändert.


### Pflegevorgaben für die arc42-Kapitel 1 bis 11 vereinheitlicht

Die Architekturdateien haben ausgeblendete Zweckbeschreibungen und kapitelbezogene Pflegevorgaben. Maßstab sind die [arc42-Dokumentation](https://docs.arc42.org/home/) und das Praxisbeispiel [DokChess](https://www.dokchess.de/). Das neue [Kapitel 10](docs/10-qualitaetsanforderungen.md) bündelt die bisherigen Prüfszenarien aus Kapitel 1. Kapitel 1 behält die Qualitätszielübersicht und verlinkt die Szenarien.

Pflegeblöcke, lokale Linkziele und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Pflegevorgaben für Kapitel 4 ergänzt

Ein ausgeblendeter Anweisungsblock begrenzt die Lösungsstrategie auf grundlegende Entscheidungen nach arc42, verlangt kurze Begründungen und verweist für Details auf die Fachkapitel. Änderungshistorie sowie Prüf- und Ausrollnachweise gehören in das Changelog. `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Schuldenregister um Befunde zu Verantwortlichkeiten ergänzt

TS-23 bis TS-26 erfassen in absteigender Priorität für die Erweiterbarkeit die Kopplung der Dokumentzugehörigkeit an Chunk-IDs, verteilte RAG-Kontextregeln, die Verflechtung der Importorchestrierung und den SQL-nahen Vector-Suchhandler. Der datenbanknahe Vektorvertrag und der Modelllade- und Health-Lebenszyklus sind bereits in TS-11 und TS-13 erfasst.

Quellstellen, Statusfelder, lokale Linkziele und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Separation of Concerns als Entwurfsprinzip präzisiert

Kapitel 4 beschreibt die Trennung unabhängig änderbarer Belange zwischen Diensten und innerhalb von Bausteinen. Die Bausteinsicht erläutert die konkreten Zuständigkeiten, das Import- und das Fehlerkonzept zeigen Anwendungen des Prinzips. Lokale Linkziele und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Entwurfsprinzipien in der Lösungsstrategie benannt

Kapitel 4 beschreibt den DDD-orientierten Dienstschnitt, Single Responsibility und Separation of Concerns im bestehenden Abschnitt zu Verantwortlichkeiten. `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Lösungsstrategie an den Qualitätszielen ausgerichtet

Kapitel 4 fasst Dienstschnitt, vergleichbare Experimente, Testbarkeit und Plattformkompatibilität zusammen und verweist auf die zugehörigen Details. Kapitel 1 und 3 beschreiben die optionale Einbindung des Rerankers in die RAG-API.

Der Reranking-Standardwert und die Aufrufbedingung wurden mit der Implementierung abgeglichen. Lokale Linkziele und `git diff --check` wurden geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Lösungsstrategie aus Bausteinsicht und Fehlerkonzept verlinkt

Beide Kapitel verweisen auf den Abschnitt „Verantwortlichkeiten und Abhängigkeiten“. Die Linkziele und `git diff --check` wurden geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Lösungsstrategie zu Architekturgrenzen ergänzt

Kapitel 4 beschreibt die fachlichen Zuständigkeiten, die Trennung von Verarbeitung und Transport sowie die Voraussetzungen für gemeinsam genutzten Code. Es verweist auf Bausteinsicht und Fehlerkonzept.

Lokale Links und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

## 2026-11-26

### Gold-Vergleich nach vollständigem Stack-Update wiederholt

`analyze.py --compare-gold` lief mit derselben Frage gegen die aktualisierten Dienste erfolgreich durch. Trefferreihenfolge und alle ausgegebenen Distanzwerte stimmten mit dem vorherigen Live-Test überein. Die generierte Antwort enthielt dieselben Kernaussagen zu Vesta und Italus mit abweichendem Wortlaut.

### Vector-API und Reranker im laufenden Stack aktualisiert

`vector-api` läuft mit Image `d69ad515b142` im bestehenden `vectorpod`. `reranker` läuft mit Image `28a1464324b5` auf Port 5000 mit den bisherigen WSL-Bind-Mounts und der Geräteoption. Die vorher aktiven Container bleiben gestoppt unter `vector-api-before-ts06` und `reranker-before-rollout-20261126` verfügbar. Der bereits gestoppte frühere `vector-api` wurde als `vector-api-inactive-before-rollout-20261126` erhalten.

Vector-Liveness und -Readiness, Reranker-Health und ein direkter Reranking-Aufruf waren erfolgreich. Eine Anfrage an `/process` lieferte fünf Retrievaltreffer, zwei durch den Reranker ausgewählte Chunks und eine generierte Antwort. PostgreSQL läuft weiter mit demselben Container und `pgvector-data`. Alle vier Volumes sowie 11.243 Chunks mit identischen Anzahlen je Embedding-Set waren nach dem Austausch vorhanden.

### RAG-Image ausgerollt und Gold-Vergleich im laufenden Stack geprüft

Die API-Images `rag-api:local` (`e298e575d464`), `vectorapi:local` (`d69ad515b142`) und `reranker:local` (`28a1464324b5`) wurden neu gebaut. Der eigenständige RAG-Container auf Port 5600 wurde ersetzt. Der bisherige RAG-Container bleibt gestoppt unter `rag-api-before-analysis-20261126` verfügbar. Die laufenden Vector- und Reranker-Container verwenden ihre bisherigen Images.

`analyze.py --compare-gold` lief gegen den bestehenden Stack erfolgreich durch. Der Aufruf lieferte fünf Treffer, eine generierte Antwort und für den Gold-Chunk eine Cosinus-Ähnlichkeit von 0,620555 sowie einen euklidischen Abstand von 0,871143. PostgreSQL blieb am Volume `pgvector-data`. Die 11.243 Chunks und ihre Verteilung auf vier Embedding-Sets stimmten vor und nach dem Austausch überein.

### Analyse auf die RAG-Evaluationsendpunkte umgestellt

`analyze.py` ruft Retrieval und Generierung über HTTP auf. Die RAG-API liefert auf Anforderung Cosinus-Ähnlichkeit und euklidischen Abstand je Treffer zusätzlich zur Rankingdistanz. `--compare-gold` sendet den vollständigen Gold-Chunk als Referenztext. Die CLI-Aufrufe verwenden denselben HTTP-Transport.

273 Unit-Tests, 12 isolierte Podman-Integrationstests und der gezielte Evaluations-E2E-Test mit echtem Ollama-Referenzembedding bestanden. Die übrigen optionalen Ollama-Tests wurden für diese Änderung ausgelassen.

### Dienstfehler an der HTTP-Grenze übersetzt

Ergebnisvalidierung, Provideraufrufe, Datenbanktransaktionen und Modellladen melden Fehler durch ursachenspezifische Python-Ausnahmen. Die Flask-Apps ordnen ihnen die bestehenden HTTP-Statuscodes und Problemtypen zu. Dieselbe Ergebnisprüfung wird für Evaluationsanfragen, Retrievalantworten und die CLI verwendet.

262 Unit-Tests und 11 isolierte Podman-Integrationstests mit Vector, RAG und Reranker bestanden. Acht optionale Tests mit echtem Host-Ollama wurden ausgelassen. Die Providerfehler wurden mit Testdoubles geprüft.

### Eingabevalidierung an die HTTP-Endpunkte verlegt

RAG, Vector und Reranker prüfen ihre Eingaben am jeweiligen Endpunkt. Die gemeinsamen Flask-Handler erzeugen weiterhin Problem Details und korrelieren Requests. RAG und Vector nutzen gemeinsame, Flask-freie Prüfungen für den Vector-Suchvertrag. Die Vector-API initialisiert den Pool erst beim Transaktionsbeginn. Ungültige Abfragen werden auch mit `HEAD` vor der Poolinitialisierung mit HTTP 400 abgewiesen.

258 Unit-Tests und 11 isolierte Podman-Integrationstests mit Vector, RAG und Reranker bestanden. Acht optionale Tests mit echtem Host-Ollama wurden ausgelassen, da der Refactor die HTTP-Validierung vor dem Providerzugriff betrifft.

## 2026-11-25

### Fachkapitel mit ausgeblendeten Pflegevorgaben versehen

Bausteinsicht, Laufzeitsicht, Verteilungssicht und Testkonzept verlangen in ausgeblendeten Pflegevorgaben, gültige Änderungen in die Fachabschnitte einzuarbeiten und Historie ausschließlich im Changelog zu führen.

### Laufzeit- und Verteilungssicht auf den aktuellen Stand konsolidiert

Reranking, Laufzeitmessung und schrittweise Evaluation sind in die Fragebeantwortung integriert. Die Laufzeitsicht beschreibt die Pipeline mit Teilimport und Bereinigung. Die Verteilungssicht beschreibt gemeinsamen und separaten Podman-Betrieb sowie die bedarfsgesteuerte Datenbankverbindung. Datierte Betriebs- und Diagnoseangaben entfallen in den Fachkapiteln.

Die frühere Laufzeitsicht dokumentierte eine Diagnose, bei der `host.containers.internal` im Container auf `169.254.1.2` zeigte und Windows-Ollama über den WSL-Gateway `172.24.64.1` erreichbar war. Diese Adressen waren damalige Beobachtungen.

Lokale Dokumentlinks und `git diff --check` geprüft. Für die reine Dokumentationsänderung wurden keine Anwendungstests ausgeführt.

### Testkonzept und Bausteinsicht auf den aktuellen Stand konsolidiert

Gültige Nachträge sind in die Abschnitte zu Import, RAG, Vector-API, Teststufen und Prüfungen integriert. Datierte Nachträge und historische Prüfvermerke entfallen in den Fachkapiteln. Die Bausteinsicht beschreibt den aktuellen Set-Default, Upserts sowie Pool und Readiness. TS-22 ist behoben.

Lokale Dokumentlinks und `git diff --check` geprüft. Für die reine Dokumentationsänderung wurden keine Anwendungstests ausgeführt.

### Ausgeblendete Pflegevorgaben in AGENTS.md verankert

Agenten prüfen vor Änderungen an Markdown-Dateien den Quelltext auf ausgeblendete Pflegevorgaben und beachten diese bei der Bearbeitung.

### Pflegevorgaben in der Markdown-Vorschau ausgeblendet

Die YAML-Pflegevorgaben im Changelog und im Schuldenregister stehen in HTML-Kommentaren. Die Blöcke bleiben im Quelltext lesbar und sind weiterhin als YAML parsebar.

### Schuldenregister auf den aktuellen Status umgestellt

Kapitel 11.2 verwendet vier verbindliche Statuswerte. Teilweise behobene Einträge führen die verbleibende Arbeit unter „Noch offen“. Die ursprünglichen Befunde bleiben erhalten. Pflegevorgaben stehen im Frontmatter. Änderungs-, Prüf- und Ausrollhistorie gehören in dieses Changelog.

YAML-Frontmatter, Statusstruktur aller 22 Einträge, lokale Linkziele und `git diff --check` geprüft. Anwendungstests entfallen bei dieser Dokumentationsänderung.

### Neue Vector-API im lokalen Podman-Stack ausgerollt

`vector-api` läuft im bestehenden `vectorpod` mit dem neu gebauten Image `localhost/vectorapi:local` (`1b4b486a630a`). PostgreSQL und das bestehende Volume wurden für den Austausch weiterverwendet. Der zuvor laufende API-Container `vector-api-before-ts08-20261122` bleibt gestoppt für einen Rückwechsel erhalten.

Live-Prüfung erfolgreich. `GET /health/ready` meldet `ready`, `DELETE /chunks` weist eine ungültige Bereichsgrenze mit HTTP 400 zurück und `GET /chunks` meldet vor und nach dem Austausch 11.243 Chunks. Die Prüfung hat keine Chunks gelöscht. Eine Datenbankmigration war nicht erforderlich.

### Risiko und Architekturentscheidung im Importkonzept verlinkt

Kapitel 8.4.7 verweist beim Datenstand nach einem Importabbruch direkt auf R-03 und Architekturentscheidung 9.4. Reine Dokumentationsänderung.

### Importabbrüche als akzeptiertes Risiko dokumentiert

R-03 beschreibt den gemischten Chunkbestand bis zur erfolgreichen Fortsetzung und Bereinigung. Architekturentscheidung 9.4 hält Eventual Consistency als implementiertes Verhalten fest und begründet den Verzicht auf automatische Sicherungen vor Wiederholungsimporten. Reine Dokumentationsänderung.

### Handler der Bereichslöschung umbenannt

Der Flask-Handler für `DELETE /chunks` heißt `delete_chunks`. Die Eingabevalidierung verwendet denselben Endpunktnamen.

252 Unit-Tests und acht Podman-Standardintegrationstests bestanden. Nach Verbindungsabbrüchen beim Start des gezielten Vector-API-Tests lief die Standardintegration erfolgreich. Die optionalen Ollama-, RAG- und Reranker-Tests wurden für die interne Umbenennung ausgelassen.

### Löschroute auf `DELETE /chunks` umbenannt

Die Pipeline und die Testaufrufer verwenden den Pluralpfad für die Bereichslöschung. `GET /chunks` zählt weiterhin die Chunks im gewählten Set. Die Schnittstellendokumentation zeigt den neuen Pfad.

252 Unit-Tests und alle 19 Podman-Integrationstests bestanden.

### Chunks über einen Nummernbereich löschen

`DELETE /chunk` löscht Chunks eines Dokuments im Zielset mit einer inklusiven Untergrenze `from` und optionaler inklusiver Obergrenze `to`. Die Pipeline übergibt für die abschließende Bereinigung die Gesamtzahl plus eins als Untergrenze. Der bisherige Aufruf mit `chunk_id` und der Endpunkt `POST /vectors/trim` entfallen. Projektaufrufer und Schnittstellendokumentation sind angepasst.

252 Unit-Tests und alle 19 Podman-Integrationstests einschließlich Ollama, RAG und Reranker bestanden.

### Import nach Abbruch mit `--start` fortsetzen

`Ingest.pipeline` erzeugt keinen Laufbericht mehr. Die Fehlerausgabe nennt die erste unbestätigte Chunknummer und den passenden `--start`-Wert. Nach einem Fehler bei der Bereinigung gibt sie die Nummer nach dem letzten Chunk aus. Einzelwrites und die abschließende Bereinigung bleiben Teil des Imports.

242 Unit-Tests und 12 isolierte Podman-Integrationstests einschließlich Ollama bestanden. Im ersten, auf die Importdatei begrenzten Integrationslauf scheiterte der erste API-Zugriff mit einem Verbindungsfehler. Im anschließenden vollständigen Podman-Lauf mit Ollama bestand derselbe Test. Die sechs optionalen RAG- und Reranker-Tests lagen außerhalb des Änderungsumfangs.

### TS-05 auf Einzelwrites und Wiederaufnahme am Chunk umgestellt

`Ingest.pipeline` schreibt jeden Chunk direkt und hält nach der Bestätigung die nächste Nummer im Laufbericht fest. `--resume` verwendet diese Nummer. `--start` startet einen neuen Lauf mit einem vorhandenen Präfix. Nach dem letzten bestätigten Chunk löscht die Vector-API überzählige IDs desselben Dokuments im Zielset. Der Zwischenstand nach einem Fehler ist im Sinne von Eventual Consistency akzeptiert. Der vorherige atomare Entwurf mit Migration 003 wurde durch diesen Ablauf ersetzt.

Prüfung mit 243 Unit-Tests und 12 isolierten Podman-Integrationstests einschließlich Ollama. Der Integrationstest prüft den sichtbaren Datenstand nach einem Abbruch, die Wiederaufnahme, den unveränderten Präfix und die Bereinigung. Sechs optionale RAG- und Reranker-Tests wurden ausgelassen, da sich die Änderung auf Import und Vector-API beschränkt.

### TS-05 für die Importpipeline abgeschlossen

`Ingest.pipeline` veröffentlicht einen vollständigen Chunk-Satz pro Dokument und Set in einer Datenbanktransaktion. Die Transaktion entfernt überzählige kanonische Chunks und speichert einen Freigabebeleg. Nach einer verlorenen Antwort bestätigt derselbe Batch mit derselben Lauf-ID den ursprünglichen Commit. Der Laufbericht im Format 2 unterstützt `--resume` mit geprüften Zwischenartefakten und `--continue-on-error` bei isolierten Chunkfehlern. Die Anleitungen beschreiben Migration 003 mit Backup und die manuelle Zuordnung alter Erste-Punkt-IDs.

Prüfung mit 243 Unit-Tests und 13 Podman-Integrationstests einschließlich Ollama, kürzerem Neuimport, Transaktionsrollback, wiederholter Freigabe und Backup-Restore. Sechs optionale RAG- und Reranker-Tests wurden ausgelassen, da die Änderung den Import und die Vector-API betrifft. Migration und Bereinigung wurden ausschließlich in Testressourcen geprüft.

### Zweckkommentare im Importmodul ergaenzt

Acht Python-Dateien in Ingest und 23 Funktionen mit mehr als fuenf Quellzeilen erhielten Zweckkommentare. Die Python-Syntaxbaeume blieben identisch und **238 Unit-Tests** bestanden. Integrationstests wurden fuer die reine Kommentaraenderung nicht erneut ausgefuehrt.

### Alte Keyword-Experimente entfernt

Keyword-Experimente laufen ueber `Ingest.enrich`. Die zwei alten manuellen Skripte und ihre Verweise wurden entfernt.

Pruefung: **238 Unit-Tests** und git diff --check erfolgreich. Integrationstests wurden fuer die Entfernung der ungenutzten Skripte nicht erneut ausgefuehrt.

### Keyword-Anreicherung separat ausfuehrbar

`Ingest.enrich` verarbeitet vorhandene Chunk-Artefakte mit waehlbaren Ollama-Modellen und eingebauten oder eigenen versionierten Systemprompts. Das Ergebnis enthaelt Keywords, den gemeinsamen Chunktext und Anfrage-, Providerzeit- und Tokenmetriken. Embedding und Speicherung erfolgen erst bei einem gesonderten Import aus `enriched.json`.

Pruefung: **238 Unit-Tests** und **3 Import-Pipeline-Integrationstests** mit Ollama und isoliertem Podman-Stack bestanden. Der erste Integrationsversuch erreichte die gestoppte Podman-Machine nicht. Nach deren Start war der gezielte Lauf erfolgreich. Weitere Integrationstests wurden fuer den auf Ingest begrenzten Umfang nicht erneut ausgefuehrt.

## 2026-11-24

### Alle Podman-Integrations- und Ende-zu-Ende-Tests ausgefuehrt

`python -m pytest -c tests/pytest.ini tests/podman --all -v`: **16 passed, 1 failed in 138.44s**. Alle drei RAG-E2E-Tests bestanden. Im separaten Import3-Test beendete sich der Ollama-Embeddingprozess bei der CUDA-Initialisierung (Exitstatus 0xc0000409). Der isolierte Wiederholungslauf dieses Tests mit `--include-ollama` bestand (**1 passed in 46.94s**). Kein erneuter Gesamtlauf.

Die Unit-Suite war nicht Teil des Auftrags. Die Teststaende nutzten isolierte Podman-Ressourcen.

### PostgreSQL per SQL vom Windows-Host geprueft

Ein temporaerer psycopg-Client erreichte vector_db direkt auf 127.0.0.1:5432. Eine SELECT-Abfrage bestaetigte transaction_read_only=on sowie 11243 Zeilen in vectors. Die Transaktion wurde zurueckgerollt und der temporaere Client anschliessend entfernt. Keine Daten geaendert.

### Windows-Zugriff auf PostgreSQL ueber IPv4 dokumentiert

Host-Aufrufe mit psql verwenden 127.0.0.1:5432. Verteilungssicht und Anleitungen benennen dieselbe Adresse. Die bestehenden Migrations- und Testaufrufe laufen im DB-Container beziehungsweise ueber dessen lokale Verbindung.

Pruefung: TCP zu 127.0.0.1:5432 sofort erfolgreich, Verbindungsversuch zu ::1 nach rund 2 Sekunden abgelehnt. Windows-psql war nicht im PATH. Unit- und Podman-Suite wurden fuer die reine Dokumentationsaenderung nicht erneut ausgefuehrt.

### Windows- und Testaufrufe der lokalen APIs auf IPv4 umgestellt

Die Windows-Aufrufe fuer Vector-API, RAG und Reranker sowie die HTTP-Aufrufe an dynamische Podman-Testports verwenden 127.0.0.1. Die Dokumentation und die Fixture-Erwartungen sind angepasst. Ollama-Adressen und Import3 blieben unveraendert.

Pruefung: Gesamtsuite mit --all **253 passed in 142.28s**, einschliesslich der isolierten Podman- und Ollama-Tests. CLI-Standardadresse, PowerShell-Syntax und git diff --check ebenfalls geprueft.

### Pipeline nutzt IPv4 fuer die lokale Vector-API

Der Standard fuer IMPORT_VECTOR_URL lautet http://127.0.0.1:5500/vectors. Die Ingest-Anleitung dokumentiert die lokal gemessene Wartezeit beim IPv6-Verbindungsversuch ueber localhost. Import3 behaelt seine bisherige Adresse.

Pruefung: **236 Unit-Tests** bestanden, einschliesslich der Standardadresse ohne Umgebungsvariable. Podman-Integration nicht erneut ausgefuehrt, da ihre Testfaelle die Vector-Adresse explizit setzen.

### Fehlerhaften Altimport entfernt

Der fehlerhafte Altimport und seine Verweise wurden entfernt. Der Regressionstest fuer snowflake-arctic-embed-v1 vergleicht die Chunkgrenzen direkt mit dem LangChain-Splitter. Die Versuchskonfiguration bleibt erhalten.

Pruefung: **236 Unit-Tests** und git diff --check erfolgreich. Podman- und Ollama-Integration wurden nicht erneut ausgefuehrt, da die aktiven Importpfade unveraendert blieben.

### Import-Helfer nach Ingest/utils verschoben

Chunking, Keyword-Aufbereitung und Gateway liegen in Ingest/utils. Pipeline, Import3, Tests und Dokumentationslinks verwenden die neuen Modulpfade.

Pruefung: **236 Unit-Tests** und **7 betroffene Podman-Integrationstests** fuer Import, Ollama und RAG bestanden. CLI-Hilfen fuer Import3 als Skript und Modul sowie Pipeline erfolgreich. Weitere Integrationstests wurden fuer die Modulverschiebung nicht erneut ausgefuehrt.

### Pipeline-Anleitung nach Ingest verschoben

Ingest/README.md beschreibt den Dokumentimport, die Beispielkonfigurationen, die Wiederverwendung von Artefakten und die Diensteinstellungen. Das Projekt-README verweist auf die Anleitung.

Pruefung: Lokale Links, der dokumentierte Chunking-Aufruf, die Pipeline-CLI-Hilfe und git diff --check erfolgreich. Unit- und Integrationstests wurden fuer die reine Dokumentationsaenderung nicht erneut ausgefuehrt.

### Neue Set-IDs im isolierten Teststack geprueft

Die drei unveraenderten Experimentdateien importierten early_rome.txt mit echten Ollama-Modellen in test-recursive-1000, snowflake-arctic-embed-v1 und snowflake-arctic-embed-v2. Einzelabruf und Vektorsuche ueber die Vector-API lieferten den Chunk jeweils mit der angefragten Set-ID. Die drei frueheren Kennungen waren im Testvolume leer.

Gezielter Podman-/Ollama-Lauf: **1 passed, 2 deselected in 48.47s**. Der Stack verwendete ein eigenes Testvolume. Bestandsdaten und import3.py blieben unveraendert. Weitere Tests wurden fuer die gezielte Integrationspruefung nicht erneut ausgefuehrt.

### Set-IDs an Experimentnamen angeglichen

Die drei Pipeline-Beispiele verwenden jetzt test-recursive-1000, snowflake-arctic-embed-v1 und snowflake-arctic-embed-v2 als Set-IDs. Die Set-Zuordnung und die Retrieval-Anleitung sind aktualisiert. Bestehende Daten und der Import3-Standard wurden nicht migriert.

Pruefung: Alle drei Konfigurationen geladen und Set-IDs mit den Dateinamen abgeglichen; **11 Pipeline-Unit-Tests** bestanden. Weitere Tests wurden fuer die reine Kennungsaenderung nicht erneut ausgefuehrt.

### Importexperimente umbenannt

Die Konfigurationsdateien und ihre Namensfelder heissen jetzt test-recursive-1000, snowflake-arctic-embed-v2 (Import3) und snowflake-arctic-embed-v1 (LangChain-Standardchunking). Embedding-Set-IDs und Verarbeitungseinstellungen bleiben erhalten. Tests und aktuelle Dokumentation verwenden die neuen Dateinamen.

Pruefung: **236 Unit-Tests** und der gezielte Ollama-/Podman-Kompatibilitaetstest (**1 passed, 1 deselected**) bestanden. Weitere Integrationstests wurden bei der Umbenennung nicht erneut ausgefuehrt.

### Import3-Kompatibilitaet mit echten Ollama-Modellen geprueft

Der neue Vergleichstest importiert early_rome.txt mit import3.py und der Pipeline-Konfiguration import3-compatible.json in getrennte Sets desselben isolierten Podman-Teststacks. Die Keyword-Praefixe aus gemma3:4b waren exakt gleich und die maximale Komponentenabweichung der gespeicherten, normalisierten 1024-dimensionalen snowflake-arctic-embed2-Vektoren war 0.

Gezielter Vergleich: **1 passed, 1 deselected in 41.58s**. Testressourcen wurden ueber die Testfixture bereinigt. Weitere Tests wurden nicht erneut ausgefuehrt, da lediglich der Vergleichstest und die Dokumentation ergaenzt wurden. Bestandsdaten und import3.py blieben unveraendert.

### Import3-Verarbeitung als Pipeline-Versuch

Der Zeichen-Fallback bleibt Standard und kann in der Trennzeichenliste entfallen. Die Beispielkonfiguration import3-compatible.json verwendet die Chunking-, Keyword- und Embedding-Defaults von import3.py mit einem eigenen Embedding-Set. import3.py ist unveraendert.

Pruefung: **236 Unit-Tests** erfolgreich. Ein Vergleich mit simulierten HTTP-Antworten bestaetigt die gleichen Keyword- und Embedding-Anfragen und numerisch uebereinstimmende normalisierte Vektoren. Alle sechs Beispieldateien lieferten dieselben Chunktexte in derselben Reihenfolge. Podman- und Ollama-Integration nicht erneut ausgefuehrt, da sich die Provideradapter und die Speicherung nicht aendern.

### Konfigurierbare Trennzeichen fuer den Import

Die Pipeline akzeptiert eine geordnete Trennzeichenliste und kann bestehende Zwischenartefakte ohne dieses Feld weiterverwenden. Eine Beispielkonfiguration bildet die LangChain-Standardtrennzeichen mit 1000 Zeichen und 100 Zeichen Ueberlappung ab.

Pruefung: **235 Unit-Tests** erfolgreich. Die vollstaendigen Chunkfolgen aller sechs Beispieldateien stimmten mit der damaligen LangChain-Referenzzerlegung ueberein. Podman- und Modellintegration nicht erneut ausgefuehrt, da die Aenderung die lokale Chunkzerlegung und Artefaktpruefung betrifft.

### Gemeinsamer Import nach Kapitel 8.4

`Ingest.pipeline` importiert mit rekursivem Chunking und optionalen Keywords. Der neue Zeichen-Fallback begrenzt ueberlange ungetrennte Passagen. Derselbe Chunktext geht an Ollama und die Vector-API. Versionierte Artefakte erlauben den Einstieg nach Chunking oder Anreicherung. `Ingest.chunk` erzeugt Chunks ohne Dienstzugriff. `Ingest/import3.py` bleibt erhalten. TS-05 bleibt fuer dokumentweite Freigabe, Altlastenbereinigung und Wiederaufnahme anhand des Laufberichts offen.

Pruefung: **231 Unit-Tests** erfolgreich. Beide Import-Integrationstests mit echten Ollama-Modellen, isoliertem Podman-Teststack und Ruecksuche erfolgreich (**2 passed**). Beide CLI-Hilfen und `git diff --check` erfolgreich. Die uebrigen Integrationstests wurden nicht erneut ausgefuehrt, da die Aenderung die Importpfade betrifft.

## 2026-11-22
### Neue Befunde im Schuldenregister priorisiert

TS-19 und TS-20 erfassen stillen Trefferverlust beim Reranking und den widersprüchlichen Vertrag für fehlenden Chunktext als P1. TS-21 und TS-22 erfassen überlange Chunks und veraltete Angaben in der Bausteinsicht als P2. Bestehende Einträge wurden um die Nachweise zum Wiederholungsimport, die Fehlerzuordnung bei falscher Vektordimension, die fehlende SciPy-Testabhängigkeit, die exakte Referenzsuche für Metrikvergleiche und die zugehörigen Testlücken ergänzt. Die Abbaureihenfolge priorisiert Importintegrität, Trefferverträge und Messkorrektheit.

Grundlage waren die vorangegangenen Prüfungen mit Testdoubles im Speicher und die lesende Chunkgrößenmessung im Beispielkorpus. Für die reine Dokumentationsänderung wurden Register, Verweise und `git diff --check` geprüft. Unit- und Podman-Suiten wurden nicht erneut ausgeführt.

### Gruener gemeinsamer Testlauf nach IDE-Referenzbereinigung

`python -m pytest -c tests/pytest.ini tests --all`: **239 passed in 259.41s (0:04:19)**, Exitcode 0, keine Fehler oder ausgelassenen Tests. Alle 225 Unit-Tests und 14 Integrationstests einschliesslich Import3 mit echten Keywords/Embeddings, RAG, Reranking, Evaluationskette, Migrationen und Vector-Wiederanlauf gemeinsam erfolgreich. Der zuvor durch externen Ollama-CUDA-Absturz fehlgeschlagene Importtest besteht jetzt auch innerhalb des gemeinsamen Laufs. Damit liegt nach der IDE-Referenzbereinigung ein vollstaendig gruener Gesamtnachweis vor; der vorherige Fehlschlag bleibt als historischer Nachweis erhalten.

Isolierte Testressourcen automatisch bereinigt. Keine Code-, Bestandsdaten- oder regulaeren Containeraenderungen. git diff --check erfolgreich.

### IDE-Referenzfehler im gesamten Testbestand bereinigt

Alle 23 Python-Dateien unter tests einschliesslich conftest und Hilfsmodulen mit der IDE-Referenzanalyse geprueft. Sieben weitere Dateien mit Referenzfehlern korrigiert: test_http_errors, test_vector_api_unit, test_chunking, test_rag_components, test_podman_stack_config, test_interact und die Import3-Integration. Statische Paketimporte und vollqualifizierte Patchziele fuer normale Module verwenden; bewusst dynamisch geladene isolierte Testmodule behalten ihre Stubs und werden ueber monkeypatch.setitem in ihrem Modulnamensraum gepatcht. Keine Inspektionen deaktiviert, keine Suppressionen eingefuegt. Testkonzept dokumentiert das Muster.

Abschliessende erneute IDE-Pruefung aller 23 Dateien: keine ERROR-Eintraege. Unit-Suite nach erster Bereinigung: **225 passed in 8.41s**. Vollstaendiger finaler Lauf `python -m pytest -c tests/pytest.ini tests --all`: **238 passed, 1 failed in 276.59s**. Einziger Fehler: externer Ollama-Embeddingprozess in Import3-Integration mit CUDA shared object initialization failed / Exitstatus 0xc0000409 abgestuerzt; kein Import-/Patchziel-Referenzfehler. Gezielte Wiederholung `python -m pytest -c tests/pytest.ini tests/podman/test_import3_integration.py --include-ollama -q`: **1 passed in 43.09s**. Damit alle Tests erfolgreich ausgefuehrt, jedoch kein vollstaendig gruener gemeinsamer Lauf in dieser Pruefung; Fehler und Wiederholung bewusst getrennt dokumentiert. Keine weitere Wiederholung der gesamten Suite nach erfolgreicher gezielter Pruefung.

Isolierte Testressourcen automatisch bereinigt. Keine regulaeren Container-/Datenaenderungen. git diff --check erfolgreich. Historische und schwache Stilhinweise bleiben von den geprueften Referenzfehlern getrennt.

### IDE-Referenzfehler in Importtests beseitigt

Dynamischen importlib-Import in tests/unit/test_import3.py durch statisch aufloesbaren Import von Ingest.import3 ersetzt. Nicht statisch erkannte reexportierte Patchziele verwenden pytest-konforme vollqualifizierte Strings (requests.post, Ingest.import3.get_keywords_ollama). Import3/keywords unterscheiden Paket- und direkte Skriptimporte, sodass Tests ohne temporaere sys.path-Erweiterung auskommen. Keine Inspektion deaktiviert und keine Suppression hinzugefuegt.

Pruefung: IDE-Analyse der Testdatei meldet keine ERROR-Eintraege mehr (zuvor unresolved references an Patchzielen); bestehende schwache Hinweise auf ungenutzte Parameter in einem Testdouble nicht unterdrueckt. `python -m pytest -c tests/pytest.ini tests/unit -q`: **225 passed in 8.17s**. `python Ingest/import3.py --help` und `python -m Ingest.import3 --help` erfolgreich. git diff --check erfolgreich. Keine erneute Podman-/Modellintegration, da ausschliesslich Importaufloesung und Test-Patchziele geaendert; keine Daten-/Containeraktualisierung.

### TS-05 teilweise umgesetzt: Import3 verwendet Path.stem

Chunk-ID- und Logdateistamm in Ingest/import3.py auf Path(file_path).stem umgestellt. Mehrere Punkte bleiben bis auf die letzte Erweiterung erhalten; erweiterungslose Namen bleiben unveraendert. Parametrisierte Tests durchlaufen echtes Chunking fuer rom.band1.txt, rom.band2.txt, rom und rom.txt, pruefen drei gespeicherte Chunk-IDs und den Logdateistamm mit gemockten externen Abhaengigkeiten. Risiko R-02 bleibt akzeptiert. TS-05 bleibt fuer kuerzere Neuimporte, Freigabe, Fehlerabschluss, Resume und Bestandsbereinigung offen. Konzept, Register, Risikoeintrag und README aktualisiert.

Pruefung: `python -m pytest -c tests/pytest.ini tests/unit -q`: **225 passed in 8.36s**. `git diff --check` erfolgreich. Keine Integration mit Podman/Ollama erneut ausgefuehrt, da ausschliesslich lokale Dateistamm-Ermittlung geaendert und ueber den echten Importablauf containerfrei geprueft. Keine Imports auf Bestandsdaten, Migrationen oder Containeraktualisierungen ausgefuehrt. Alte IDs mehrteiliger Namen werden nicht automatisch geloescht; vor Wiederholungsimport Altbestand pruefen und Bereinigung planen.

### Dateistamm-Regel und akzeptiertes Kollisionsrisiko dokumentiert

Kapitel 8.4 und TS-05 legen Chunk-IDs als Dateinamen ohne letzte Erweiterung (Path.stem) plus Chunknummer ab 1 fest. Eindeutigkeit des Stamms gilt innerhalb eines Embedding-Sets; keine Versions-/Pfadkomponenten im Chunkschluessel. R-02 akzeptiert Kollisionen etwa zwischen rom.txt und rom.md sowie gleichen Namen aus verschiedenen Verzeichnissen; manuell umbenennen oder getrennte Sets verwenden. Keine technische Kollisionsregistrierung vorgesehen. Abbauplan auf diese Entscheidung angepasst. Codekorrektur, Bestandsbereinigung, kuerzere Neuimporte und Fehlerabschluss bleiben offen.

Pruefung: Dokumentverweise und Konsistenz der ID-Regel kontrolliert; git diff --check erfolgreich. Keine Code-/Daten-/Containeraenderung; Unit-/Integrationstests fuer diese Dokumentationsentscheidung nicht ausgefuehrt.

### Importkonzept auf gemeinsamen Chunktext vereinfacht

Kapitel 8.4 verwendet vorerst denselben chunktext fuer Embedding, Reranking und Antwortkontext. texts aus der Versuchskonfiguration entfernt; Ablauf, Datenvertrag und Baselinebeschreibung angepasst. Original und Anreicherung bleiben als lokale Zwischeninformationen erhalten, ohne getrennte Embedding-/Kontextfelder einzufuehren. Abschnitt 8.4.10 bewahrt Erklaerung, Beispiel und Versuchsfragestellung der spaeteren Trennung, markiert aber ausdruecklich: derzeit nicht implementieren, auch keine Schalter oder Schemavorbereitung.

Pruefung: JSON-Beispiele geparst, texts-Schluessel ausgeschlossen und lokale Kapitelverweise kontrolliert; git diff --check erfolgreich. Keine Code-/Container-/Datenaenderung. Unit- und Integrationstests wegen ausschliesslicher Konzeptaenderung nicht erneut ausgefuehrt.

### Kapitel 8.4: Variantenfaehiges Importkonzept

Neues docs/8-4-importkonzept.md beschreibt gemeinsamen Importablauf, austauschbare Python-Strategien und JSON-Versuchskonfigurationen statt vollstaendiger Importskripte pro Idee. Enthalten sind Schnittstellen-/CLI-Entwuerfe, getrennte Quell-/Anreicherungs-/Embedding-/Kontexttexte, versionierte Zwischenartefakte, explizite Wiederverwendung, Dokument-/Versions-/Laufidentitaet sowie Zielregeln fuer Freigabe, Altlasten, Resume und Metriken. R-01 bleibt unveraendert: keine automatische Set-Konfigurationsregistrierung oder -pruefung. Zielkonzept klar von aktuellem Import3 und noch umzusetzenden TS-05/12/14/17 abgegrenzt; in Bausteinsicht und Schuldenregister verlinkt.

Pruefung: beide JSON-Beispiele geparst, lokale Kapitelverweise und neun nummerierte Unterabschnitte kontrolliert; git diff --check erfolgreich. Keine Code-/Container-/Datenaenderung und kein Schuldenabschluss. Unit-/Integrationstests nicht ausgefuehrt, da ausschliesslich Konzeptdokumentation geaendert. Neue Konzeptdatei gezielt fuer Git vorgemerkt; kein Commit.

### Schuldenregister gegen Code und Testbestand abgeglichen

Alle TS-01 bis TS-18 anhand aktueller Implementierung, Tests, Dockerfiles und Migrationsskripte geprueft; k8s-Verzeichnisse ausgeschlossen. TS-01/02/03/06/07/09 bleiben abgeschlossen, TS-08 jetzt konsistent als abgeschlossen ausgewiesen. R-01 unveraendert akzeptiertes Risiko. TS-05 und TS-10 bis TS-18 bleiben mit praezisiertem Restumfang offen.

Ueberholte Befunde entfernt: Vektoreingangsvalidierung, echte Chunking-Grenz-/Overlaptests, Import3-Integration inklusive Keywords, Parallelitaet/Rollback/DB-Erholung sowie versionierte SQL-Migrationen mit Backup-/Restoretests existieren bereits. TS-11 auf Ausgabevertrag, Providerdimension und Importvektoren begrenzt; TS-15 auf Build-/Modellrevisionen und Fortschreibung vorhandener Migrationen. TS-12 grenzt vorhandene RAG-Adapter von Keyword-/Resolver-/Budget-/Logresten ab. TS-17 benennt konkrete Resttests statt pauschal fehlender Import-/Chunkingabdeckung. tmpfs-Erholungstest nicht als Volume-Persistenznachweis gewertet.

AST-Pruefung bestaetigt weiterhin fehlerhaften GOLDCHUNK in analyze.py: 46 Zeichen, 14 eigenstaendige Textliterale. Importidentitaet/Fehlerabschluss, mehrdeutige Chunkabfragen, Reranker-Health und ungepinnte Builds bleiben im Code offen. Abbauplan auf Restarbeiten umgestellt: TS-14, TS-05, Health, Identitaets-/Vektorvertraege, Adapterreste; Build-Reproduzierbarkeit parallel, Suchplaene/erweiterter Betrieb nach Bedarf. Bereits umgesetzte Infrastruktur nicht erneut eingeplant. Goldvergleich bleibt trotz /evaluate ein noch zu definierender fachlicher Schritt.

Pruefung: `python -m pytest -c tests/pytest.ini tests/unit -q`: **221 passed in 8.22s**; `git diff --check` erfolgreich. Keine Produktionscode-/Container-/Datenaenderungen. Podman-, Modell-, Last- und Persistenztests bei dieser Dokumentationspruefung nicht erneut ausgefuehrt; vorhandene Tests gelesen und historische Nachweise getrennt von der aktuellen Codepruefung behandelt.

### Evaluationsendpunkte ausgerollt und live verkettet

RAG-Image mit `python scripts/build_image.py rag-api --tag localhost/rag-api:evaluate-20261122` gebaut, Image-ID `e5c5e1d44286f0107b3442de9934e9e7c7296d6bc67b50abe1783d6e9a6fbf2e`, ebenfalls als localhost/rag-api:local markiert. Container rag-api mit bisheriger Konfiguration (Port 5600:5600, keine zusaetzlichen Umgebungsvariablen) ersetzt. Vorheriger Container bleibt gestoppt als rag-api-before-evaluate erhalten. Quellhash app.py im Container entspricht Workspace: `7a70f9a93405927425f57ec76191e5db49badf85be3b0ef941b486c1e6327ab2`. Datenbank, Vector-API, Reranker und Volumes unveraendert.

Live-Kette gegen localhost:5600: POST /evaluate/retrieve mit Frage "Wer beherrschte das westliche Mittelmeer?", num_results=3, top_k=1 und answer_model=gemma4:e4b; dessen next_request unveraendert an /evaluate/rerank, dessen next_request unveraendert an /evaluate/generate. Alle drei HTTP 200. Retrieval liefert drei Chunks (pg3060-552, pg3061-301, pg3065-1770), 1024-dimensionalen Query-Vektor und Distanzen. Reranking waehlt pg3060-552, Score 2,9705081. Chunk-ID, Text und Distanz entsprechen dem ueber original_index referenzierten Retrievaltreffer. Generierung liefert status ok, nichtleere Antwort, passenden Kontext und Chunk-ID, Modell gemma4:e4b sowie wiederverwendbare request identisch zur vorherigen next_request.

Laufzeiten: Embedding 0,09257 s, Retrieval 0,04543 s, Retrieve gesamt 0,13802 s, Rerank 0,11598 s, Generate-Aufruf 17,89520 s. Ollama-Generierungsdauer 17,89191 s, Ladezeit 17,23282 s, 136 Prompt- und 23 Antworttoken. Zeitfelder automatisch auf endliche nichtnegative Werte geprueft, Score und Generierungsmetriken ebenfalls validiert. Antwort: "Die vereinigte Macht der Italiker und Phoeniker behauptete die westliche Haelfte des Mittelmeeres."

Keine Schreibzugriffe auf Datenbank oder Exportdateien fuer die Live-Kette. Vorheriger Gesamttestnachweis (235 bestanden) bleibt erhalten; keine Codeaenderung oder erneute Gesamtsuite beim reinen Ausrollen.

### Schrittweise Evaluation ueber drei RAG-Endpunkte

Die extern gelesene historische rag-configmap.yaml aus dem knowledge-experimental-ki/rag-setup dient als fachliche Referenz fuer /evaluate/retrieve, /evaluate/rerank und /evaluate/generate. Implementierung verwendet aktuelle RAG-Providerfunktionen, Chunkfelder und Problem Details statt historischer SQL-/LangChain-Verarbeitung. Retrieve und Rerank liefern next_request mit Frage, Ergebnissen und Folgeparametern, direkt als Eingabe fuer den naechsten Schritt. Generate liefert eine wiederverwendbare request-Eingabe. Trefferidentitaet und Metadaten/Distanzen bleiben erhalten; Reranking ergaenzt Score und Index. Modelle, Laufzeiten und verfuegbare Provider-Metriken werden ausgegeben; fehlende Metriken null. Retrieve kann gespeicherte Vektoren verwenden, Generate eigene System-/Userpromptvorlagen. Kein serverseitiger Sitzungszustand oder impliziter Folgeaufruf. Goldvergleich und aggregierte Qualitaetsmessung bleiben spaetere Schritte.

Pruefung: Unit-Suite **221 passed in 8.08s**. Abschliessend `python -m pytest -c tests/pytest.ini tests --all`: **235 passed in 255.85s (0:04:15)**, Exitcode 0, keine ausgelassenen Tests. Vertragstests pruefen Verkettbarkeit und Isolation der Schritte, erhaltene Chunk-ID/Distanz/Score, gespeicherte Vektoren, leere Eingaben und Eingangs-/Promptvalidierung. Neue isolierte Integration durchlaeuft Retrieve/Rerank/Generate mit echtem Testchunk, Reranker und Antwortmodell; Testchunk und isolierte Ressourcen anschliessend entfernt. Vorhandene Datenbestaende und regulaere Container unveraendert. `git diff --check` erfolgreich.

README mit Vertragsbeschreibung und PowerShell-Beispiel, Baustein-/Laufzeitsicht, Architekturentscheidung, Fehler- und Testkonzept aktualisiert. Keine Gold-Antworten bewertet und keine regulaeren Images/Container aktualisiert; fuer Live-Nutzung RAG-Image neu bauen und Container ersetzen.

### Neue RAG-Laufzeiten ausgerollt und live geprueft

`python scripts/build_image.py rag-api --tag localhost/rag-api:timings-20261122` erfolgreich; Image-ID `32b7fe95e32f675c5b1a35beb0275a37587d69e8b5023b4f7645d95c37c0e45f`, auch localhost/rag-api:local. Container rag-api mit unveraenderter Startkonfiguration (Port 5600:5600, keine zusaetzlichen Umgebungsvariablen) ersetzt. Vorheriger Container bleibt gestoppt als rag-api-before-timings erhalten. Quellhash app.py im Container entspricht Workspace: `d9249f9836bb8afcfbffbcd594c9f0c7230c20262dd700edf1d3aabecbe0399b`. Datenbank, Vector-API, Reranker und Volumes unveraendert.

Live-CLI ueber interact.main mit Argumenten `--query "Wer beherrschte das westliche Mittelmeer?" --num_results 3 --top_k 0` und anschliessend `--top_k 1`: beide HTTP 200, status ok, Exitcode 0, Modell gemma4:e4b, drei Retrieval-/Exportpassagen. Ohne Reranking: Embedding 0,14 s, Retrieval 0,03 s, Pipeline 14,09 s, Generierung 13,92 s. Mit Reranking: Embedding 2,74 s, Retrieval 0,03 s, Reranking 3,94 s, Pipeline 12,56 s, Generierung 5,85 s; ein ausgewaehlter Kontexttreffer pg3060-552.

Automatisch geprueft: neue API-Zeitfelder endlich und nichtnegativ; Pipelinezeit mindestens Summe der gemessenen Teilzeiten einschliesslich Reranking; generation_duration identisch zum kompatiblen total_duration-Alias. CLI-Ausgabe mit Sekunden und zwei Nachkommastellen sowie getrennten Abschnitten bestaetigt. Bestehende search_results.json bytegetreu wiederhergestellt. Keine Datenbankschreibpruefung. Vorheriger Gesamtnachweis (216 bestanden) bleibt gueltig; keine erneute Gesamtsuite beim reinen Ausrollen ohne Codeaenderung.

### Embedding-, Retrieval- und Pipeline-Laufzeiten ergaenzt

RAG-API liefert timings.embedding_duration, timings.retrieval_duration und timings.pipeline_duration in ungerundeten Sekunden mit monotoner Uhr. Messbeginn am Eintritt in process_request nach Eingangsvalidierung; Pipelineende unmittelbar vor JSON-Antwortaufbau. Enthalten sind Aufloesung, Provideraufrufe, Validierung/Normalisierung, Retries, optionales Reranking und Generierung; Antwortserialisierung, Clienttransport und CLI-Export nicht enthalten. no_context enthaelt ebenfalls timings, metrics bleibt null; Fehlerantworten liefern keine Teillaufzeiten.

Ollamas bisherige total_duration heisst nun metrics.generation_duration; metrics.total_duration bleibt kompatibler Alias. CLI benennt den Wert Generierungsdauer und zeigt zusaetzlich Embedding-/Retrieval-Laufzeiten im Retrievalabschnitt sowie RAG-Pipeline-Gesamtdauer. Einheitlich Sekunden mit zwei Nachkommastellen. Fehlende Felder aelterer APIs werden als nicht verfuegbar angezeigt. README, Bausteinsicht, Laufzeitsicht und Testkonzept aktualisiert.

Pruefung: `python -m pytest -c tests/pytest.ini tests/unit -q`: **203 passed in 8.05s**. Abschliessend `python -m pytest -c tests/pytest.ini tests --all`: **216 passed in 260.42s (0:04:20)**, Exitcode 0, keine ausgelassenen Tests. Kontrollierte Uhr prueft exakte Messgrenzen mit/ohne Reranking und no_context vor/nach Reranking; CLI-Test prueft Rundung und Bezeichnungen. Echte RAG-Integration prueft neue Zeitfelder und kompatiblen Generierungsalias. Isolierte Testressourcen automatisch bereinigt; regulaere Container und Daten nicht geaendert. `git diff --check` erfolgreich. Fuer Live-Nutzung der neuen Servermessungen RAG-Image neu bauen und Container ersetzen.

### Gruppierte CLI-Ausgabe am laufenden System geprueft

Live-Aufrufe: `python interact.py --query "Wer beherrschte das westliche Mittelmeer?" --num_results 3 --top_k 0` und derselbe Aufruf mit `--top_k 1`. Beide erfolgreich (Exitcode 0), Antwortmodell gemma4:e4b, je drei Retrieval- und Exportpassagen. Ohne Reranking: Abschnitt meldet Deaktiviert; Generierungs-Gesamtdauer 13,53 s, Modell-Ladezeit 10,18 s, Prompt-Verarbeitung 0,40 s, Antwortgenerierung 2,94 s. Mit Reranking: cross-encoder/ms-marco-MiniLM-L6-v2, 0,28 s, ein ausgewaehlter Chunk pg3060-552; Generierungs-Gesamtdauer 0,86 s, Modell-Ladezeit 0,01 s, Prompt-Verarbeitung 0,09 s, Antwortgenerierung 0,25 s.

Abschnitte Retrieval, Reranking und Antwortgenerierung sowie Leerzeilen und Sekundenformat mit zwei Nachkommastellen in beiden echten CLI-Ausgaben bestaetigt. Tokenzahlen und Antwort-Rate ausgegeben. Die Gesamtdauer stammt aus den Generierungsmetriken und umfasst nicht die gesamte RAG-Pipeline. Bestehende search_results.json nach den Tests bytegetreu wiederhergestellt. Keine Datenbank-Schreibpruefung, Code- oder Containeraenderung; vorheriger CLI-Unit-Nachweis bleibt erhalten, Gesamtsuite nicht erneut ausgefuehrt.

### CLI-Ausgabe nach Verarbeitungsschritten gruppiert

interact.py trennt Retrieval, Reranking und Antwortgenerierung durch Leerzeilen. Treffer/Export, Rerankermodell/ausgewaehlte Chunks sowie Antwort/Generierungsmetriken stehen jeweils im passenden Abschnitt. Saemtliche ausgegebenen Laufzeiten verwenden Sekunden mit zwei Nachkommastellen (auch Modell-Ladezeit); fehlende Werte bleiben nicht verfuegbar. Tokenzahlen bleiben unveraendert, Antwort-Rate mit zwei Nachkommastellen. Ausgelassene Schritte und no_context werden explizit angezeigt. README aktualisiert.

Pruefung: `python -m pytest -c tests/pytest.ini tests/unit/test_interact.py -q`: **31 passed in 0.19s**. Ausgabepruefung sichert Abschnittsreihenfolge, Leerzeilen, Rundung, Einheiten und fehlende Messwerte. `git diff --check` erfolgreich. Keine Podman-/Modelltests oder erneute Gesamtsuite fuer die reine CLI-Darstellung; keine Containeraktualisierung erforderlich.

### Antwortmodellstandard im laufenden RAG-System aktualisiert

RAG-Image mit `python scripts/build_image.py rag-api --tag localhost/rag-api:gemma4-20261122` neu gebaut, Image-ID `68d7c0495b2cdca8fd6d2b0c762e974154a795594841adc09ee2f58c91aae4ac`; ebenfalls als localhost/rag-api:local markiert. Container rag-api mit unveraenderter Startkonfiguration (Port 5600:5600, keine weiteren Umgebungsvariablen) ersetzt. Bisheriger Container bleibt gestoppt als rag-api-before-gemma4 erhalten. Datenbank, Vector-API, Reranker und Volumes nicht ersetzt.

Laufender API-Standard gemma4:e4b bestaetigt. SHA256 von app.py (`97ba723df545d40630168e525c64a4aa7e5a121838d150772caff636e402a7d1`) und embedding_config.py (`ceb0eb9a9b74617537284471a2589a5f3a5988b431f32feb2850895b8515c9f1`) stimmen mit dem Workspace ueberein.

CLI-Livepruefung ueber interact.main mit Argumenten `--query "Wer beherrschte das westliche Mittelmeer?" --num_results 3 --top_k 1`: ohne Modelloption wird nachweislich answer_model=gemma4:e4b an die laufende RAG-API gesendet; mit `--answer-model phi3:mini` nachweislich phi3:mini. Beide Laeufe Exitcode 0, HTTP 200, status ok, Antwort und Generierungsmetriken. Reranking mit cross-encoder/ms-marco-MiniLM-L6-v2 erfolgreich: drei Retrievaltreffer, ein ausgewaehlter Kontexttreffer (pg3060-552), Export jeweils drei Passagen. Rerankingdauer rund 0,0121 s beziehungsweise 0,2740 s. Vorhandene search_results.json nach den Tests bytegetreu wiederhergestellt. Keine Datenbankschreibtests auf regulaeren Daten.

Vorheriger Unit-Nachweis (197 bestanden) bleibt erhalten; reine Bereitstellung ohne Codeaenderung, deshalb keine erneute Gesamtsuite. Neuer Default und explizite Modellwahl sind jetzt im laufenden System geprueft.

### Gemeinsames Antwortmodell gemma4:e4b

CLI und RAG-API lesen den gemeinsamen Antwortmodellstandard aus rag/embedding_config.py: ohne Konfiguration gemma4:e4b, mit ANSWER_MODEL der konfigurierte Wert. Die vorhandene CLI-Option --answer-model und das API-Feld answer_model ueberschreiben diesen Standard pro Anfrage. Ungueltige Modellangaben ergeben weiterhin frueh HTTP 400 beziehungsweise CLI-Exitcode 2. Dokumentation und CLI-Beispiel aktualisiert; E2E-Tests behalten ihre explizite Modellwahl phi3:mini.

Pruefung: `python -m pytest -c tests/pytest.ini tests/unit -q`: **197 passed in 9.83s**. Tests sichern Standard, Umgebungsueberschreibung, CLI-Weitergabe, explizite Modellwahl und API-Eingangsvalidierung ab. `git diff --check` erfolgreich. Keine erneuten Modell-/Podman-Integrationstests fuer diese reine Standardkonfigurationsaenderung; keine laufenden Container ersetzt. Fuer den neuen serverseitigen Default muss das RAG-Image neu gebaut und der Container neu erstellt werden.

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

Der Datenbankcontainer wurde weder ersetzt noch neu gestartet; das Volume `pgvector-data` blieb unverändert eingebunden. Vorherige und anschließende SQL-Zählung ergaben jeweils 10.378 Zeilen. Ports, Pod-Zuordnung, Geräte einschließlich GPU, Mounts und Startkonfiguration der APIs wurden erhalten und abgeglichen; lediglich automatisch vergebene Container-Hostnamen änderten sich. Die bisherigen API-Container bleiben gestoppt mit dem Suffix `-before-ts03-20261121` als Rückweg erhalten. Den aktuellen Status führt [TS-03 in Kapitel 11.2](docs/11-2-technische-schulden.md#ts-03--requestvalidierung-und-fehlerverträge). Die weiteren Zielmaßnahmen dieses Konzepts bleiben davon unberührt.

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
