# 9 Architekturentscheidungen

## 9.1 Modell und Embedding-Set trennen (21.11.2026, TS-01)

`embedding_set_id` bezeichnet die Menge zusammengehöriger Vektoren aus einer gemeinsamen Verarbeitungslogik. Die Kennung bezeichnet keinen einzelnen Ausführungslauf und ist unabhängig vom Modellnamen. Wiederholte Imports dürfen dasselbe Set verwenden. Die Konfiguration wird gemäß Abschnitt 9.3 manuell dokumentiert; Importlaufverwaltung bleibt TS-05.

Import3, CLI und RAG lesen Modell und Set aus `rag/embedding_config.py`. Beide Einstellungen sind unabhängig über Umgebungsvariablen überschreibbar. Der Standard verweist auf das bestehende Set `snowflake-arctic-embed2-v2`; das Modell bleibt `snowflake-arctic-embed2`.

Die Datenbankspalte wird transaktional umbenannt; Kennungen und Vektoren bleiben unverändert. Vor jeder Bestandsmigration erzeugt das Werkzeug ein vollständiges Backup und prüft dessen Inhaltsverzeichnis. Es gibt keine automatische Migration beim API-Start. Damit sind Backup und Umstellungszeitpunkt explizite Betriebsschritte.

Die Vector-API akzeptiert `embedding` weiterhin als Alias und liefert beide Namen in Einzelchunk- und Suchantworten. RAG akzeptiert weiterhin `filter`. Widersprüchliche Doppelangaben werden vor SQL- oder Modellzugriff mit HTTP 400 zurückgewiesen. Das Entfernen der Aliase benötigt eine spätere ausdrückliche Schnittstellenentscheidung. Ungefilterte Vector-Abfragen bleiben möglich.

Migration und neue API-Version müssen gemeinsam ausgerollt werden; alte API-Versionen erwarten den alten Spaltennamen. Rückweg und Restore sind im README dokumentiert.

## 9.2 Chunktext explizit benennen (21.11.2026)

Die Spalte `metadata` enthält den zur Kontextbildung verwendeten Text und heißt künftig `chunktext`. Der Name gilt durchgängig in SQL, Vector-API, Import, Retrieval, Reranking und Analyse. Es gibt keinen Kompatibilitätsalias; externe API-Clients müssen gleichzeitig aktualisiert werden. `/find` durchsucht `chunktext` weiterhin mit `ILIKE`.

`002_chunktext.sql` benennt nur die Spalte um. Inhalte einschließlich NULL, Vektoren, Schlüssel und Index bleiben erhalten. Der vorhandene Backup-Migrationsmechanismus führt die Migration mit `--migration 002_chunktext.sql` erst nach einem geprüften vollständigen Dump aus. Migration und API-Aktualisierung erfolgen bei gestoppten APIs. Ein erneutes Embedding ist nicht erforderlich.

## 9.3 Set-Konfiguration manuell dokumentieren (21.11.2026)

Die Zuordnung von Verarbeitungsparametern zu `embedding_set_id` wird auf ausdrückliche Projektentscheidung ausschließlich im [Set-ID-Verzeichnis, Abschnitt 8.2](8-2-embedding-sets.md) gepflegt. Eine zusätzliche technische Speicherung, Konfigurationsprüfung oder automatische Vergabe von Set-Identitäten ist nicht vorgesehen. Der bisherige technische Abbauvorschlag aus TS-04 wird damit ersetzt.

Vor neuen Imports werden Set-ID und tatsächliche Parameter manuell dokumentiert; bei geänderter Verarbeitung wird eine neue Kennung gewählt. Historisch unbekannte Angaben bleiben als unbekannt gekennzeichnet. Vorhandene Daten bleiben erhalten. Die Möglichkeit einer versehentlichen Vermischung oder Überschreibung bei falsch gewählter Kennung wird als [Risiko R-01](11-1-risiken.md#r-01--manuelle-zuordnung-von-importvarianten--akzeptiertes-risiko) bewusst akzeptiert. Die Dokumentation verhindert solche Fehler nicht technisch.

Historische Aenderungs- und Pruefnachweise: [Changelog](../changelog.md).
