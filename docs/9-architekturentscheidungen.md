<!--

purpose: "Gründe und Konsequenzen wesentlicher Architekturentscheidungen nachvollziehbar festhalten."
agent_instructions:
  - "Nur weitreichende, schwer umkehrbare, riskante oder strittige Entscheidungen aufnehmen. Lokale Entscheidungen beim zuständigen Baustein oder Konzept dokumentieren."
  - "Je Entscheidung möglichst Datum und Status, Kontext und Kriterien, erwogene Alternativen, Entscheidung und wesentliche Konsequenzen erfassen. Fehlende Informationen als unbekannt kennzeichnen. Abgelöste Entscheidungen als solche markieren und mit der Nachfolgeentscheidung verknüpfen."
  - "Die Kurzfassung wesentlicher Lösungsentscheidungen steht in Kapitel 4. Das Datum einer Entscheidung gehört zum Entscheidungsdatensatz. Chronologische Änderungs-, Prüf- und Ausrollnachweise ausschließlich in ../changelog.md pflegen."

-->

# 9 Architekturentscheidungen

## 9.1 Modell und Embedding-Set trennen (21.11.2026, TS-01)

`embedding_set_id` bezeichnet die Menge zusammengehöriger Vektoren aus einer gemeinsamen Verarbeitungslogik. Die Kennung bezeichnet keinen einzelnen Ausführungslauf und ist unabhängig vom Modellnamen. Wiederholte Imports dürfen dasselbe Set verwenden. Die Konfiguration wird gemäß Abschnitt 9.3 manuell dokumentiert; die Importpipeline verwaltet ihre Läufe getrennt von der Set-ID.

CLI und RAG lesen Modell und Set aus `rag/embedding_config.py`. Beide Einstellungen sind unabhängig über Umgebungsvariablen überschreibbar. Der Standard verweist auf das bestehende Set `snowflake-arctic-embed2-v2`; das Modell bleibt `snowflake-arctic-embed2`.

Die Datenbankspalte wird transaktional umbenannt; Kennungen und Vektoren bleiben unverändert. Vor jeder Bestandsmigration erzeugt das Werkzeug ein vollständiges Backup und prüft dessen Inhaltsverzeichnis. Es gibt keine automatische Migration beim API-Start. Damit sind Backup und Umstellungszeitpunkt explizite Betriebsschritte.

Vector-API und RAG-API verwenden für die Set-Kennung ausschließlich `embedding_set_id`. Die CLI verwendet `--embedding-set-id`. Nur die Zeilenzählung kann ohne Set-ID alle Sets umfassen. Die RAG-API verwendet ohne Angabe das konfigurierte Standard-Set.

Migration und neue API-Version müssen gemeinsam ausgerollt werden; alte API-Versionen erwarten den alten Spaltennamen. Rückweg und Restore sind im README dokumentiert.

## 9.2 Chunktext explizit benennen (21.11.2026)

Die Spalte `metadata` enthält den zur Kontextbildung verwendeten Text und heißt künftig `chunktext`. Der Name gilt durchgängig in SQL, Vector-API, Import, Retrieval, Reranking und Analyse. Es gibt keinen Kompatibilitätsalias; externe API-Clients müssen gleichzeitig aktualisiert werden. `/find` durchsucht `chunktext` weiterhin mit `ILIKE`.

`002_chunktext.sql` benennt nur die Spalte um. Inhalte einschließlich NULL, Vektoren, Schlüssel und Index bleiben erhalten. Der vorhandene Backup-Migrationsmechanismus führt die Migration mit `--migration 002_chunktext.sql` erst nach einem geprüften vollständigen Dump aus. Migration und API-Aktualisierung erfolgen bei gestoppten APIs. Ein erneutes Embedding ist nicht erforderlich.

## 9.3 Set-Konfiguration manuell dokumentieren (21.11.2026)

Die Zuordnung von Verarbeitungsparametern zu `embedding_set_id` wird auf ausdrückliche Projektentscheidung ausschließlich im [Set-ID-Verzeichnis, Abschnitt 8.2](8-2-embedding-sets.md) gepflegt. Eine zusätzliche technische Speicherung, Konfigurationsprüfung oder automatische Vergabe von Set-Identitäten ist nicht vorgesehen. Der bisherige technische Abbauvorschlag aus TS-04 wird damit ersetzt.

Vor neuen Imports werden Set-ID und tatsächliche Parameter manuell dokumentiert; bei geänderter Verarbeitung wird eine neue Kennung gewählt. Historisch unbekannte Angaben bleiben als unbekannt gekennzeichnet. Vorhandene Daten bleiben erhalten. Die Möglichkeit einer versehentlichen Vermischung oder Überschreibung bei falsch gewählter Kennung wird als [Risiko R-01](11-1-risiken.md#r-01--manuelle-zuordnung-von-importvarianten--akzeptiertes-risiko) bewusst akzeptiert. Die Dokumentation verhindert solche Fehler nicht technisch.

## 9.4 Eventual Consistency beim Dokumentimport (25.11.2026)

`Ingest.pipeline` schreibt jeden Chunk einzeln. Bestätigte Chunks sind sofort abrufbar und bleiben bei einem Abbruch gespeichert. Die Pipeline gibt die Startnummer für den nächsten Aufruf aus. Die manuelle Fortsetzung per `--start` verarbeitet die verbleibenden Chunks. Nach dem letzten erfolgreichen Write entfernt `DELETE /chunks` die überzähligen Chunks desselben Dokuments im selben Embedding-Set. Die Konsistenz des vorgesehenen Datenstands wird mit dem erfolgreichen Abschluss einschließlich Bereinigung erreicht. [Importkonzept 8.4](8-4-importkonzept.md#847-identitaet-wiederholung-und-abschluss)

Eine automatische Sicherung der bisherigen Chunks vor jedem Wiederholungsimport ist fachlich nicht erforderlich. Für die Importversuche zählt der vollständig verarbeitete Zielstand. Der vorherige Stand lässt sich bei Bedarf aus der ursprünglichen Eingabe mit der zugehörigen Konfiguration erneut importieren. Automatische Sicherungen würden bei den häufigen Wiederholungen zusätzliche Lese- und Schreibvorgänge verursachen und die Laufzeit aus Projektsicht zu stark erhöhen. Der vorübergehend gemischte Datenstand wird daher bewusst akzeptiert. [Risiko R-03](11-1-risiken.md#r-03--vorübergehend-inkonsistenter-chunkbestand-bei-importabbrüchen)

Historische Aenderungs- und Pruefnachweise: [Changelog](../changelog.md).

## 9.5 Herkunft und Reihenfolge in der Chunk-ID abbilden (27.11.2026, TS-23)

**Status** · entschieden

Bei der Auswertung muss jederzeit direkt an der Chunk-ID erkennbar sein, aus welchem Dokument ein Treffer stammt und wo er ungefähr im Dokument liegt. Die ID behält deshalb das Format `<Dateistamm>-<Chunknummer>`. Der Dateistamm bezeichnet den Dateinamen ohne die letzte Erweiterung. Die bei 1 beginnende Chunknummer gibt die Reihenfolge im Dokument für den jeweiligen Import an. Beispielsweise bezeichnet `rom.band1-17` den 17. Chunk aus `rom.band1.txt`. [Importkonzept 8.4](8-4-importkonzept.md#847-identitaet-wiederholung-und-abschluss)

Eine künstliche ID mit separat gespeicherter Dokumentkennung und Chunknummer wurde erwogen. Für diese Anwendung müssten viele Abfragen und Reports dann zusätzliche Felder abrufen und ausgeben, um die Herkunft und ungefähre Position eines Treffers sichtbar zu machen.

Import und Löschabfrage verwenden das Format gemeinsam. Eine spätere Formatänderung muss deshalb beide Bausteine und bestehende IDs berücksichtigen. Der Dateistamm muss innerhalb eines Embedding-Sets eindeutig sein. [TS-23](11-2-technische-schulden.md#ts-23--dokumentzugehörigkeit-an-das-format-der-chunk-id-gekoppelt) · [Risiko R-02](11-1-risiken.md#r-02-dateistamm-als-dokumentidentitaet)

## RAG-Orchestrierung als einziger CLI-Verarbeitungspfad (TS-09)

`interact.py` delegiert die Verarbeitung an `/process` und übernimmt Argumentprüfung, Darstellung und Dateiexport. Reranking und Modellwahl sind explizite API-Parameter. Ursprüngliche und ausgewählte Treffer stehen in eigenen Antwortfeldern. API-Clients erhalten ohne neue Parameter kein Reranking. `analyze.py` delegiert Retrieval, Distanzdiagnostik und Antwortgenerierung an die Evaluationsendpunkte derselben RAG-API. Der Standard für das Antwortmodell ist `gemma4:e4b`. Die Schnittstelle unterstützt weder Fortschrittsstreaming noch einen Export nach späteren Providerfehlern.

## Stateless Evaluationsendpunkte

Die drei historischen /evaluate-Endpunktnamen werden als aktuelle RAG-HTTP-Adapter umgesetzt; historische SQL- und LangChain-Orchestrierung werden nicht uebernommen. Einheitliche Chunkobjekte statt blossen Textlisten bewahren Identitaet, Distanzen und Scores ueber alle Schritte. next_request transportiert Frage, Ergebnisse und Folgeparameter explizit, damit gespeicherte Zwischenergebnisse fuer getrennte Versuchsreihen ausreichen. Gemeinsame Providerfunktionen verhindern einen zweiten fachlichen Verarbeitungskern. Goldvergleich ist eine spaetere Anwendung dieser Schnittstellen.
