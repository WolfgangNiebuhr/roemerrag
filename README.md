# Römer-RAG

Das RAG-System dient dazu, unterschiedliche Parameter und Strategien für Retrieval Augmented Generation experimentell zu untersuchen und ihre Ergebnisse zu vergleichen. Texte zur römischen Geschichte bilden den Beispielkorpus. Der Experimentator importiert Texte, variiert Verarbeitung und Modelle, stellt Fragen und beurteilt die gefundenen Textstellen, generierten Antworten und verfügbaren Metriken.

Das System unterstützt folgende Aufgaben:

- Texte in Chunks zerlegen, optional mit Keywords anreichern, Embeddings erzeugen und zusammen mit dem Quelltext speichern.
- Importvarianten über Set-Kennungen auswählen und Retrieval mit unterschiedlichen Suchparametern untersuchen.
- Antworten aus gefundenen Textabschnitten generieren und Quell-Chunk-IDs sowie Generierungsmetriken ausgeben.
- Modelle und Reranking über lokale Werkzeuge beziehungsweise HTTP-Schnittstellen erproben. Die RAG-API kann den optionalen Reranker aufrufen.


Änderungen und Ausrollnachweise stehen im [Changelog](changelog.md). Diese README beschreibt Einrichtung, Bedienung und aktuellen Schnittstellenvertrag.

Die arc42-Dokumentation beginnt mit [Einführung und Zielen](docs/1-einfuehrung-und-ziele.md), [Randbedingungen](docs/2-randbedingungen.md) und [Kontextabgrenzung](docs/3-kontextabgrenzung.md).

## Voraussetzungen

- Podman mit laufender Podman-Machine (unter Windows)
- Python für Import- und Analysewerkzeuge
- Ollama, falls lokale Sprach- oder Embedding-Modelle verwendet werden

**IPv6 und `localhost` unter Windows.** Python kann `localhost` zuerst zu `::1` auflösen. Ist der veröffentlichte Podman-Port der Vector-API nur über IPv4 erreichbar, wartet Python auf die Ablehnung der IPv6-Verbindung, bevor es `127.0.0.1` versucht. In der lokalen Messung kostete das rund zwei Sekunden pro Verbindungsversuch. Der Standard `127.0.0.1` verbindet sich direkt über IPv4. Für einen anderen Host oder Port lässt sich `IMPORT_VECTOR_URL` weiterhin setzen. Die Windows-Beispiele fuer Vector-API, RAG-API und Reranker sowie die HTTP-Aufrufe an den Podman-Teststack verwenden daher ebenfalls `127.0.0.1`.

## Lokalen Stack starten

Die Befehle gelten für PowerShell im Projektstamm und einen Neuaufbau. Bereits vorhandene Container nicht erneut unter denselben Namen anlegen. PostgreSQL/pgvector, Vector-API und RAG-API laufen mit Podman; Ollama läuft als Windows-Hintergrund-App. Der Reranker wird optional durch die RAG-API aufgerufen. PostgreSQL-Daten bleiben im Named Volume erhalten; Ollama verwaltet seine Modelle separat im Windows-Benutzerprofil. Eine GPU ist für den Grundbetrieb nicht erforderlich.

### Ollama auf Windows vorbereiten

Ollama installieren und einmalig die dauerhafte Netzwerkbindung für den Benutzer setzen:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
```

Ollama danach über das Tray-Menü beenden und aus dem Startmenü neu starten. Modelle bereitstellen:

```powershell
ollama pull snowflake-arctic-embed2
ollama pull gemma4:e4b
# Zusätzlich für den Import mit Keyword-Anreicherung:
ollama pull gemma3:4b
```

Die Bindung nimmt Verbindungen auf allen IPv4-Schnittstellen an; den Zugriff über die Windows-Firewall auf die benötigte Umgebung begrenzen. Netzwerkgrenzen, Automatik und Fehlersuche erklärt die [Laufzeitsicht](docs/6-laufzeitsicht.md).

### Images bauen

```powershell
podman machine start
podman build -t vectordb:local -f Vector/Dockerfile Vector
python scripts/build_image.py vectorapi --tag vectorapi:local
python scripts/build_image.py rag-api --tag rag-api:local
# Optional:
python scripts/build_image.py reranker --tag reranker:local
```

### Vector-Datenbank und API starten

```powershell
podman pod create --name vectorpod -p 5432:5432 -p 5500:5500 -p 5600:5600
podman volume create pgvector-data
podman run -d --name vectordb --pod vectorpod -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vector_db -e PGDATA=/var/lib/postgresql/data/pgdata -v pgvector-data:/var/lib/postgresql/data localhost/vectordb:local
# Erst fortfahren, sobald der folgende Befehl Erfolg meldet; ggf. wiederholen:
podman exec vectordb pg_isready -U admin -d vector_db
podman run -d --name vector-api --pod vectorpod -e DB_HOST=127.0.0.1 -e DB_PORT=5432 -e DB_USER=admin -e DB_PASSWORD=admin -e POSTGRES_DB=vector_db localhost/vectorapi:local
```

Für den direkten Zugriff mit einem auf Windows installierten PostgreSQL-Client den veröffentlichten Port über IPv4 ansprechen. Auch Port 5432 war bei der lokalen Messung nur per IPv4 erreichbar. Der Verbindungsversuch zu `::1` wurde nach rund zwei Sekunden abgelehnt.

```powershell
psql -h 127.0.0.1 -p 5432 -U admin -d vector_db
```

### RAG-API starten

Warum Windows-`localhost` im Container nicht genügt, wozu der WSL-Gateway dient und wie die automatische Ermittlung funktioniert, erklärt die [Laufzeitsicht](docs/6-laufzeitsicht.md). Dort stehen auch die Bedeutung der Umgebungsvariablen und Schritte zur Fehlersuche.

Das aktuelle RAG-Image ermittelt Ollama beim ersten Modellaufruf automatisch. Im vorhandenen Vector-Pod nutzt es die lokale Vector-API:

```powershell
python scripts/build_image.py rag-api --tag rag-api:local
podman run -d --name rag-api --pod vectorpod -e VECTOR_API_URL=http://127.0.0.1:5500/search localhost/rag-api:local
```

Der Pod muss wie oben Port 5600 veröffentlichen. Bei einem älteren Pod ohne dieses Mapping kann die RAG-API stattdessen separat gestartet werden; den vorhandenen Datenbank-Pod dabei erhalten. Nur eine der beiden RAG-Startvarianten ausführen:

```powershell
podman run -d --name rag-api -p 5600:5600 localhost/rag-api:local
```

Diese Variante nutzt `http://host.containers.internal:5500/search` für die bereits veröffentlichte Vector-API. Falls diese Adresse in der eigenen Netzwerkkonfiguration nicht erreichbar ist, `VECTOR_API_URL` beim Containerstart explizit setzen. Die automatische Gateway-Ermittlung gilt nur für Ollama.

CLI und RAG verwenden gemeinsame Defaults aus `rag/embedding_config.py`: `EMBEDDING_MODEL=snowflake-arctic-embed2` und `EMBEDDING_SET_ID=snowflake-arctic-embed2-v2`. Beide sind unabhängig über gleichnamige Umgebungsvariablen konfigurierbar. Die Importpipeline liest Embeddingmodell und Set-Kennung aus ihrer Versuchskonfiguration. Die Set-Kennung wählt gespeicherte Daten und legt kein Modell fest.

Die Vector-API verwendet `embedding_set_id` in Anfragen und Antworten. Der frühere Parameter `embedding` führt zu HTTP 400. Einzelabruf, Textsuche und Vektorsuche benötigen eine Set-ID. Nur `GET /chunks` zählt bei fehlender Set-ID alle Datensätze. RAG verwendet `embedding_set_id` und setzt ohne Angabe das konfigurierte Standard-Set ein. Der frühere Parameter `filter` führt bei `/process` und den Evaluationsendpunkten zu HTTP 400. Die CLI wählt das Set über `--embedding-set-id`.

Gespeicherte Vektoren liefert die Vector-API ebenso wie den RAG-Fragevektor auf Anfrage als JSON-Zahlenlisten. Beim Einzelabruf `include_vector=true` in der URL setzen, etwa `GET /chunks/pg3060-1?embedding_set_id=snowflake-arctic-embed2-v2&include_vector=true`. Bei `POST /search` den booleschen Wert `include_vector: true` im JSON-Body setzen. Ohne Opt-in fehlt `vector` in diesen Antworten.

### Bestehende Datenbank migrieren

Der Quelltext eines Chunks heißt in Datenbank und API `chunktext` (bei ?lteren Datenbanken `metadata`). Importer, Retrieval, Reranking, Analyse und `/find` verwenden den neuen Namen. Es gibt keinen Alias für `metadata`; externe Clients müssen gleichzeitig aktualisiert werden.

Für eine Datenbank, deren Set-Spalte bereits `embedding_set_id` heißt, nach dem Bauen der neuen API-Images und Stoppen beider APIs ausführen:

```powershell
python scripts/migrate_embedding_set_id.py --migration 002_chunktext.sql
```

Auch dieser Schritt erstellt und prüft zuerst einen neuen vollständigen Dump unter `backups/`. Die Migration benennt ausschließlich `metadata` in `chunktext` um, ist transaktional und wiederholbar und berechnet keine Embeddings neu. Rückweg bei gestoppten APIs: `ALTER TABLE vectors RENAME COLUMN chunktext TO metadata;`, dann die vorherigen API-Versionen starten. Bei älteren Datenbanken zuerst die nachfolgende Set-Migration und anschließend die Umbenennung ausführen.

Vor dem Start der aktuellen APIs die Pflichtfeldregel auf bestehende Datenbanken anwenden:

```powershell
python scripts/migrate_embedding_set_id.py --migration 003_required_chunktext.sql
```

Die Migration erstellt und prüft zuerst einen Dump. Bei vorhandenen ungültigen Texten bricht sie ohne Datenänderung ab. Zur Prüfung dient `SELECT id, chunk_id, embedding_set_id FROM vectors WHERE chunktext IS NULL OR length(btrim(chunktext, E' \n\r')) = 0;`. Nach Korrektur der betroffenen Texte kann die Migration erneut ausgeführt werden. Neue Datenbanken erhalten die Regel bei der Initialisierung.

Kein Neuimport und kein erneutes Embedding: Die Migration benennt nur `vectors.embedding` in `embedding_set_id` um. Kennungen, Vektoren, IDs, Metadaten, Constraints und Index bleiben erhalten. Änderungen an `init.sql` allein aktualisieren keine vorhandene Datenbank.

Zuerst neue API-Images bauen, externe schreibende Clients anhalten und beide APIs stoppen:

```powershell
python scripts/build_image.py vectorapi --tag vectorapi:local
python scripts/build_image.py rag-api --tag rag-api:local
podman stop rag-api vector-api
python scripts/migrate_embedding_set_id.py
# Nur nach Erfolg: API-Container mit den Startbefehlen oben neu erstellen.
```

Das Werkzeug erstellt einen vollständigen binären `pg_dump -Fc` unter `backups/` (nicht versioniert) und prüft ihn mit `pg_restore --list`, bevor es `Vector/migrations/001_embedding_set_id.sql` ausführt. Bei Backupfehlern wird nicht migriert. Optionen: `--container`, `--user`, `--database`, `--backup-dir`. Die SQL-Migration ist transaktional und wiederholbar. Die Inhaltsverzeichnisprüfung ersetzt keinen Restore-Test; die Podman-Integration prüft zusätzlich die tatsächliche Wiederherstellung in eine eigene Datenbank.

Rückweg: APIs stoppen, `ALTER TABLE vectors RENAME COLUMN embedding_set_id TO embedding;` ausführen und alte API-Versionen starten. Für eine vollständige Wiederherstellung das Dump mit `podman cp` in den DB-Container kopieren und dort `pg_restore -U admin -d <leere-zieldatenbank> <dump-pfad>` ausführen. Bestehende Volumes nicht löschen.

Die Ollama-Ermittlung prüft zuerst `host.containers.internal:11434`. Unter WSL werden anschließend die IPv4-Default-Gateways aus `/proc/net/route` geprüft. Nur ein erreichbarer Endpunkt mit einer Ollama-Modellliste wird übernommen und für die Prozesslaufzeit gespeichert. Bei Nichterreichbarkeit versucht der nächste Request die Ermittlung erneut. Nach einem WSL-Neustart startet der Containerprozess mit einer neuen Ermittlung. Bei einer eigenen Bridge kann deren Gateway statt des Windows-Gateways sichtbar sein; dafür oder für entfernte Modellserver lässt sich `OLLAMA_BASE_URL` beim Containerstart ausdrücklich setzen. Diese Einstellung hat Vorrang vor der Automatik. Ollama muss weiterhin aus der WSL-Umgebung erreichbar sein.

### Optionalen Reranker starten

```powershell
podman run -d --name reranker -p 5000:5000 localhost/reranker:local
Invoke-RestMethod http://127.0.0.1:5000/health
```

Der erste Health-Aufruf lädt das Modell in den Prozess und kann dauern. Das Image lädt `cross-encoder/ms-marco-MiniLM-L6-v2` bereits beim Build herunter. Der Standardstart reicht keine GPU durch; Hinweise für einen optionalen GPU-Start stehen unten.

Das Rerankermodell lässt sich pro Anfrage ohne erneuten Containerstart auswählen:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/rerank -Method Post -ContentType application/json -Body '{"model":"cross-encoder/ms-marco-TinyBERT-L2-v2","query":"Was ist Rom?","documents":["Rom ist eine Stadt.","Ein Fisch schwimmt."]}'
python interact.py --query "Was ist Rom?" --reranker cross-encoder/ms-marco-TinyBERT-L2-v2
```

`model` ist optional; ohne Angabe gilt das beim Start konfigurierte `RERANK_MODEL`. Ein expliziter Wert ändert diesen Default nicht. Die Antwort nennt das ausgewählte Modell als `model`; die CLI zeigt es an. Erwartet wird ein CrossEncoder mit einem skalaren Score pro Frage-Dokument-Paar. Modelle, die eigenen Remote-Code benötigen, sind nicht unterstützt. Siehe den [CrossEncoder-Vertrag](https://www.sbert.net/docs/package_reference/cross_encoder/model.html).

Der Dienst hält ein Modell aktiv. Gleiche Auswahl verwendet es erneut, ein Wechsel lädt ein anderes Modell; ein Rückwechsel lädt die Modellinstanz erneut aus dem lokalen Cache. Noch nicht vorhandene Gewichte benötigen beim ersten Aufruf einen Download. Laden und Inferenz laufen nacheinander unter einer gemeinsamen Sperre. Der Wechsel kann daher dauern und vorübergehend Speicher für beide Modelle benötigen. Ladefehler liefern HTTP 503 mit der angefragten Modellkennung, ohne auf ein anderes Modell auszuweichen; das vorher aktive Modell bleibt verfügbar. Ungültige Modellparameter liefern HTTP 400. Leere Dokumentlisten liefern eine leere Ergebnisliste mit der ausgewählten Kennung, ohne ein Modell zu laden. `/health` zeigt das aktive Modell und lädt nur bei noch ungeladenem Dienst den Default.

Modellwechsel erfordern weder einen Image-Build noch einen Neustart. Der isolierte Integrationstest `python -m pytest -c tests/pytest.ini tests/podman/test_reranker.py --include-reranker` prüft zwei echte Modelle und den Rückwechsel; dafür muss der Download des zusätzlichen Testmodells möglich sein.

### Einzelne Dienste und Details

Die Vector-spezifischen Hinweise stehen in [Vector/README.txt](Vector/README.txt). Für den aktuellen Gesamtaufbau gelten die Befehle oben. Verzeichnisse namens `k8s` sind historische Referenzen. Die [Bausteinsicht](docs/5-bausteinsicht.md), [Laufzeitsicht](docs/6-laufzeitsicht.md), [Verteilungssicht](docs/7-verteilungssicht.md) und das [Testkonzept](docs/8-1-testkonzept.md) beschreiben den Podman-Betrieb. Die Verteilungssicht zeigt Windows-/WSL-Grenzen, Pods, Container, Ports und persistente Speicher sowie die Unterschiede zwischen Neuaufbau, bestehendem Betrieb und Teststack.

### Automatisierte Tests: Unit und Podman-Integration

Die Testarten sind getrennt: containerfreie Unit-Tests liegen in `tests/unit`; Podman- und externe Dienst-Integrationstests liegen in `tests/podman`. `tests/conftest.py` stellt gemeinsame pytest-Optionen bereit. `tests/podman/conftest.py` baut den isolierten Containerstack auf und räumt ihn anschließend ab.
Die pytest-Konfiguration deaktiviert den Cache-Provider (`-p no:cacheprovider`), damit kein Zugriff auf `.pytest_cache` erforderlich ist. Die Chunking-Tests legen eindeutige UTF-8-Testdateien direkt in `tests/unit` an und löschen sie selbst. Diese Chunking-Tests benötigen keine temporären Verzeichnisse. Pytest-Tempverzeichnisse (`tmp_path`/`tmpdir`) liegen durch `tests/conftest.py` immer außerhalb des Checkouts in einem eindeutigen Unterverzeichnis des System-/Benutzer-Tempbereichs. Ein explizites `--basetemp` innerhalb des Projekts wird vor Testbeginn zurückgewiesen; auch ein Tempbereich aus Umgebungsvariablen darf nicht im Projekt liegen. `PYTEST_DEBUG_TEMPROOT` kann die Fixture-Verzeichnisse nicht ins Projekt umleiten. Migrationstests verwenden ebenfalls externe Tempverzeichnisse. Private Windows-ACLs solcher Verzeichnisse bleiben damit außerhalb des Projekts.

Voraussetzungen für Unit-Tests sind Python und die Testabhängigkeiten. Podman-Integration benötigt zusätzlich eine gestartete Podman-Machine. Ollama-Tests setzen eine Host-Instanz auf `localhost:11434` und das Modell `snowflake-arctic-embed2` voraus.
Bei Exitcode 125 zuerst `podman info` aus derselben Ausfuehrungsumgebung pruefen. Meldet Podman beim Lesen seiner SSH-Identitaet unter `%USERPROFILE%\.local\share\containers\podman\machine` einen Zugriffsfehler, benoetigt der Testprozess Zugriff auf diese Datei. In einer eingeschraenkten Agent-Sandbox die isolierten Tests mit genehmigtem Zugriff ausserhalb der Sandbox ausfuehren; Schluessel und Dateirechte unveraendert lassen.


```powershell
python -m pip install -r tests/podman/requirements.txt
# Nur Unit-Tests
python -m pytest -c tests/pytest.ini tests/unit
# Standard-Integration: PostgreSQL/pgvector und Vector-API
python -m pytest -c tests/pytest.ini tests/podman
```

Optionale Integrationstests und gemeinsamer Lauf:

```powershell
python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker
python -m pytest -c tests/pytest.ini tests/podman --include-ollama
# Ende zu Ende: Testkorpus importieren und Frage mit echten Modellen beantworten
python -m pytest -c tests/pytest.ini tests/podman/test_rag_e2e.py --include-rag --include-ollama
# Unit-Tests plus alle Integrationstests
python -m pytest -c tests/pytest.ini tests --all
# Ohne Podman; optionale Ollama-Tests bleiben ohne --include-ollama deaktiviert
python -m pytest -c tests/pytest.ini tests --no-podman
# Test-Pod und Volume zur Fehlersuche behalten
python -m pytest -c tests/pytest.ini tests --all --keep-podman
```

`--all` aktiviert die optionalen RAG-, Reranker- und Ollama-Gruppen. Der Reranker lädt sein Modell beim Image-Build. Alle Podman-Ressourcen und Testdaten sind von regulären Stack-Ressourcen getrennt.
Für den Ende-zu-Ende-Test auf dem Host vorab `ollama pull snowflake-arctic-embed2`, `ollama pull phi3:mini` und `ollama pull gemma3:4b` ausführen. Der Import verwendet `gemma3:4b` für Keywords. Embedding- und Antwortmodell müssen auch aus dem RAG-Container über den automatisch ermittelten oder explizit konfigurierten Endpunkt erreichbar sein. Podman weist dem Teststack dynamische Hostports zu; ein regulärer Stack kann parallel weiterlaufen. PostgreSQL wird nur innerhalb des Test-Pods angesprochen. Die RAG-API verwendet dort `VECTOR_API_URL=http://127.0.0.1:5500/search` für die eigene Vector-API. Außerhalb der Tests bleibt der Standard `http://host.containers.internal:5500/search` erhalten; `VECTOR_API_URL` kann ihn beim Containerstart überschreiben.

Bei Verbindungsfehlern Windows-Aufruf und Container-Aufruf getrennt prüfen; ein erfolgreicher Host-Test beweist keinen Zugriff aus dem Container. Die [Laufzeitsicht](docs/6-laufzeitsicht.md) enthält konkrete Diagnosebefehle und die dauerhafte Einrichtung der Hintergrund-App. `OLLAMA_HOST_URL` setzt die Adresse für den E2E-Import (Standard `http://localhost:11434`); `OLLAMA_CONTAINER_URL` setzt optional die Adresse aus dem Testcontainer (ohne Vorgabe: automatische Ermittlung). Beide müssen denselben Modellserver erreichen. Die Testfixture reicht die Containeradresse als `OLLAMA_BASE_URL` weiter.

Tests nutzen dieselbe automatische Ermittlung wie die reguläre RAG-API. Eine zuvor manuell gesetzte Testadresse bei Bedarf entfernen:

```powershell
Remove-Item Env:OLLAMA_CONTAINER_URL -ErrorAction SilentlyContinue
python -m pytest -c tests/pytest.ini tests/podman/test_rag_e2e.py --include-rag --include-ollama
```

`OLLAMA_CONTAINER_URL` bleibt als ausdrückliche Testkonfiguration verfügbar und wird als `OLLAMA_BASE_URL` an den Testcontainer weitergereicht. Ohne diese Variable prüft die Vorabprüfung denselben Resolver wie die RAG-API. Ein erfolgreicher Host-Test gegen `localhost` prüft den Netzwerkweg aus dem Container nicht.

Der Test prüft vor dem Import die Modellverfügbarkeit über `/api/tags`. Danach importiert er `tests/podman/fixtures/early_rome.txt` über `Ingest.pipeline` mit Keyword-Anreicherung und normalisierten Embeddings. Die Pipeline schreibt über die Vector-API des Test-Pods in ein eigenes Embedding-Set. Anschließend fragt der Test „Wer beherrschte in der Frühzeit Roms das westliche Mittelmeer“ über die RAG-API ab und prüft den Karthago-Quellabschnitt, den Antwortinhalt und Generierungsmetriken.

### NVIDIA-GPU unter Windows mit WSL2 und Podman

Der Standardstart benötigt keine GPU. Für einen optionalen NVIDIA-GPU-Start unter WSL2 werden ein passender Windows-NVIDIA-Treiber, `/dev/dxg` und die WSL-Treiberbibliotheken benötigt. Bei einem Neuaufbau kann der Reranker statt des CPU-Starts so gestartet werden:

```powershell
podman run -d --name reranker -p 5000:5000 --device /dev/dxg -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro -v /usr/lib/wsl/drivers:/usr/lib/wsl/drivers:ro -e LD_LIBRARY_PATH=/usr/lib/wsl/lib localhost/reranker:local
```

Die Geräteweitergabe allein garantiert keine CUDA-Inferenz; auch die installierte torch-Variante muss CUDA unterstützen. Diese optionale Konfiguration ist kein Bestandteil der Standard-Testfixture. Die zusätzliche Einbindung von `/usr/lib/wsl/drivers` ist erforderlich: Fehlen diese Treiberdateien, kann CUDA trotz sichtbarem `/dev/dxg` mit `cuInit: 100` scheitern.

Voraussetzungen und Prüfung:

1. Aktuellen NVIDIA-Windows-Treiber mit WSL-CUDA-Unterstützung installieren.
2. WSL2 verwenden und die Podman-Machine starten (`podman machine start`).
3. In der Podman-Machine prüfen, dass `/dev/dxg` und `/usr/lib/wsl/lib/libcuda.so.1` vorhanden sind.
4. Nach dem Start des Rerankers GPU-Erkennung prüfen:

```powershell
podman exec reranker python -c "import torch; print('CUDA verfügbar:', torch.cuda.is_available()); print('Geräte:', torch.cuda.device_count()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'keine')"
```

Bei erfolgreicher GPU-Einrichtung liefert die Prüfung `CUDA verfügbar: True` und den Namen der NVIDIA-Grafikkarte. Andernfalls Treiberbereitstellung und CUDA-Unterstützung der installierten torch-Variante prüfen; die Inferenz kann weiterhin auf CPU laufen.

### Vector-API nach Pod-Neustart

`podman pod start vectorpod` startet die Container, wartet aber nicht auf die Datenbankbereitschaft. Sobald PostgreSQL bereit ist, erholt sich die Vector-API ohne Containerneustart. Solange die Datenbank nicht verfügbar ist, liefern gültige Anfragen HTTP 503 mit Problem Details. Ungültige Requests werden vorher mit HTTP 400 zurückgewiesen. [Zeitlimits und Initialisierungsversuche](docs/8-3-error-handling.md#834-timeouts-und-wiederholungen)

Nach Änderungen an der API muss das Image neu gebaut und der API-Container neu erstellt werden; ein bloßes `podman restart` übernimmt kein neues Image:

```powershell
python scripts/build_image.py vectorapi --tag vectorapi:local
podman stop vector-api
podman rm vector-api
podman run -d --name vector-api --pod vectorpod -e DB_HOST=127.0.0.1 -e DB_PORT=5432 -e DB_USER=admin -e DB_PASSWORD=admin -e POSTGRES_DB=vector_db localhost/vectorapi:local
```

Der Datenbankcontainer und sein Volume bleiben dabei erhalten.

Der Import-Integrationstest verwendet die Importpipeline mit echter Keyword-Anreicherung und echten Embeddings. Er verwendet die Vector-API im isolierten Test-Pod, einen eindeutigen Variantenfilter und entfernt seine Chunks auch bei Fehlern. Voraussetzung: Host-Ollama (`OLLAMA_HOST_URL`, Standard `http://localhost:11434`) mit `gemma3:4b` und `snowflake-arctic-embed2`; kein RAG-Container erforderlich. Modelle vorher mit `ollama pull gemma3:4b` und `ollama pull snowflake-arctic-embed2` bereitstellen.

```powershell
python -m pytest -c tests/pytest.ini tests/podman/test_import_pipeline_integration.py --include-ollama
```

## HTTP-Fehlervertrag (TS-03)

RAG-, Vector- und Reranker-API liefern Fehler als RFC-9457-Problemobjekte direkt im Body mit `Content-Type: application/problem+json`. Das bisherige Feld `error` entfaellt. Clients verwenden `type` und den HTTP-Status; `detail` dient der Anzeige. Unbekannte Erweiterungen ignorieren. `instance` identifiziert das Fehlerereignis, `request_id` korreliert Aufrufe und entspricht dem Antwortheader `X-Request-ID`. Eigene Kennungen sind auf 1 bis 128 Zeichen aus Buchstaben, Zahlen, Punkt, Unterstrich und Bindestrich begrenzt. Interne Exceptiontexte werden nicht ausgegeben.

Vor Dienstzugriffen werden JSON-Objekte, nichtleere Textfelder, Set-Kennungen, Metriken (`euclidean`, `cosine`) und Trefferzahlen (ganze Zahl 1 bis 100, keine Booleans oder Zahlenstrings) validiert. Reranker-Dokumente sind nichtleere Strings; eine leere Liste bleibt erlaubt. Das Eingabefeld `vector` erwartet eine JSON-Zahlenliste mit genau 1024 endlichen Zahlen. Ein Listenstring ergibt HTTP 400. Cosine verbietet Nullvektoren. `POST /vectors` verlangt einen String in `chunktext` mit mindestens einem Zeichen außerhalb von Leerzeichen, LF und CR. PostgreSQL erzwingt dieselbe Regel. Ungueltige Eingaben liefern 400 vor Modell-/DB-Arbeit, fehlende Chunks 404, nicht verfuegbare Datenbanken oder Rerankermodelle 503 und unerwartete Fehler neutrale 500-Antworten. HTTP-Fehler wie 405 behalten erforderliche Header.

Die API-Images werden mit `scripts/build_image.py` aus einem temporaeren Build-Kontext gebaut (siehe Befehle oben). Das Skript kopiert ausschliesslich die pro Dienst aufgelisteten Quelldateien und das gemeinsame Paket `rag_common`; es durchsucht weder Tests noch historische Verzeichnisse. Dies umgeht den Windows-Podman-Fehler beim Lesen gesperrter Verzeichnisse trotz Ignore-Regeln. Der temporaere Kontext wird auch bei Buildfehlern entfernt. Neue Laufzeitdateien muessen in der Eingabeliste des Skripts ergaenzt werden. Nach Codeaenderungen Images neu bauen und Container neu erstellen. Weitergehende Adapterklassifikation, Importabschluss und Readiness sind noch Zielkonzept: [Kapitel 8.3](docs/8-3-error-handling.md).

Auch bei pytest-Aufrufen aus tests, tests/unit und tests/podman greift die gemeinsame Temp-/Cache-Absicherung. Ein ausdrücklich aktivierter Cache-Provider wird vor seiner Initialisierung in den externen Tempbereich (rag-pytest-cache) umgeleitet, selbst bei überschriebenem addopts/cache_dir. Grenzen (insbesondere --noconftest/--confcutdir) siehe [Testkonzept](docs/8-1-testkonzept.md); historische Prüfnachweise stehen im [Changelog](changelog.md).

## RAG-Antworten und Metriken

`/process` liefert bei leerem Retrievalkontext HTTP 200 mit status no_context, chunks [] und metrics null; es wird kein Antwortmodell aufgerufen. Fehlerhafte Retrievalantworten liefern HTTP 502 Problem Details. Bei normalen Antworten sind fehlende/ungültige Einzelmetriken null; answer_rate ist bei fehlender oder nullwertiger eval_duration null. Clients müssen null-Werte unterstützen. Nach Codeänderungen Images neu bauen und Container neu erstellen.

## CLI verwenden: Fehlerbehandlung und Validierung

`interact.py` ruft ausschliesslich die RAG-API auf (`RAG_API_URL`, Standard `http://127.0.0.1:5600/process`). Ollama, Vector-API und Reranker werden durch die API orchestriert. Die CLI behaelt Argumentpruefung, Ausgabe und lokalen Export nach `search_results.json`. Fortschrittsmeldungen und Export nach spaeteren Verarbeitungsfehlern entfallen. Exitcodes: 0 Erfolg einschliesslich no_context, 1 Verarbeitungs-/Exportfehler, 2 Argumentfehler.

Die CLI sendet metric=cosine, num_results=5, top_k=6 und das Rerankermodell explizit. `--top_k 0` deaktiviert Reranking. `--answer-model` waehlt das Antwortmodell; Standard ist fuer CLI und API `ANSWER_MODEL` beziehungsweise `gemma4:e4b`. `--embedding-set-id` waehlt das Embedding-Set. Der Export enthaelt die urspruenglichen nichtleeren Retrievalpassagen; ausgegebene ausgewaehlte Chunks entsprechen der Kontextreihenfolge. Bei no_context erfolgt kein Export.

`POST /process` akzeptiert neben query, embedding_set_id, metric und num_results die optionalen Felder `top_k` (Integer >= 0, Standard 0), `reranker` und `answer_model` (nichtleere Strings). Ohne Angabe bleiben API-Defaults metric=euclidean und Antwortmodell gemma4:e4b erhalten. Die Antwort behaelt response, metrics und chunks und ergaenzt `status` (ok/no_context), `retrieved_results` und `selected_results` (jeweils chunk_id und chunktext) sowie `reranking` (null oder model und duration in Sekunden). chunks nennt ausgewaehlte IDs. Leeres Retrieval oder leeres Reranking verhindert Generierung; metrics ist dann null.

Der API-Container benoetigt bei Reranking `RERANKER_URL` (Standard `http://host.containers.internal:5000/rerank`), optional `RERANK_MODEL`; bei gemeinsamen Pods kann die URL auf `http://127.0.0.1:5000/rerank` zeigen. Fuer das laufende System muss das RAG-Image nach dem Umbau neu gebaut und der Container neu erstellt werden. API-Clients muessen zusaetzliche Antwortfelder tolerieren.

Die Konfiguration der Zeitlimits und die Wiederholungsregeln für RAG-API, CLI und Importpipeline stehen im [Fehlerkonzept](docs/8-3-error-handling.md#834-timeouts-und-wiederholungen). Die RAG-API gibt die Request-ID als `X-Request-ID` an aufgerufene Dienste weiter.

CLI-Validierung: --metric erlaubt ausschließlich cosine und euclidean (euklidische/L2-Distanz). L2 ist kein akzeptierter Parameterwert. Ungültige Optionen werden einzeln mit Parametername und erlaubten Werten beziehungsweise Grenzen gemeldet; Exitcode 2, ohne Dienstaufruf.

CLI-Validierungsfehler werden auf Deutsch ausgegeben, einschließlich fehlender Pflichtparameter/Werte, unbekannter Optionen und ungültiger Ganzzahlen. Beispiel: Parameter --metric: 'L2' ist ungültig; erlaubt sind cosine und euclidean (L2-Distanz). Parameterabkürzungen sind deaktiviert, damit Tippfehler nicht unbemerkt als andere Option interpretiert werden. Exitcode bleibt 2.

Die Vector-API schreibt atomar auf dem Schl?ssel `(chunk_id, embedding_set_id)` und erh?lt dabei die interne ID. Ihr threadsicherer Pool umfasst maximal zehn Verbindungen; bei Ersch?pfung antwortet sie mit HTTP 503. Alle Datenbankzugriffe schlie?en ihre Transaktion ab oder rollen sie bei Fehlern zur?ck.

Pytest verwendet `--import-mode=importlib`, damit gleichnamige Unit- und Integrationstestmodule im gemeinsamen Lauf getrennt geladen werden. Die Testverzeichnisse sind fuer bestehende Helper-Imports im Python-Suchpfad eingetragen (`tests/pytest.ini`).

Die Vector-API bietet `GET /health/live` (200, `status: alive`, ohne Datenbankzugriff) und `GET /health/ready` (200, `status: ready`, nach erfolgreichem Schema-Zugriff). Fehlende Bereitschaft ergibt 503 mit Problem Details. Readiness nach einem Datenbankausfall kann zunaechst eine veraltete Verbindung verwerfen und erholt sich mit spaeteren Probes ohne API-Neustart. [Zeitlimits und Wiederholungsregeln der Vector-API](docs/8-3-error-handling.md#834-timeouts-und-wiederholungen)

Antwortmodell pro CLI-Aufruf: `python interact.py --query "Was ist Rom?" --answer-model phi3:mini`. Ohne Option gilt `ANSWER_MODEL` aus der Umgebung, sonst `gemma4:e4b`. Direkter API-Aufruf: `POST /process` mit `{"query":"Was ist Rom?","answer_model":"phi3:mini"}`. Das gewaehlte Modell muss in Ollama installiert sein; fuer den Standard `ollama pull gemma4:e4b` verwenden. Die E2E-Tests waehlen weiterhin explizit phi3:mini.

Die CLI-Ausgabe gliedert sich durch Leerzeilen in Retrieval (Treffer und Export), Reranking (Modell, Laufzeit und ausgewaehlte Chunks) und Antwortgenerierung (Antwort, Laufzeiten und Tokenmetriken). Laufzeiten erscheinen einheitlich in Sekunden mit zwei Nachkommastellen; fehlende Werte als nicht verfuegbar. Deaktiviertes oder mangels Kontext ausgelassenes Reranking wird entsprechend angezeigt.

`POST /process` liefert zusaetzlich `timings` mit `embedding_duration`, `retrieval_duration` und `pipeline_duration`, jeweils Sekunden aus einer monotonen Uhr. Embedding umfasst Endpunktaufloesung, Provideraufruf, Normalisierung und moegliche Retries; Retrieval umfasst Suche, Validierung und Entfernen leerer Texte. Die Pipelinezeit reicht vom Eintritt in die Verarbeitung nach Requestvalidierung bis unmittelbar vor Aufbau der JSON-Antwort und umfasst Reranking, Kontextbildung und Generierung. HTTP-Transport zum Client, Antwortserialisierung und lokaler Export sind nicht enthalten. Auch no_context liefert timings; Generierungsmetriken bleiben dann null. Fehlerantworten erhalten keine Teillaufzeiten.

Die bisherige Ollama-Gesamtdauer heisst `metrics.generation_duration` und erscheint in der CLI als Generierungsdauer. `metrics.total_duration` bleibt als Kompatibilitaetsalias erhalten und ist keine Pipelinezeit. Die CLI zeigt Embedding- und Retrieval-Laufzeiten im Retrievalabschnitt, Reranking separat und die RAG-Pipeline-Gesamtdauer im Abschnitt Antwortgenerierung. Alle Zeitangaben werden in Sekunden mit zwei Nachkommastellen dargestellt; die API liefert ungerundete Werte. Aeltere APIs ohne timings werden als nicht verfuegbar dargestellt.

## Einzelne RAG-Schritte evaluieren

An den Evaluationsendpunkten kann `analyze.py` Distanzdiagnostik abrufen und aus den Treffern eine Antwort erzeugen. Es ruft `/evaluate/retrieve` auf und übergibt `next_request` an `/evaluate/generate`. Die Basisadresse `RAG_API_BASE_URL` ist standardmäßig `http://127.0.0.1:5600`. `--compare-gold` aktiviert den Vergleich mit dem im Skript hinterlegten vollständigen Gold-Chunk. `--metric`, `--num_results`, `--embedding-set-id` und `--answer-model` steuern die Analyse.

```powershell
python analyze.py --query "Was ist Rom?" --metric cosine --compare-gold
```

Die RAG-API bietet drei POST-Endpunkte fuer spaetere Qualitaetsmessungen. Sie verwenden dieselben Providerfunktionen, Validierung und Modelle wie `/process`, fuehren aber nur den jeweiligen Schritt aus. Gold-Antworten und Qualitaetsscores werden noch nicht berechnet. Die historische ConfigMap dient nur als fachliche Referenz; deren SQL-Zugriffe und Feldnamen werden nicht uebernommen.

| Endpunkt | Eingabe | Ausgabe und Weiterverwendung |
|---|---|---|
| `/evaluate/retrieve` | query, optional embedding_set_id, metric (Standard euclidean), num_results (5), vector, include_distances, include_query_vector, reference_text | Treffer mit Rankingdistanz, optionaler Fragevektor, Modell/Set/Metrik, Laufzeiten, Trefferzahl und optionale Diagnostik. next_request kann an rerank oder generate gesendet werden. |
| `/evaluate/rerank` | query, results (Liste von Chunkobjekten), optional reranker und top_k (5) | results in neuer Reihenfolge, erhaltene Trefferfelder sowie rerank_score und original_index; Modell, ausgewaehlte Anzahl und Laufzeit. next_request kann direkt an generate gesendet werden. |
| `/evaluate/generate` | query, results, optional answer_model, system_prompt, user_prompt | Antwort, Kontext, Chunk-IDs, ausgewaehlte Texte, Modell, Ollama-Metriken und serverseitige Laufzeit; request erlaubt Wiederholung der Generierung. |

results enthalten mindestens `chunk_id` und `chunktext`. Zum Ueberspringen von Reranking kann der Retrieve-next_request auch direkt an generate gesendet werden (zusaetzliche Felder werden ignoriert). answer_model sowie eigene Promptvorlagen koennen bereits beim Retrieval angegeben werden und werden im next_request bis zur Generierung weitergereicht. Jeder Schritt kann ebenso mit einer gespeicherten oder von Hand erstellten Eingabe aufgerufen werden. Es gibt keinen serverseitigen Sitzungszustand und keine impliziten Folgeaufrufe.

Beispiel in PowerShell:

```powershell
$base = 'http://127.0.0.1:5600'
$retrieved = Invoke-RestMethod "$base/evaluate/retrieve" -Method Post -ContentType 'application/json' -Body (@{
    query = 'Wer beherrschte das westliche Mittelmeer?'
    embedding_set_id = 'snowflake-arctic-embed2-v2'
    num_results = 5
    top_k = 2
    answer_model = 'gemma4:e4b'
} | ConvertTo-Json)
# Objekte fuer spaetere Versuchsreihen speichern, statt Retrieval zu wiederholen.
$retrieved | ConvertTo-Json -Depth 30 | Set-Content retrieved.json -Encoding utf8
$ranked = Invoke-RestMethod "$base/evaluate/rerank" -Method Post -ContentType 'application/json' -Body ($retrieved.next_request | ConvertTo-Json -Depth 30)
$answer = Invoke-RestMethod "$base/evaluate/generate" -Method Post -ContentType 'application/json' -Body ($ranked.next_request | ConvertTo-Json -Depth 30)
$answer.response
$answer.metrics
```

Optionaler Retrieve-vector ist ein bereits vorbereiteter Vektor als JSON-Zahlenliste mit 1024 endlichen Zahlen; er wird unveraendert verwendet, nicht erneut normalisiert. Embedding entf?llt dann, embedding_model und embedding_duration sind null. Bei neuem Embedding sind vorhandene Ollama-Laufzeit-/Tokenmetriken unter metrics.embedding enthalten; fehlende Messwerte sind null und werden nicht als null Sekunden erfunden. Trefferzahl steht unter metrics.retrieved_count. Serverzeiten stehen in timings (embedding_duration/retrieval_duration/evaluation_duration beziehungsweise reranking_duration oder generation_request_duration), jeweils ungerundete Sekunden. Generierungsmetriken entsprechen `/process`.

`include_query_vector: true` gibt den verwendeten Fragevektor als JSON-Zahlenliste im Feld `vector` aus. Das ist unabhängig von `include_distances`. Folgeaufrufe in `next_request` enthalten weder Frage- noch Treffervektoren.

`include_distances: true` liefert `diagnostics.hits` in der Reihenfolge der Suchtreffer. Jeder Eintrag enthält `chunk_id`, die Rankingdistanz `distance`, `cosine_similarity` und `euclidean_distance`. Die Cosinus-Ähnlichkeit für einen Nullvektor ist `null`. Ein nichtleerer `reference_text` liefert beide Vergleichswerte in `diagnostics.reference`. Der Dienst erzeugt dabei Frage- und Referenzembedding mit demselben Modell. Die Kombination von `reference_text` mit einem vom Client gelieferten `vector` ergibt HTTP 400.

Reranking behaelt Distanzen und sonstige Trefferfelder bei. original_index bezieht sich auf die an den Reranker uebergebene Liste nach Entfernen leerer Texte. top_k=0 deaktiviert Reranking und behaelt alle nichtleeren Treffer ohne neue Scores. Leere results sind erlaubt: Rerank/Generate liefern no_context, ohne Provideraufruf; Generierungsmetriken sind null. Nichtleere Textfelder, Modellparameter und Indizes werden validiert; ungueltige Eingaben ergeben 400 Problem Details vor Dienstzugriff, defekte Providerantworten 502, Dienstausfaelle 503.

Eigene user_prompt-Vorlagen erlauben ausschliesslich `{context}` und `{question}` als Platzhalter, ohne Formatierung oder Attributzugriff; literale Klammern muessen verdoppelt werden. Ohne Vorlagen gelten dieselben Prompts wie bei `/process`. Die drei Endpunkte verwenden query/results/reranker/answer_model/system_prompt/user_prompt; die historischen Felder question/chunks/modelname/systemprompt/userprompt der ConfigMap sind keine API-Aliase. Vor Live-Nutzung RAG-Image neu bauen und Container ersetzen.

Die Importpipeline bildet Chunk-IDs aus dem Dateistamm und der Chunknummer ab 1. Aus `rom.band1.txt` entsteht `rom.band1-1`, aus `rom` entsteht `rom-1`. Der Stamm muss innerhalb eines Embedding-Sets eindeutig sein; etwa `rom.txt` und `rom.md` kollidieren weiterhin (akzeptiertes Risiko R-02). Gegenueber alten Imports mehrteiliger Dateinamen entstehen andere IDs. Vor deren Wiederholungsimport den Altbestand pruefen und Bereinigung planen; alte Schluessel werden nicht automatisch entfernt oder migriert.

## Dokumentimport

Aufrufe, Versuchskonfigurationen und Zwischenartefakte beschreibt die [Anleitung zum Dokumentimport](Ingest/README.md).
