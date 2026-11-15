# Projektbeschreibung

- Das Projekt ist ein RAG-System zur Evaluierung verschiedenster Parameter und Strategien. Als Beispieldaten werden Texte zu römischer Geschichte verwendet
- Eine Architekturbeschreibung liegt in docs/5-bausteinsicht.md

# Out-of-Scope
- Alle Verzeichnisse namens `k8s` sind historische Referenzen.
  Bei Suche, Analyse und Änderungen ausschließen.
- Kubernetes-spezifische Aussagen in der Dokumentation sind für
  den aktuellen Podman-Betrieb nicht maßgeblich.

# Entwicklung
- Umgebung: Windows, PowerShell, Podman, Ollama
- Programmiersprache: Python
- Befehle aus dem Projektstamm ausführen.
- Setup und Startbefehle stehen in README.md.

# Tests
- Testkonzept: docs/8-1-testkonzept.md.
- Containerfreie Unit-Tests: tests/unit.
- Integrationstests mit Podman und externen Diensten: tests/podman.
- Nur containerfreie Unit-Tests:
  `python -m pytest -c tests/pytest.ini tests/unit`
- Standardintegration mit PostgreSQL/pgvector und Vector-API:
  `python -m pytest -c tests/pytest.ini tests/podman`
- RAG- und Reranker-Integration zusätzlich aktivieren:
  `python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker`
- Ollama-Embedding-Integration aktivieren (Ollama auf `localhost:11434`):
  `python -m pytest -c tests/pytest.ini tests/podman --include-ollama`
- Unit- und alle optionalen Integrationstests:
  `python -m pytest -c tests/pytest.ini tests --all`
- Containerfreie Tests aus der gesamten Testsuite:
  `python -m pytest -c tests/pytest.ini tests --no-podman`
- Podman-Testressourcen zur Fehlersuche behalten:
  `python -m pytest -c tests/pytest.ini tests --all --keep-podman`
- `--all` aktiviert alle optionalen Testgruppen und benötigt deren
  Voraussetzungen gemäß README.md.
- Voraussetzungen und Optionen für RAG, Reranker und Ollama:
  siehe README.md.
- Je nach Änderung die betroffenen Teststufen ausführen.
  Nicht ausgeführte Prüfungen und deren Gründe im Abschluss nennen.
- Integrationstests dürfen nur eigene Testressourcen verwenden;
  bestehende Datenbestände und manuell genutzte Volumes erhalten.

# Dokumentation
- Architektur-relevante Dokumentation nach arc42 in docs
- Entwickler-Dokumentation in README.md
- Ändert sich beschriebenes Verhalten, Setup, eine Schnittstelle oder die Architektur, die jeweils betroffene Dokumentation aktualisieren.



