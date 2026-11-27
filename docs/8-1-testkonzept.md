<!--

purpose: "Systemübergreifende Teststrategie mit Teststufen, Isolation und Abdeckung wichtiger Verträge."
agent_instructions:
  - "Je Teststufe erläutern, was sie prüft, welche Abhängigkeiten sie braucht und wie Testdaten und Betriebsdaten getrennt werden. Stabile Aufrufoptionen und relevante Abdeckung dürfen hier als Referenz stehen."
  - "Qualitätsanforderungen und ihre Erfolgskriterien in Kapitel 10 pflegen. Testtopologie steht in Kapitel 7, konkrete Prüfergebnisse im Changelog."
  - "In diesem Kapitel nur den aktuellen Stand und ausdrücklich als offen gekennzeichnete Ziele beschreiben."
  - "Weiterhin gültige Änderungen direkt in den fachlich passenden Abschnitt einarbeiten und überholte Aussagen ersetzen."
  - "Keine datierten Nachträge, Änderungshistorie, Prüfergebnisse oder Ausrollstände in dieses Kapitel aufnehmen. Diese ausschließlich in ../changelog.md dokumentieren."

-->

# Testkonzept für den Podman-Betrieb

Automatisierte Tests sichern Import, Datenhaltung, Schnittstellen und Zusammenarbeit der Dienste ab. Die [Bausteinsicht](5-bausteinsicht.md) beschreibt die Komponenten, die [Laufzeitsicht](6-laufzeitsicht.md) ihre Aufrufe und Ollama-Netzwerkgrenzen.

## Teststufen und Ausführung

| Stufe | Prüfumfang | Voraussetzungen |
|---|---|---|
| Unit- und Vertragstests | Chunking, Adapterverträge, Fehlerpfade und Ablauf mit Testdoubles | Python |
| Podman-Standardintegration | Image-Build, PostgreSQL/pgvector, Vector-API, Importfehler und Schemamigrationen | Gestartete Podman-Machine |
| Optionale Integration | RAG-HTTP, Reranker-Modellwahl und echte Ollama-Embeddings beziehungsweise Keyword-Anreicherung | Dienste und Modelle gemäß gewählter Testgruppe |
| Ende zu Ende | Kleinkorpus, Retrieval, Generierung und Evaluation mit echten Modellen | RAG-Testcontainer und Host-Ollama, für Reranking zusätzlich der Reranker |

Ausführung aus dem Projektstamm:

```powershell
python -m pip install -r tests/podman/requirements.txt
# Nur Unit-Tests
python -m pytest -c tests/pytest.ini tests/unit
# Standard-Integration
python -m pytest -c tests/pytest.ini tests/podman
# Optionale Dienste
python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker
python -m pytest -c tests/pytest.ini tests/podman --include-ollama
# Unit- und alle Integrationstests
python -m pytest -c tests/pytest.ini tests --all
# Nur containerfreie Tests
python -m pytest -c tests/pytest.ini tests --no-podman
# Ressourcen zur Fehlersuche behalten
python -m pytest -c tests/pytest.ini tests --all --keep-podman
```

`--include-rag --include-ollama` aktiviert den RAG-Ende-zu-Ende-Test ohne Reranking. Für die E2E-Pfade mit Reranking ist zusätzlich `--include-reranker` erforderlich. E2E verwendet `snowflake-arctic-embed2` und `phi3:mini`. Für die Keyword-Anreicherung im Grundfall und in den Keyword-Importtests benötigt Host-Ollama zusätzlich `gemma3:4b`. `--all` aktiviert alle optionalen Gruppen. `--no-podman` überspringt Container-Tests. Ein gleichzeitig ausdrücklich aktivierter Host-Ollama-Test kann weiterhin laufen. Setup und Modellbereitstellung beschreibt das [README](../README.md).

## Isolierter Testbetrieb

Containerbasierte Tests verwenden pro Sitzung einen isolierten Pod mit eigener Datenbank und eigenem Volume. Container-, Image- und Datenkennungen enthalten eine eindeutige Test-ID. Die Fixture entfernt ihre Ressourcen am Ende, außer bei `--keep-podman`. Manuell genutzte Volumes und Bestandsdaten bleiben dem Testlauf entzogen. Die [Verteilungssicht](7-verteilungssicht.md) beschreibt die Testtopologie.

Podman vergibt dynamische Hostports für die APIs. Die Fixture liest sie am Infrastrukturcontainer aus. PostgreSQL benötigt keinen Hostport. Die RAG-API verwendet innerhalb des Test-Pods `VECTOR_API_URL=http://127.0.0.1:5500/search`. `tests/unit/test_podman_stack_config.py` prüft diese Konfiguration containerfrei. Die Fixture gibt bei Startproblemen Containerstatus und Logs aus.

Ollama ist ein externer, mit dem regulären Betrieb geteilter Host-Dienst. Der eigenständige Embedding-Test benötigt weder Pod noch Testvolume. Für RAG-E2E muss der Modellserver vom Host und aus dem Container erreichbar sein. Die Fixture prüft die benötigten Modelle und berücksichtigt `OLLAMA_HOST_URL` und `OLLAMA_CONTAINER_URL`. Die automatische Ermittlung und ihre WSL-Gateway-, Cache- und Fehlerpfade prüft `tests/unit/test_ollama_endpoint.py`.

## Automatisierte Prüffälle

### PostgreSQL und Vector-API

`tests/unit/test_vector_api_unit.py` verwendet Testdoubles für PostgreSQL-Pool und Cursor und prüft SQL-Parameter, Commit, Rollback und Poolfehler. `tests/podman/test_vector_api.py` prüft HTTP-Schreiben und -Lesen, stabile IDs bei parallelen Upserts, Variantenisolation, setgebundene Suche mit L2 und Cosinus sowie `ILIKE` auf `chunktext`. Dieselbe Chunk-ID in zwei Sets sichert die Trennung bei Einzelabruf und Suche ab. Unit-Tests sichern HTTP 400 bei Listenstrings im Feld `vector` sowie bei fehlender verpflichtender Set-ID oder bei Verwendung von `embedding` als Set-Parameter vor dem Datenbankzugriff ab. Die Tests verwenden Vektoren mit 1024 Komponenten und prüfen beim Einzelabruf und bei der Suche, dass `include_vector` den Vektor als JSON-Zahlenliste liefert. `DELETE /chunks` wird mit gleichen Grenzen und einem inklusiven Bereich geprüft, der die Dezimalgrenze zwischen 9 und 10 überschreitet.

Der Wiederanlauftest startet die API in einem zusätzlichen isolierten Pod vor PostgreSQL. Er prüft Liveness ohne Datenbank und Readiness mit HTTP 503. Nach dem Datenbankstart speichert er einen Chunk, erstellt den PostgreSQL-Container mit demselben eigenen Testvolume neu und prüft, dass der Chunk ohne Neustart der API abrufbar und per Vektorsuche auffindbar bleibt. Der Test räumt Pod und Volume auch bei Fehlern auf.

`tests/podman/test_embedding_migration.py` prüft `001_embedding_set_id.sql` und `002_chunktext.sql` in eigenen Testdatenbanken. Es kontrolliert erhaltene Zeilen, Vektoren und Unique Constraints, wiederholbare Migrationen und die Wiederherstellung der gesicherten Struktur. Die API-Vertragstests prüfen die Set-Kennung `embedding_set_id` und das Antwortfeld `chunktext`.

### Dokumentimport

`tests/unit/test_chunking.py` prüft UTF-8, Reihenfolge, Splitter-Konfiguration, Chunkgrenzen und Overlap. `tests/unit/test_import_pipeline.py` prüft den CLI-Einstieg, lange ungetrennte Passagen, Wiederverwendung von Artefakten, Modell- und Promptvarianten und denselben angereicherten Text beim Embedding und Speichern. Bei Fehlern im Embedding, Einzelwrite oder Bereinigung prüft der Test die ausgegebene Chunknummer und den erneuten Aufruf mit `--start`. Ungültige Providervektoren werden vor Speicherung abgefangen.

Die Standardintegration in `tests/podman/test_import_pipeline_integration.py` prüft den sichtbaren Teilstand nach Abbruch, die Fortsetzung mit `--start` und die nachfolgende Löschung oberhalb der letzten Chunknummer. Andere Sets und Dokumente dienen als Kontrollfälle. Mit `--include-ollama` prüft dieselbe Datei Keyword-Anreicherung aus einem Chunk-Artefakt, Provider-Metriken, Import aus dem Anreicherungsartefakt, Speicherung und Rücksuche in den konfigurierten Sets. 

### RAG-API, CLI und Evaluation

`tests/unit/test_rag_components.py` prüft Embedding, Retrieval, Kontextbildung und Generierung mit gemockten Diensten. Die Fälle umfassen die Set-Auswahl, ungültige Providerantworten, Fehler beim Retrieval, leeren Kontext, Metrikgrenzen, Reranking-Zuordnung und Grenzen für Wiederholungen. Tests mit kontrollierter monotoner Uhr prüfen Teil- und Gesamtzeiten einschließlich `no_context` und den Alias `generation_duration`/`total_duration`.

`tests/unit/test_interact.py` prüft die Delegation in einem API-Aufruf, Modell- und Reranking-Parameter, getrennte ursprüngliche und ausgewählte Treffer, Export und Anzeige, CLI-Fehler und Zeitlimits. `tests/podman/test_rag_api.py` prüft die Eingabevalidierung am HTTP-Endpunkt.

`tests/podman/test_rag_e2e.py` importiert im Grundfall `tests/podman/fixtures/early_rome.txt` über `Ingest.pipeline` mit Keyword-Anreicherung und echten Ollama-Embeddings. Der Test prüft den gespeicherten angereicherten Chunktext, den erwarteten Quellabschnitt, Karthago als Antwortinhalt und die Laufzeit- und Generierungsmetriken. Der Import schreibt über die Vector-API des Test-Pods in ein eigenes Embedding-Set. Ausgewählte E2E-Pfade nutzen den Reranker, während der Grundfall ohne ihn läuft.

Evaluations-Vertragstests prüfen direkt verkettbare `next_request`-Antworten, erhaltene Trefferidentität, Distanzen und Scores, unabhängige Dienstaufrufe, übergebene Vektoren, getrennte Opt-ins für Diagnostik und Fragevektor sowie frühe Eingabe- und Promptvalidierung. Tests sichern HTTP 502 bei falscher Providerdimension vor Retrieval und bei ungültigen gespeicherten Diagnosevektoren ab. Tests für `analyze.py` prüfen seine beiden HTTP-Aufrufe, die Ausgabe, Fehler und die Übergabe des vollständigen Gold-Chunks. Ein Integrationstest vergleicht Distanzwerte für bekannte, in pgvector gespeicherte Vektoren. Der E2E-Test verkettet Retrieve, Rerank und Generate mit echten Modellen und prüft den optionalen Referenzvergleich.

### Reranker

`tests/unit/test_reranker_unit.py` prüft mit einem Fake-Modell Eingabevalidierung, leere Dokumentlisten, Rangfolge, Modellwahl und Default, Wiederverwendung, Wechsel, parallele Anfragen sowie Lade- und Inferenzfehler. `tests/podman/test_reranker.py` prüft Health und HTTP-Modellwechsel mit MiniLM-L6 und TinyBERT-L2 im selben Container. Das Standardmodell wird beim Image-Build geladen und beim ersten entsprechenden Zugriff in den Prozess geladen. Der Download des Zusatzmodells benötigt Netzwerkzugriff.

### Fehlervertrag und Image-Build

`tests/unit/test_http_errors.py` prüft unter anderem HTTP 400 für den entfernten RAG-Parameter `filter` vor Providerzugriff. Weitere Fälle betreffen frühe Validierung vor Modell- und Poolzugriff, RFC-9457-Medientyp und -Felder, Request-Korrelation, sichere interne Fehler, HTTP-Status und den `Allow`-Header. `tests/podman/test_http_errors.py` prüft den HTTP-Vertrag der drei APIs im isolierten Stack. `tests/unit/test_build_image.py` prüft die explizite Dateiauswahl des Build-Skripts und die Bereinigung temporärer Build-Kontexte bei Erfolg und Fehler.

## Pytest-Konfiguration und temporäre Dateien

`tests/pytest.ini` verwendet `--import-mode=importlib`, damit gleichnamige Unit- und Integrationstestmodule getrennt geladen werden. Die Testverzeichnisse stehen für Helper-Imports im Suchpfad. Der Cache-Provider ist standardmäßig deaktiviert. Bei expliziter Aktivierung leitet die Konfiguration seinen Cache nach `<System-/Benutzer-Temp>/rag-pytest-cache` um.

Fixture-Tempbasispfade sind pro Lauf eindeutig und liegen außerhalb des Projekts. Die gemeinsame Konfiguration weist projektinterne `--basetemp`-Pfade und projektinterne System- oder Benutzer-Tempbereiche ab. `PYTEST_DEBUG_TEMPROOT` kann Fixtures nicht ins Projekt umleiten. `test_temporary_paths.py` prüft die Regeln auch mit Subprozessaufrufen aus Testunterverzeichnissen. Der Schutz setzt voraus, dass die Projekt-Konfiguration geladen wird. Chunking-Tests verwalten ihre eigenen temporären UTF-8-Dateien und räumen sie nach dem Test auf.

### Testimporte und Patchziele

Tests verwenden statische Paketimporte fuer normale Projektmodule. Reexportierte Funktionen und Providerzugriffe koennen mit vollqualifizierten pytest-Patchzielen ersetzt werden, etwa `monkeypatch.setattr("requests.post", fake_post)` oder `monkeypatch.setattr("rag.app.resolve_ollama_base_url", resolver)`. Dynamisches Laden bleibt fuer bewusst isolierte Module/Fixtures mit Stubs erhalten; deren Modulnamensraum wird gezielt mit `monkeypatch.setitem(vars(module), "db_pool", pool)` ersetzt. Dabei nur bekannte, vom Test benoetigte Schluessel setzen; anders als setattr prueft setitem nicht auf ein bereits vorhandenes Attribut. Alle Aenderungen werden durch monkeypatch zurueckgesetzt. Referenzinspektionen bleiben aktiv; keine pauschalen Suppressionen fuer Testdateien.

## Offene Testziele

Das [Schuldenregister](11-2-technische-schulden.md#1122-schuldenregister) führt offene Vertrags- und Testlücken. Dazu gehören eine nicht beantwortbare Frage bei vorhandenem Kontext, Goldantworten und referenzierte Retrievaltreffer, Prüfungen von Reranker-Health während Laden und Inferenz, die Prüfung des Schemas samt Index beim Neuaufbau sowie repräsentative Suchpläne und Lastprofile. GPU-Prüfungen benötigen passende Hardware und bilden eine eigene Testgruppe. Echte Modelle werden anhand fachlicher Kriterien geprüft, da Modellversion, Hardware und Sampling Antworten beeinflussen.
