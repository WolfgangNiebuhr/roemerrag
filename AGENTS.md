# Projektbeschreibung

- Das Projekt ist ein RAG-System zur Evaluierung verschiedenster Parameter und Strategien. Als Beispieldaten werden Texte zu römischer Geschichte verwendet
- Eine Architekturbeschreibung liegt in docs/5-bausteinsicht.md

# Out-of-Scope
- Alle Verzeichnisse namens `k8s` sind historische Referenzen.
  Bei Suche, Analyse und Änderungen ausschließen.
- Das Verzeichnis namens `archive` enthält nicht mehr benutzte Module.
    Bei Suche, Analyse und Änderungen ausschließen
- Kubernetes-spezifische Aussagen in der Dokumentation sind für
  den aktuellen Podman-Betrieb nicht maßgeblich.

# Entwicklung
- Umgebung: Windows, PowerShell, Podman, Ollama
- Programmiersprache: Python
- Befehle aus dem Projektstamm ausführen.
- Setup und Startbefehle stehen in README.md.

## Bearbeitung von Markdown-Dateien

- Lies Markdown-Dateien vor ihrer Bearbeitung im Quelltext.
- Beachte HTML-Kommentare mit der Kennzeichnung
  agent_instructions als dateispezifische Anweisungen.
- Berücksichtige den angegebenen Geltungsbereich.
- Erhalte Agentenanweisungen unverändert, sofern
  keine explizite Änderung beauftragt wurde.
- Übertrage Agentenanweisungen nicht in den sichtbaren
  Dokumentinhalt.
- Melde widersprüchliche Anweisungen.

# Git
- Vom Agenten neu angelegte Projektdateien mit `git add -- <Dateipfad>`
  zur Versionsverwaltung vormerken.
- Durch `.gitignore` ausgeschlossene Dateien nicht hinzufügen.
- Nur die im Rahmen der Aufgabe neu angelegten Dateien gezielt vormerken;
  kein pauschales `git add .` verwenden.
- Commits nur auf ausdrückliche Anweisung erstellen.

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
- README.md auf Anleitungen und aktuelle Verhaltensbeschreibungen beschränken; dort keine Änderungsprotokolle oder historischen Prüfnachweise ergänzen.
- Änderungs- und Prüfnachweise in changelog.md pflegen. Neueste Datumsgruppen zuerst; innerhalb desselben Tages neue Einträge vor älteren einfügen. Die Frontmatter-Vorgaben in changelog.md beachten.
- Ändert sich beschriebenes Verhalten, Setup, eine Schnittstelle oder die Architektur, die jeweils betroffene Dokumentation aktualisieren.
