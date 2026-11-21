# 9 Architekturentscheidungen

## 9.1 Modell und Embedding-Set trennen (21.11.2026, TS-01)

`embedding_set_id` bezeichnet die Menge zusammengehöriger Vektoren aus einer gemeinsamen Verarbeitungslogik. Die Kennung bezeichnet keinen einzelnen Ausführungslauf und ist unabhängig vom Modellnamen. Wiederholte Imports dürfen dasselbe Set verwenden. Vollständige Konfigurationsidentität und Importlaufverwaltung bleiben TS-04/TS-05.

Import3, CLI und RAG lesen Modell und Set aus `rag/embedding_config.py`. Beide Einstellungen sind unabhängig über Umgebungsvariablen überschreibbar. Der Standard verweist auf das bestehende Set `snowflake-arctic-embed2-v2`; das Modell bleibt `snowflake-arctic-embed2`.

Die Datenbankspalte wird transaktional umbenannt; Kennungen und Vektoren bleiben unverändert. Vor jeder Bestandsmigration erzeugt das Werkzeug ein vollständiges Backup und prüft dessen Inhaltsverzeichnis. Es gibt keine automatische Migration beim API-Start. Damit sind Backup und Umstellungszeitpunkt explizite Betriebsschritte.

Die Vector-API akzeptiert `embedding` weiterhin als Alias und liefert beide Namen in Einzelchunk- und Suchantworten. RAG akzeptiert weiterhin `filter`. Widersprüchliche Doppelangaben werden vor SQL- oder Modellzugriff mit HTTP 400 zurückgewiesen. Das Entfernen der Aliase benötigt eine spätere ausdrückliche Schnittstellenentscheidung. Ungefilterte Vector-Abfragen bleiben möglich.

Migration und neue API-Version müssen gemeinsam ausgerollt werden; alte API-Versionen erwarten den alten Spaltennamen. Rückweg und Restore sind im README dokumentiert.

## 9.2 Chunktext explizit benennen (21.11.2026)

Die Spalte `metadata` enthält den zur Kontextbildung verwendeten Text und heißt künftig `chunktext`. Der Name gilt durchgängig in SQL, Vector-API, Import, Retrieval, Reranking und Analyse. Es gibt keinen Kompatibilitätsalias; externe API-Clients müssen gleichzeitig aktualisiert werden. `/find` durchsucht `chunktext` weiterhin mit `ILIKE`.

`002_chunktext.sql` benennt nur die Spalte um. Inhalte einschließlich NULL, Vektoren, Schlüssel und Index bleiben erhalten. Der vorhandene Backup-Migrationsmechanismus führt die Migration mit `--migration 002_chunktext.sql` erst nach einem geprüften vollständigen Dump aus. Migration und API-Aktualisierung erfolgen bei gestoppten APIs. Ein erneutes Embedding ist nicht erforderlich.

Nachweis am 21.11.2026: 45 Unit-Tests und 7 Podman-Integrationstests mit `--include-rag --include-ollama` bestanden, einschließlich Backup-Wiederherstellung, Migration, echtem Keyword-/Embedding-Import und RAG-E2E. Die optionale Reranker-Integration wurde nicht aktiviert; die Umstellung der CLI-Rerankingdaten auf `chunktext` ist durch einen Unit-Test abgesichert. Die Bestandsmigration erhielt alle 10.378 Zeilen mit identischen Prüfsummen über IDs, Set-Kennungen, Vektoren und Text. Backup vor der Migration: `backups/20261121-145838-030786.dump`.
