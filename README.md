# knowledge-experimental-ki

Experimentelle KI-Komponenten lokal mit Podman ausführen.

## Voraussetzungen

- Podman mit laufender Podman-Machine (unter Windows)
- Python für Import- und Analysewerkzeuge
- Ollama, falls lokale Sprach- oder Embedding-Modelle verwendet werden

## Gesamten Podman-Stack starten

Die Befehle sind f?r PowerShell im Projektstamm gedacht. Voraussetzung f?r den Reranker ist ein Windows-NVIDIA-Treiber mit WSL2-CUDA-Unterst?tzung und eine laufende Podman-Machine. Der Stack besteht aus PostgreSQL/pgvector, Vector-API, Ollama, RAG-API und Reranker. Die Datenbank und die Modelle bleiben in Named Volumes erhalten.

### Images bauen

```powershell
podman machine start
podman build -t vectordb:local -f Vector/Dockerfile Vector
podman build -t vectorapi:local -f Vector/Dockerfile.api Vector
podman build -t rag-api:local -f rag/Dockerfile rag
podman build -t reranker:local -f reranker/Dockerfile reranker
```

### Vector-Datenbank und API starten

```powershell
podman pod create --name vectorpod -p 5432:5432 -p 5500:5500
podman volume create pgvector-data
podman run -d --name vectordb --pod vectorpod -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vector_db -e PGDATA=/var/lib/postgresql/data/pgdata -v pgvector-data:/var/lib/postgresql/data localhost/vectordb:local
podman run -d --name vector-api --pod vectorpod -e DB_HOST=127.0.0.1 -e DB_PORT=5432 -e DB_USER=admin -e DB_PASSWORD=admin -e POSTGRES_DB=vector_db localhost/vectorapi:local
```

### Einzelne Dienste und Details

Der vollst?ndige Build- und Startablauf steht oben. Die Vector-spezifischen Hinweise und alternative Einzelstarts sind in [Vector/README.txt](Vector/README.txt) beschrieben. Die lokalen RAG- und Reranker-Dateien liegen in [rag](rag) und [reranker](reranker); Kubernetes-Manifeste sind in deren `k8s`-Unterverzeichnissen.

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
# Unit-Tests plus alle Integrationstests
python -m pytest -c tests/pytest.ini tests --all
# Containerfreie Tests aus beiden Verzeichnissen; Integrationstests werden übersprungen
python -m pytest -c tests/pytest.ini tests --no-podman
# Test-Pod und Volume zur Fehlersuche behalten
python -m pytest -c tests/pytest.ini tests --all --keep-podman
```

`--all` aktiviert die optionalen RAG-, Reranker- und Ollama-Gruppen. Der Reranker lädt sein Modell beim Image-Build. Alle Podman-Ressourcen und Testdaten sind von regulären Stack-Ressourcen getrennt.
### NVIDIA-GPU unter Windows mit WSL2 und Podman

Der Windows-NVIDIA-Treiber stellt CUDA f?r WSL2 bereit. In dieser Umgebung ist die RTX 4060 in der Podman-Machine ?ber `/dev/dxg` sichtbar; der Treiberpfad `/usr/lib/wsl/lib` muss in den Container eingebunden werden. Der Reranker-Startbefehl oben reicht das Ger?t durch und bindet die Treiberbibliotheken read-only ein. Eine zus?tzliche Installation des Linux-NVIDIA-Treibers in WSL oder im Container ist nicht erforderlich.

Voraussetzungen und Pr?fung:

1. Aktuellen NVIDIA-Windows-Treiber mit WSL-CUDA-Unterst?tzung installieren.
2. WSL2 verwenden und die Podman-Machine starten (`podman machine start`).
3. In der Podman-Machine pr?fen, dass `/dev/dxg` und `/usr/lib/wsl/lib/libcuda.so.1` vorhanden sind.
4. Nach dem Start des Rerankers GPU-Erkennung pr?fen:

```powershell
podman exec reranker python -c "import torch; print('CUDA verf?gbar:', torch.cuda.is_available()); print('Ger?te:', torch.cuda.device_count()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'keine')"
```

Erwartet werden `CUDA verf?gbar: True` und als Ger?t die NVIDIA-Grafikkarte. Falls `/dev/dxg` in der Podman-Machine fehlt, WSL aktualisieren (`wsl --update`) und Windows neu starten. Die Host-Treiber m?ssen mit der CUDA-Version des installierten PyTorch kompatibel sein.
