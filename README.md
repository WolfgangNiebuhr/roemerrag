# knowledge-experimental-ki

Experimentelle KI-Komponenten lokal mit Podman ausführen.

## Voraussetzungen

- Podman mit laufender Podman-Machine (unter Windows)
- Python für Import- und Analysewerkzeuge
- Ollama, falls lokale Sprach- oder Embedding-Modelle verwendet werden

## Lokalen Stack starten

Die Befehle gelten für PowerShell im Projektstamm und einen Neuaufbau. Bereits vorhandene Container nicht erneut unter denselben Namen anlegen. PostgreSQL/pgvector, Vector-API und RAG-API laufen mit Podman; Ollama läuft als Windows-Hintergrund-App. Der Reranker ist optional und nicht in den RAG-Ablauf eingebunden. PostgreSQL-Daten bleiben im Named Volume erhalten; Ollama verwaltet seine Modelle separat im Windows-Benutzerprofil. Eine GPU ist für den Grundbetrieb nicht erforderlich.

### Ollama auf Windows vorbereiten

Ollama installieren und einmalig die dauerhafte Netzwerkbindung für den Benutzer setzen:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_HOST", "0.0.0.0:11434", "User")
```

Ollama danach über das Tray-Menü beenden und aus dem Startmenü neu starten. Modelle bereitstellen:

```powershell
ollama pull snowflake-arctic-embed2
ollama pull phi3:mini
# Zusätzlich für den Import mit Keyword-Anreicherung:
ollama pull gemma3:4b
```

Die Bindung nimmt Verbindungen auf allen IPv4-Schnittstellen an; den Zugriff über die Windows-Firewall auf die benötigte Umgebung begrenzen. Netzwerkgrenzen, Automatik und Fehlersuche erklärt die [Laufzeitsicht](docs/6-laufzeitsicht.md).

### Images bauen

```powershell
podman machine start
podman build -t vectordb:local -f Vector/Dockerfile Vector
podman build -t vectorapi:local -f Vector/Dockerfile.api Vector
podman build -t rag-api:local -f rag/Dockerfile rag
# Optional:
podman build -t reranker:local -f reranker/Dockerfile reranker
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

### RAG-API starten

Warum Windows-`localhost` im Container nicht genügt, wozu der WSL-Gateway dient und wie die automatische Ermittlung funktioniert, erklärt die [Laufzeitsicht](docs/6-laufzeitsicht.md). Dort stehen auch die Bedeutung der Umgebungsvariablen und Schritte zur Fehlersuche.

Das aktuelle RAG-Image ermittelt Ollama beim ersten Modellaufruf automatisch. Im vorhandenen Vector-Pod nutzt es die lokale Vector-API:

```powershell
podman build -t rag-api:local -f rag/Dockerfile rag
podman run -d --name rag-api --pod vectorpod -e VECTOR_API_URL=http://127.0.0.1:5500/search localhost/rag-api:local
```

Der Pod muss wie oben Port 5600 veröffentlichen. Bei einem älteren Pod ohne dieses Mapping kann die RAG-API stattdessen separat gestartet werden; den vorhandenen Datenbank-Pod dabei erhalten. Nur eine der beiden RAG-Startvarianten ausführen:

```powershell
podman run -d --name rag-api -p 5600:5600 localhost/rag-api:local
```

Diese Variante nutzt `http://host.containers.internal:5500/search` für die bereits veröffentlichte Vector-API. Falls diese Adresse in der eigenen Netzwerkkonfiguration nicht erreichbar ist, `VECTOR_API_URL` beim Containerstart explizit setzen. Die automatische Gateway-Ermittlung gilt nur für Ollama.

Für Daten aus `import3.py` muss der Request `"filter": "snowflake-arctic-embed2-v2"` enthalten. Der RAG-Standardfilter lautet `snowflake-arctic-embed2` und findet diese Importvariante nicht.

Die Ollama-Ermittlung prüft zuerst `host.containers.internal:11434`. Unter WSL werden anschließend die IPv4-Default-Gateways aus `/proc/net/route` geprüft. Nur ein erreichbarer Endpunkt mit einer Ollama-Modellliste wird übernommen und für die Prozesslaufzeit gespeichert. Bei Nichterreichbarkeit versucht der nächste Request die Ermittlung erneut. Nach einem WSL-Neustart startet der Containerprozess mit einer neuen Ermittlung. Bei einer eigenen Bridge kann deren Gateway statt des Windows-Gateways sichtbar sein; dafür oder für entfernte Modellserver lässt sich `OLLAMA_BASE_URL` beim Containerstart ausdrücklich setzen. Diese Einstellung hat Vorrang vor der Automatik. Ollama muss weiterhin aus der WSL-Umgebung erreichbar sein.

### Optionalen Reranker starten

```powershell
podman run -d --name reranker -p 5000:5000 localhost/reranker:local
Invoke-RestMethod http://localhost:5000/health
```

Der erste Health-Aufruf lädt das Modell in den Prozess und kann dauern. Das Image lädt `cross-encoder/ms-marco-MiniLM-L6-v2` bereits beim Build herunter. Der Standardstart reicht keine GPU durch; Hinweise für einen optionalen GPU-Start stehen unten.

### Einzelne Dienste und Details

Die Vector-spezifischen Hinweise stehen in [Vector/README.txt](Vector/README.txt). Für den aktuellen Gesamtaufbau gelten die Befehle oben. Verzeichnisse namens `k8s` sind historische Referenzen. Die [Bausteinsicht](docs/5-bausteinsicht.md), [Laufzeitsicht](docs/6-laufzeitsicht.md), [Verteilungssicht](docs/7-verteilungssicht.md) und das [Testkonzept](docs/8-1-testkonzept.md) beschreiben den Podman-Betrieb. Die Verteilungssicht zeigt Windows-/WSL-Grenzen, Pods, Container, Ports und persistente Speicher sowie die Unterschiede zwischen Neuaufbau, bestehendem Betrieb und Teststack.

### Automatisierte Tests: Unit und Podman-Integration

Die Testarten sind getrennt: containerfreie Unit-Tests liegen in `tests/unit`; Podman- und externe Dienst-Integrationstests liegen in `tests/podman`. `tests/conftest.py` stellt gemeinsame pytest-Optionen bereit. `tests/podman/conftest.py` baut den isolierten Containerstack auf und räumt ihn anschließend ab.
Die pytest-Konfiguration deaktiviert den Cache-Provider (`-p no:cacheprovider`), damit kein Zugriff auf `.pytest_cache` erforderlich ist. Die Chunking-Tests legen eindeutige UTF-8-Testdateien direkt in `tests/unit` an und löschen sie selbst; pytest `tmp_path` und das Benutzer-Temp-Verzeichnis werden nicht verwendet.

Voraussetzungen für Unit-Tests sind Python und die Testabhängigkeiten. Podman-Integration benötigt zusätzlich eine gestartete Podman-Machine. Ollama-Tests setzen eine Host-Instanz auf `localhost:11434` und das Modell `snowflake-arctic-embed2` voraus.

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
Der Ende-zu-Ende-Test benötigt zusätzlich das Ollama-Antwortmodell `phi3:mini`. Beide Modelle müssen auf dem Host unter `localhost:11434` und aus dem RAG-Container über den automatisch ermittelten oder explizit konfigurierten Endpunkt erreichbar sein. Modelle vorab mit `ollama pull snowflake-arctic-embed2` und `ollama pull phi3:mini` bereitstellen. Podman weist dem Teststack dynamische Hostports zu; ein regulärer Stack kann parallel weiterlaufen. PostgreSQL wird nur innerhalb des Test-Pods angesprochen. Die RAG-API verwendet dort `VECTOR_API_URL=http://127.0.0.1:5500/search` für die eigene Vector-API. Außerhalb der Tests bleibt der Standard `http://host.containers.internal:5500/search` erhalten; `VECTOR_API_URL` kann ihn beim Containerstart überschreiben.

Bei Verbindungsfehlern Windows-Aufruf und Container-Aufruf getrennt prüfen; ein erfolgreicher Host-Test beweist keinen Zugriff aus dem Container. Die [Laufzeitsicht](docs/6-laufzeitsicht.md) enthält konkrete Diagnosebefehle und die dauerhafte Einrichtung der Hintergrund-App. `OLLAMA_HOST_URL` setzt die Adresse für den E2E-Import (Standard `http://localhost:11434`); `OLLAMA_CONTAINER_URL` setzt optional die Adresse aus dem Testcontainer (ohne Vorgabe: automatische Ermittlung). Beide müssen denselben Modellserver erreichen. Die Testfixture reicht die Containeradresse als `OLLAMA_BASE_URL` weiter.

Tests nutzen dieselbe automatische Ermittlung wie die reguläre RAG-API. Eine zuvor manuell gesetzte Testadresse bei Bedarf entfernen:

```powershell
Remove-Item Env:OLLAMA_CONTAINER_URL -ErrorAction SilentlyContinue
python -m pytest -c tests/pytest.ini tests/podman/test_rag_e2e.py --include-rag --include-ollama
```

`OLLAMA_CONTAINER_URL` bleibt als ausdrückliche Testkonfiguration verfügbar und wird als `OLLAMA_BASE_URL` an den Testcontainer weitergereicht. Ohne diese Variable prüft die Vorabprüfung denselben Resolver wie die RAG-API. Ein erfolgreicher Host-Test gegen `localhost` prüft den Netzwerkweg aus dem Container nicht.

Der Test prüft vor dem Import die Modellverfügbarkeit über `/api/tags` vom Host und aus dem RAG-Container. Danach zerlegt er `tests/podman/fixtures/early_rome.txt`, normalisiert echte Embeddings und speichert die Chunks über die Vector-API. Anschließend fragt er „Wer beherrschte in der Frühzeit Roms das westliche Mittelmeer“ über die RAG-API ab und prüft den Karthago-Quellabschnitt, den Antwortinhalt und Generierungsmetriken. Er verwendet eine eigene Importkennung und das Testvolume; eine Keyword-Anreicherung über `import3.py` ist nicht Teil dieses Tests.

### NVIDIA-GPU unter Windows mit WSL2 und Podman

Der Standardstart benötigt keine GPU. Für einen optionalen NVIDIA-GPU-Start unter WSL2 werden ein passender Windows-NVIDIA-Treiber, `/dev/dxg` und die WSL-Treiberbibliotheken benötigt. Bei einem Neuaufbau kann der Reranker statt des CPU-Starts so gestartet werden:

```powershell
podman run -d --name reranker -p 5000:5000 --device /dev/dxg -v /usr/lib/wsl/lib:/usr/lib/wsl/lib:ro -v /usr/lib/wsl/drivers:/usr/lib/wsl/drivers:ro -e LD_LIBRARY_PATH=/usr/lib/wsl/lib localhost/reranker:local
```

Die Geräteweitergabe allein garantiert keine CUDA-Inferenz; auch die installierte torch-Variante muss CUDA unterstützen. Diese optionale Konfiguration ist kein Bestandteil der Standard-Testfixture. Die zusätzliche Einbindung von `/usr/lib/wsl/drivers` ist erforderlich: Fehlen diese Treiberdateien, kann CUDA trotz sichtbarem `/dev/dxg` mit `cuInit: 100` scheitern. Die Konfiguration wurde auf einer NVIDIA GeForce RTX 4060 mit CUDA-Berechnung geprüft.

Voraussetzungen und Prüfung:

1. Aktuellen NVIDIA-Windows-Treiber mit WSL-CUDA-Unterstützung installieren.
2. WSL2 verwenden und die Podman-Machine starten (`podman machine start`).
3. In der Podman-Machine prüfen, dass `/dev/dxg` und `/usr/lib/wsl/lib/libcuda.so.1` vorhanden sind.
4. Nach dem Start des Rerankers GPU-Erkennung prüfen:

```powershell
podman exec reranker python -c "import torch; print('CUDA verfügbar:', torch.cuda.is_available()); print('Geräte:', torch.cuda.device_count()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'keine')"
```

Bei erfolgreicher GPU-Einrichtung liefert die Prüfung `CUDA verfügbar: True` und den Namen der NVIDIA-Grafikkarte. Andernfalls Treiberbereitstellung und CUDA-Unterstützung der installierten torch-Variante prüfen; die Inferenz kann weiterhin auf CPU laufen.
