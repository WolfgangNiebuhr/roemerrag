<!--

purpose: "Ausdrücklich identifizierte Architekturrisiken mit ihren möglichen Auswirkungen und dem Umgang damit."
agent_instructions:
  - Dies ist Teil einer  Architekturdokumentation nach Arc42
  - "Je Risiko eine stabile R-ID, Auslöser oder Ursache, mögliche Auswirkungen, Status und den Umgang damit festhalten. Wo belastbar, Eintrittswahrscheinlichkeit und Auswirkung für die Priorisierung angeben."
  - "Akzeptierte Restrisiken und ihre Begründung kenntlich machen. Technische Schulden in 11.2 pflegen und bei einem ausdrücklich erfassten Zusammenhang aufeinander verweisen."
  - "Gültige Änderungen direkt einarbeiten. Datierte Nachträge sowie Änderungs-, Prüf- und Ausrollnachweise ausschließlich in ../changelog.md pflegen."

-->

# 11.1 Risiken

Stand: 28.11.2026. Dieses Register enthält ausschließlich ausdrücklich als Risiko markierte Einträge. Technische Schulden werden separat in [Abschnitt 11.2](11-2-technische-schulden.md) geführt und gelten nicht automatisch als Risiken. Risiken erhalten eine eigene Nummerierung mit dem Präfix R.

## R-01 – Manuelle Zuordnung von Importvarianten · Akzeptiertes Risiko

- **Befund:** `embedding_set_id` ist eine frei gewählte Kennung. Retrieval kann Modell und Set unabhängig konfigurieren; die Datenbank speichert und prüft keine vollständige Verarbeitungskonfiguration. Eine Set-ID allein belegt daher weder Chunking, Anreicherung und Prompts noch das tatsächlich verwendete Modell und die Normalisierung.
- **Entscheidung vom 21.11.2026:** Keine zusätzliche technische Speicherung oder Absicherung dieser Konfiguration. Stattdessen wird die Zuordnung manuell im [Set-ID-Verzeichnis, arc42-Abschnitt 8.2](8-2-embedding-sets.md) gepflegt. Die [Architekturentscheidung 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026) ersetzt den bisherigen Vorschlag einer persistierten Variantenkonfiguration.
- **Manuelle Behandlung:** Vor einem Import die tatsächlichen Parameter zum Set dokumentieren; bei geänderter Verarbeitung eine neue Set-ID verwenden. Evaluationen nennen die verwendete Set-ID. Unbekannte historische Angaben bleiben ausdrücklich unbekannt; der aktuelle Codezustand ist kein vollständiger Herkunftsnachweis für Bestandsvektoren. Ein erneutes Embedding ist hierfür nicht erforderlich.
- **Akzeptiertes Restrisiko:** Eine falsche Kennung oder veraltete Dokumentation kann unterschiedliche Verarbeitungen unter derselben Set-ID vermischen. Gleiche `(chunk_id, embedding_set_id)` können überschrieben werden; Vergleiche werden dadurch schwer erklärbar oder nicht wiederholbar. Das Verzeichnis unterstützt die Nachvollziehbarkeit, verhindert solche Fehler aber nicht technisch. Es besteht kein offener Implementierungsauftrag für die ursprünglich vorgeschlagene Konfigurationspersistenz. Der Importabschluss der Pipeline ist in TS-05 dokumentiert; Modellrevisionen und Buildstände behandelt TS-15.

Herkunft: bisheriger Eintrag TS-04.

## R-02 Dateistamm als Dokumentidentitaet

**Status: Akzeptiertes Risiko, Entscheidung vom 22.11.2026.**

- **Regel:** Chunk-IDs verwenden den Dateinamen ohne die letzte Erweiterung und eine bei 1 beginnende Chunknummer, beispielsweise rom.band1-1 aus rom.band1.txt. Der Dateistamm muss innerhalb eines Embedding-Sets eindeutig sein; Verzeichnis und Erweiterung gehoeren nicht zum Schluessel.
- **Akzeptiertes Restrisiko:** Dateien wie rom.txt und rom.md besitzen denselben Stamm und erzeugen im selben Set dieselben Chunk-IDs. Auch gleiche Dateinamen aus verschiedenen Verzeichnissen kollidieren. Atomare Upserts koennen dadurch fremde Chunks ueberschreiben; bei unterschiedlichen Chunkzahlen koennen vermischte Restbestaende entstehen. Retrieval und Qualitaetsmessungen koennen dadurch falsche Quellen enthalten.
- **Manuelle Behandlung:** Vor Import Dateistaemme innerhalb des Sets eindeutig halten; kollidierende Quellen umbenennen oder unterschiedlichen Sets zuordnen. Keine automatische Erweiterungs-/Verzeichniskennung oder technische Kollisionsregistrierung vorgesehen. Gleichnamige Dateien in verschiedenen Sets kollidieren wegen des zusammengesetzten Datenbankschluessels nicht.
- **Abgrenzung:** Kürzere Wiederholungsimporte und Wiederaufnahme sind für die Pipeline unter TS-05 umgesetzt. Das Risiko akzeptiert keine unbeabsichtigte Loeschung von Bestandsdaten und ersetzt keinen Umstellungsplan.

Konzept: [Kapitel 8.4.7](8-4-importkonzept.md#847-identitaet-wiederholung-und-abschluss).

## R-03 – Vorübergehend inkonsistenter Chunkbestand bei Importabbrüchen

**Akzeptiertes Risiko, Entscheidung vom 25.11.2026.**

- **Auslöser.** `Ingest.pipeline` schreibt Chunks einzeln. Bricht der Import ab, bleiben die bereits geschriebenen Chunks abrufbar. Im betroffenen Dokument und Embedding-Set können dadurch Chunks fehlen oder alte, neue und überzählige Chunks gleichzeitig abrufbar sein.
- **Auswirkung.** Retrieval und Evaluation können bis zum erfolgreichen Abschluss einen unvollständigen oder gemischten Datenstand verwenden. Ein Fehler in der abschließenden Bereinigung kann alte Chunks mit höheren Nummern zurücklassen.
- **Behandlung.** Den Import mit derselben Eingabe, Konfiguration und Set-ID ab der ausgegebenen Chunknummer mit `--start` fortsetzen. Nach einem reinen Bereinigungsfehler startet der Aufruf mit der ausgegebenen Nummer direkt nach dem letzten Chunk und holt die Bereinigung nach. Vergleichsmessungen für den betroffenen Bestand erst nach erfolgreichem Abschluss durchführen. Der Zwischenstand bleibt bis zu einem erfolgreichen Folgeaufruf bestehen. [Architekturentscheidung 9.4](9-architekturentscheidungen.md#94-eventual-consistency-beim-dokumentimport-25112026)

## R-04 – Fehlende oder überzählige Scores beim Reranking

**Akzeptiertes Risiko, Entscheidung vom 27.11.2026.**

- **Auslöser.** Die Zahl der Scores weicht von der Zahl der übergebenen Chunks ab. Scores können fehlen, wenn ein Ersatzdienst nur seine Top-Treffer zurückgibt oder ein Adapter fehlgeschlagene Batches überspringt. Überzählige Scores können entstehen, wenn ein Adapter beim Zusammenführen der Ergebnisse einen Batch doppelt anhängt.
- **Auswirkung.** Bei fehlenden Scores können relevante Chunks still aus dem Antwortkontext und der Evaluation fallen, auch bei voller `top_k`-Auswahl. Ist die Rangliste leer, meldet die RAG-API `no_context`, obwohl das Retrieval Treffer geliefert hat. Der Reranker verwirft überzählige Scores am Ende der Liste still. Sind zusätzliche Scores vorher eingefügt, können nachfolgende Chunks falsch bewertet und einsortiert werden.
- **Behandlung und Begründung.** Für den Betrieb mit dem Standardmodell `cross-encoder/ms-marco-MiniLM-L6-v2` wird eine abweichende Score-Anzahl als Risiko akzeptiert. Im lokalen Modelllauf entsprach die Anzahl der Scores der Anzahl der übergebenen Chunks, auch bei langen Eingaben, mehreren Batches und parallelen Anfragen. Der technische Befund ist unter [TS-19](11-2-technische-schulden.md#ts-19--stiller-trefferverlust-beim-reranking) dokumentiert.

## R-05 – Veränderliche Basisimages, Python-Abhängigkeiten und Modellrevisionen

**Akzeptiertes Risiko, Entscheidung vom 28.11.2026.**

- **Auslöser und Auswirkung.** Vector-API, RAG-API und Reranker beziehen ihr Python-Basisimage über einen beweglichen Tag. Ein Neubau kann bei gleichem Projektstand einen anderen Plattformstand ergeben. Änderungen können den Build oder die Laufzeit der Dienste beeinflussen. Auch unter derselben Modellkennung kann sich die bereitgestellte Revision ändern. Dadurch können sich Embeddings, Trefferreihenfolgen oder generierte Antworten bei gleicher Versuchskonfiguration verändern.
- **Begründung.** Für das lokale Experimentiersystem hat eine aktuelle Plattform Vorrang vor der exakten Reproduktion früherer API-Builds. Änderungen der Modellrevisionen werden akzeptiert, weil die Untersuchung von Modelldrift ein Projektziel ist. Ein spezifischer Test auf Modelldrift ist derzeit nicht vorgesehen. [TS-15](11-2-technische-schulden.md#ts-15--nicht-reproduzierbare-builds-und-testumgebungen)
- **Python-Abhängigkeiten.** Direkte und transitive Python-Abhängigkeiten dürfen beim Neubau neu aufgelöst werden. Neuere Paketstände können den Build oder den Dienststart beeinträchtigen und Verhalten oder Laufzeiten verändern. Änderungen außerhalb der abgedeckten Testfälle sind als Restrisiko akzeptiert.
- **Freigabekriterium.** Die API-Images regelmäßig mit aktuellen Basisimages neu erstellen. Bestandene Integrationstests im isolierten Podman-Stack genügen als Freigabekriterium für den Neubau. Im laufenden Stack genau die geprüften Images einsetzen. [Aktualisierungsskript](../scripts/update-api-images.ps1)
