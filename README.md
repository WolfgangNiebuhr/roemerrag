# knowledge-experimental-ki
Experimentelle KI-Komponenten in Kubernetes

## Umgebung am MEAP einrichten

Installieren aus dem Softwarecenter:
- tkgi
- kubectl
- Python

CommandShell-Window vorbereiten (DEV-Umgebung):

```bash
set no_proxy=.k8s.dev.datev.de
set https_proxy=www-proxy-p-wl-iap.services.datev.de:8880
set all_proxy=socks5://socks-proxy-p-iap.services.datev.de:1080
```

Einmal pro Session:

login-k8s.py ausführen im Command-Window

## Deployment auf kubernetes

* Die Setups im Verzeichnis global-setup müssen zuerst ausgeführt werden, diese werden von anderen ggf
gemeinsam genutzt
* registry-setup ist nicht nutzbar, in der entstehenden registry kann man zwar Images speichern, diese sind jedoch wegen des fehlenden https-Zugangs nicht in den Deployments nutzbar. Dazu bäuchte es entweder zum pod-dnsnamen passende zertikate oder eine Einstellung am zugrundeliegenden worker-node
* Zugriff auf die Services bekommt man im Moment nur via port-forward, etwa
```bash
kubectl port-forward -n experimental service/reranker 6000:6000
```
port-forward ist ein blocking-call, man braucht für jeden weiterzuleitenden port ein eigenes cmd-Fenster

Ports:
* (5000: Container-registry)
* 5432: Postgres "nativ"
* 5500: Vektor-api
* 5600: rag-api
* 6000: reranker-api
* 11434: Ollama, nutzbar mit passenden Modellen für Embedding und Textgenerierung

Konfiguration:
* Embedding snowflake-arctic-embed2 , Vektorgröße 1024, via Ollama
* LLM : phi3:mini  , via Ollama
  * phi-3:mini ist auf Faktenwissen, Code und kurze Dialoge optimiert.
* Pgvector-DB: Index mit hnsw , euklidischer Abstand
* Reranker: cross-encoder/ms-marco-MiniLM-L6-v2 via Huggingface-Library
* rag-api : bindet alle komponenten zusammen, anfragen an port 5600, Endpunkt /process , parameter query, metric, num_results

## Debugging

Wie geht es dem Cluster allgemein:

```bash
kubectl top pods --all-namespaces
```

viele Fehler sieht man in den logs:
```bash
kubectl logs -n experimental <podname>
``` 

In die Datenbank kann man auch reinsehen:

```bash
kubectl exec -it <postgres-pod-name> -n experimental -- psql -U admin -d vector_db
```
Ersetze <postgres-pod-name> durch den Namen des PostgreSQL-Pods.

Backup auf lokales System.
```bash
kubectl exec -it <postgres-pod-name> -n experimental -- pg_dump -U admin -d vector_db > mydb_backup.sql
```

Backup wieder herstellen:
Datei in Pod kopieren und dort ausführen:
```bash
kubectl cp mydb_backup.sql experimental/<postgres-pod-name>:/tmp/mydb_backup.sql
kubectl exec -it <postgres-pod-name> -n experimental -- bash
psql -U admin -d vector_db -f /tmp/mydb_backup.sql
```


Man kann im psql auch die Größe der Datenbank abfragen:
```sql
SELECT pg_size_pretty(pg_database_size(current_database())) AS db_size;
```
(Zur Einschätzung: Die Testdatenbank mit Band 1 (pg3060.txt) hat eine Größe von 20 MB)

bzw pro Tabelle: Gesamtspeicher, Datenspeicher, Indexgröße)

```sql
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS data_size,
    pg_size_pretty(pg_total_relation_size(relid) - pg_relation_size(relid)) AS index_size
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
```

Für die Daten zu Band 1 (pg3060.txt) und für alle 6 Bände sieht das so aus:

| table_name | total_size | data_size | index_size |
|------------|------------|-----------|------------|
| vectors    | 12 MB      | 768 kB    | 12 MB      |
| vectors (alle) | 129 MB | 8568 kB | 121 MB |

**Ollama:**

geladene Modelle abfragen (Voraussetzung: port-forward läuft):
```bash
curl http://localhost:11434/api/tags
```

Modell nachladen (Voraussetzung: port-forward läuft):
```bash
curl http://localhost:11434/api/pull -d "{\"name\": \"mixtral\"}" -H "Content-Type: application/json"
```