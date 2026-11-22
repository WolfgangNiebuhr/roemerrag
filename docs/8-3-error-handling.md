# 8.3 Übergreifendes Error-Handling

Stand: 21.11.2026. Dieses Querschnittskonzept beschreibt den **Zielzustand**, keine bereits implementierte Schnittstelle. Es gilt für RAG-API, Vector-API, Reranker sowie unterstützte Import- und Analysewerkzeuge. Die Umsetzung betrifft insbesondere TS-03, TS-05 bis TS-09, TS-13 und TS-17 aus [Kapitel 11.2](11-2-technische-schulden.md). Bausteine und Teststufen beschreiben die [Bausteinsicht](5-bausteinsicht.md) und das [Testkonzept](8-1-testkonzept.md).

## 8.3.1 Ziele und Verantwortlichkeiten

Fehler werden an ihrer Ursache eingeordnet, mit ihrem Verarbeitungsschritt versehen und an HTTP- beziehungsweise CLI-Grenzen einheitlich ausgegeben. Technische Ausfälle müssen von fachlichen Ergebnissen unterscheidbar bleiben, damit Evaluationen keine fehlgeschlagenen Verarbeitungsschritte als erfolgreiche Versuche werten.

- Eingangsvalidierung prüft JSON-Struktur, Pflichtfelder, Typen, Wertebereiche, widersprüchliche Aliasangaben und Vektoren vor Modell- oder Datenbankzugriffen. Vektoren müssen die erwartete Dimension, endliche Zahlen und bei Normalisierung eine positive Norm haben.
- Dienstadapter übersetzen gezielt HTTP-, Netzwerk-, Modell- und Datenbankfehler in gemeinsame Anwendungsfehler. Die ursprüngliche Exception bleibt durch Exception-Chaining erhalten.
- Die Orchestrierung ergänzt den Schritt, etwa `embedding`, `retrieval`, `generation`, `reranking` oder `storage`, ohne Fehler zu verschlucken.
- Zentrale Flask-Handler erzeugen den HTTP-Fehlervertrag. Ein letzter Auffanghandler protokolliert unerwartete Exceptions und liefert einen neutralen internen Fehler. Bestehende HTTP-Statuscodes und erforderliche Header, etwa `Allow` bei 405, bleiben erhalten.
- Ein kleines gemeinsames Python-Paket enthält Fehlerklassen, Problemtypregister, Serialisierung und Logging-Konventionen. Die Container-Builds müssen dieses Paket explizit bereitstellen.

## 8.3.2 HTTP-Fehlervertrag nach RFC 9457

HTTP-Fehlerantworten verwenden [RFC 9457 – Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc9457.html), insbesondere Abschnitte 3 bis 5. Das Problemobjekt steht direkt im Body, ohne umschließendes `error`-Objekt. Der Medientyp ist `application/problem+json`.

Das Projektprofil verlangt bei anwendungsspezifischen Fehlern folgende Felder; diese Vollständigkeit ist eine Projektentscheidung, keine generelle Pflicht des RFC:

| Feld | Bedeutung und Projektregel |
|---|---|
| `type` | Absolute, stabile URI als primäre maschinenlesbare Identität des Problemtyps. |
| `title` | Kurze Bezeichnung des Typs; außer bei Übersetzung für denselben Typ konstant. |
| `status` | Numerischer HTTP-Status; muss dem tatsächlich gesendeten Status entsprechen. |
| `detail` | Sichere, verständliche Beschreibung dieses konkreten Fehlers. Keine maschinelle Auswertung des Textes. |
| `instance` | URI des konkreten Fehlerereignisses, beispielsweise eine eindeutige `urn:uuid:`-URI. Sie setzt keinen abrufbaren Diagnoseendpunkt voraus. |
| `request_id` | Projekterweiterung: Korrelationskennung für den gesamten eingehenden Aufruf und seine Dienstaufrufe. |
| `stage` | Projekterweiterung: betroffener Verarbeitungsschritt. |
| `retryable` | Projekterweiterung: boolescher Hinweis, ob eine spätere Wiederholung sinnvoll sein kann; keine Zusage und keine automatische Retryanweisung. |

Die hier festgelegten Typ-URIs verwenden den absoluten Präfix `urn:rag:problem:`. Sie sind Identifikatoren und nicht abrufbar. Das Register in Abschnitt 8.3.3 dokumentiert ihre Bedeutung. Ein späterer Wechsel zu HTTPS-URIs verändert die Typidentität und ist als Vertragsänderung zu behandeln. RFC 9457 erlaubt nicht auflösbare URIs, bevorzugt aber abrufbare Dokumentation.

Beispiel:

```http
HTTP/1.1 504 Gateway Timeout
Content-Type: application/problem+json
X-Request-ID: a74f92

{
  "type": "urn:rag:problem:dependency-timeout",
  "title": "Zeitlimit einer Abhängigkeit überschritten",
  "status": 504,
  "detail": "Die Antwortgenerierung hat das Zeitlimit überschritten.",
  "instance": "urn:uuid:45f139da-6497-4f86-a116-4f3b32be4952",
  "request_id": "a74f92",
  "stage": "generation",
  "retryable": true
}
```

Clients identifizieren Fehler über `type`, werten den HTTP-Status aus und ignorieren unbekannte Erweiterungen. Ein zusätzlicher Fehlercode wird nicht benötigt. Für allgemeine HTTP-Fehler ohne eigene fachliche Bedeutung darf `type: about:blank` verwendet werden; dabei entspricht `title` der zum HTTP-Status empfohlenen Bezeichnung, gegebenenfalls übersetzt.

Validierungsfehler können die Projekterweiterung `errors` enthalten: eine Liste mit `pointer` als JSON Pointer zum betroffenen Bodyfeld und `detail` als Beschreibung. Für Queryparameter wird stattdessen `parameter` verwendet. Beispiel: `{"pointer":"/num_results","detail":"Muss eine positive ganze Zahl sein."}`. Unterschiedliche unabhängige Fehler werden nicht in einem generischen Sammelproblem versteckt; der maßgebliche Fehler bestimmt Typ und Status.

## 8.3.3 Problemtypregister und Statuszuordnung

Die Spalte Typ nennt den Suffix hinter `urn:rag:problem:`. Alle hier definierten Typen verwenden den angegebenen Status als Projektvertrag.

| Typ | Titel | HTTP | Bedeutung / Wiederholung |
|---|---|---|---|
| `invalid-request` | Ungültige Anfrage | 400 | Fehlende oder ungültige Felder, widersprüchliche Aliase, falsche Dimension oder Metrik. Erst nach Korrektur wiederholen. |
| `not-found` | Ressource nicht gefunden | 404 | Explizit angefragter Chunk fehlt. Kein automatischer Retry. |
| `conflict` | Ressourcenkonflikt | 409 | Anfrage kollidiert mit dem aktuellen Ressourcenzustand. Erst nach Auflösung wiederholen. |
| `dependency-unavailable` | Abhängigkeit nicht verfügbar | 503 | Dienst, Datenbank oder Pool vorübergehend nicht verfügbar. Wiederholung nur bei vorübergehender Ursache. |
| `model-unavailable` | Modell nicht verfügbar | 503 | Laden oder Bereitstellen des benötigten Modells fehlgeschlagen. Fehlende oder inkompatible Konfiguration nicht automatisch wiederholen. |
| `upstream-invalid-response` | Ungültige Antwort einer Abhängigkeit | 502 | Ungültiges JSON, fehlendes Embedding oder verletzter Antwortvertrag. Kein automatischer Retry. |
| `dependency-timeout` | Zeitlimit einer Abhängigkeit überschritten | 504 | Wartezeit auf einen aufgerufenen Dienst überschritten. Wiederholung nur bei sicherer Operation. |
| `internal-error` | Interner Fehler | 500 | Unerwarteter Programm- oder Inferenzfehler. Kein automatischer Retry. |

Ein 404 von Ollama ist beispielsweise kein fehlender Chunk: Der Adapter ordnet ihn nach Ursache ein. Unbekannte, vom Client ausdrücklich wählbare Modellkennungen können als ungültige Anfrage behandelt werden; ein fehlendes serverseitig benötigtes Modell ist `model-unavailable`. Rohantworten anderer Dienste werden nicht ungeprüft weitergereicht. Deren Request-ID und Ursache bleiben intern nachvollziehbar; der aufrufende Dienst erzeugt ein eigenes Fehlerereignis.

## 8.3.4 Timeouts und Wiederholungen

Alle externen Aufrufe erhalten konfigurierbare Verbindungs- und Antwortzeitlimits. Für die RAG-Verarbeitung gilt zusätzlich ein Gesamtbudget über Auflösung, Embedding, Retrieval und Generierung hinweg. Jeder weitere Aufruf und Retry berücksichtigt die verbleibende Zeit; einzelne Bibliotheks-Timeouts allein garantieren kein Gesamtlimit.

Retries sind begrenzt, verwenden wachsende Wartezeiten mit Zufallsanteil und erfolgen nur bei vorübergehenden Ursachen sowie sicher wiederholbaren Operationen. Ungültige Requests, Vertragsverletzungen und Programmfehler werden nicht automatisch wiederholt. Ein begründetes `Retry-After` kann bei 503 mitgegeben und muss innerhalb des verbleibenden Budgets berücksichtigt werden. Retryverantwortung liegt bei einem festgelegten Adapter; verschachtelte Retries über mehrere Schichten sind zu vermeiden.

Generierung wird zunächst nicht automatisch wiederholt, weil Ollama nach einem Timeout weiterrechnen kann. Schreiboperationen dürfen erst nach gesicherter Idempotenz wiederholt werden. Ein Timeout belegt nicht, dass ein Schreibvorgang fehlgeschlagen ist.

## 8.3.5 Datenbank und Ressourcenbereinigung

Jeder Datenbankzugriff hat einen eindeutig begrenzten Transaktions- und Verbindungslebenszyklus: bei Erfolg abschließen, bei Fehler explizit zurückrollen, anschließend die Verbindung freigeben. Defekte oder nicht bereinigbare Verbindungen werden geschlossen statt wiederverwendet. Dies gilt auch für Lesetransaktionen.

Upserts erfolgen atomar über `INSERT ... ON CONFLICT DO UPDATE` auf dem bestehenden Schlüssel `(chunk_id, embedding_set_id)`. Der Pool muss zur Nebenläufigkeit des Servers passen. Poolerschöpfung und Nichterreichbarkeit werden kontrolliert behandelt; verzögerter Datenbankstart darf durch spätere Initialisierungsversuche aufgeholt werden. Bereinigung darf den ursprünglichen Fehler nicht verdecken.

## 8.3.6 Fachliche Ergebnisse und Importabschluss

Eine leere Suchtrefferliste ist ein erfolgreiches fachliches Ergebnis. Die RAG-API beendet dann die Verarbeitung ohne Generierung mit HTTP 200, `status: "no_context"`, `chunks: []` und einer kontrollierten Ablehnungsantwort. Nicht ausgeführte Generierungsmetriken werden als nicht vorhanden gekennzeichnet, nicht als gemessene Nullwerte. Ein Retrievalausfall darf niemals in eine leere Trefferliste umgewandelt werden.

Modell- und Strategiefallbacks sind nur ausdrücklich konfiguriert zulässig. Ein Ergebnis weist die tatsächlich verwendeten Modelle, Varianten und eine mögliche Degradierung aus, damit Evaluationen vergleichbar bleiben.

Der Import bricht im Standardmodus bei Fehlern ab. Optionales `--continue-on-error` erlaubt das Überspringen einzelner dauerhaft fehlerhafter Chunks; systemische Störungen führen nach begrenzten Wiederholungsversuchen weiterhin zum Abbruch. Jeder Lauf erzeugt eine Zusammenfassung mit erfolgreicher, fehlgeschlagener und noch nicht bearbeiteter Chunkanzahl sowie einen Fehlerbericht mit Lauf-ID, Chunk-ID, Set-ID, Schritt und Problemtyp. Die Wiederaufnahme muss gezielt fehlgeschlagene Chunks erfassen können und dieselbe Dokument-/Verarbeitungskonfiguration verwenden.

Vorgesehene CLI-Exitcodes: `0` für vollständigen Erfolg, `1` für Abbruch, `2` für ungültigen CLI-Aufruf und `3` für einen abgeschlossenen Lauf mit Teilfehlern. CLI-Berichte verwenden dieselben Typidentitäten, sind aber keine HTTP-Antworten und führen keinen künstlichen HTTP-Status ein.

## 8.3.7 Diagnose und Betriebszustand

Der HTTP-Eingang übernimmt eine in Format und Länge geprüfte `X-Request-ID` oder erzeugt eine neue Kennung. Diese wird an Abhängigkeiten weitergereicht und in der Antwort zurückgegeben. Pro Dienstfehler entsteht eine eindeutige `instance`; ein Import verwendet zusätzlich eine Lauf-ID.

Strukturierte Logs enthalten Dienst, Request-/Lauf-ID, Fehlerereignis, Verarbeitungsschritt, Problemtyp, Laufzeit und Retryversuch. Stacktraces und Ursachen werden an der verantwortlichen Grenze einmal protokolliert. Zugangsdaten, rohe Upstreamantworten, vollständige Fragen und Dokumenttexte gehören nicht in öffentliche Problemantworten und werden standardmäßig auch nicht geloggt.

Liveness prüft nur, ob der Prozess lebt, und löst keine Modellinitialisierung aus. Readiness beschreibt, ob der Dienst seine Aufgaben ausführen kann; fehlende erforderliche Abhängigkeiten oder Modelle führen zu 503 mit Problem Details. Prüfungen sind zeitlich begrenzt und berücksichtigen die tatsächlich benötigten Abhängigkeiten.

## 8.3.8 Umsetzung und Abnahmekriterien

1. Gemeinsames Fehlerprofil und Typregister, frühe Validierung sowie zentrale Flask-Handler einführen. Die Umstellung vom bisherigen `{"error": ...}`-Format ist eine Schnittstellenänderung: unterstützte Clients, Tests und README gemeinsam aktualisieren.
2. Adapterfehler, Zeitlimits und Retrybudget sowie atomare Writes und sichere Poolbereinigung umsetzen.
3. Fachliche Ergebniszustände, Importberichte und Exitcodes, Wiederaufnahme und Readiness ergänzen.

Containerfreie Tests prüfen Medientyp, Top-Level-Problemobjekt, Typidentität, Feldtypen, Übereinstimmung von HTTP- und Bodystatus, Erhalt von HTTP-Fehlern und Headern, sichere Meldungen sowie Validierung vor Dienstzugriff. Weitere Tests prüfen Fehlerübersetzung, ungültige Upstreamantworten, Budget-/Retrygrenzen, Korrelationskennungen, leeren Kontext und Import-Teilfehler.

Isolierte Podman-Tests prüfen Rollback und Wiederverwendung nach SQL-Fehlern, atomare parallele Upserts, Pool-/Dienstausfälle, verzögerten Datenbankstart und Readiness. Bestehende Datenbestände und manuell genutzte Volumes bleiben erhalten. Teststufen und Ausführungsoptionen folgen [Kapitel 8.1](8-1-testkonzept.md). Die genannten Maßnahmen und Abnahmekriterien sind bis zu ihrer Umsetzung offene Zielzustände.

## Umsetzungsstand TS-03 (21.11.2026)

Frühe Requestvalidierung und zentrale RFC-9457-Fehlerantworten der drei APIs sind in rag_common/http_errors.py umgesetzt. Eingangsregeln und Build-Umstellung beschreibt das README. 99 Unit-Tests und 6 isolierte Podman-Integrationstests mit RAG/Reranker bestehen. Drei optionale Ollama-/Import-/RAG-E2E-Tests wurden nicht aktiviert, da TS-03 keine echte Generierung oder Ingestion ändert. scripts/build_image.py erstellt temporäre Kontexte aus expliziten Quelldateien und umgeht den zuvor bestätigten Windows-Podman-Zugriffsfehler auf tests/.pytest-tmp. Der HTTP-Vertrag aller drei APIs in der isolierten Testumgebung ist durch tests/podman/test_http_errors.py nachgewiesen. Die übrigen Maßnahmen dieses Kapitels bleiben Zielzustände; insbesondere erfolgt noch keine vollständige Adapterfehlerklassifikation oder Readiness-Trennung. Details siehe TS-03 in Kapitel 11.2.

### Ausrollen und anschließende API-Prüfungen (21.11.2026)

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` neu gebaut. Die Container `vector-api`, `rag-api` und `reranker` laufen seit dem Update mit diesen Images. An den regulären Ports 5500, 5600 und 5000 wurden anschließend ungültige Requests erfolgreich mit HTTP 400 und RFC-9457-Problemantworten beantwortet; geprüft wurden Medientyp, Typ-URI, HTTP-/Bodystatus und Request-Korrelation.

Zusätzlich bestanden folgende Betriebsprüfungen: Vector-Zählung über `GET /chunks` (10.378 Datensätze), Reranker-Health mit geladenem `cross-encoder/ms-marco-MiniLM-L6-v2`, echte Bewertung zweier Dokumente sowie eine vollständige RAG-Abfrage mit Embedding, Retrieval und Generierung. Die RAG-Antwort enthielt zwei Quellchunks (`pg3060-552`, `pg3061-301`). Diese lesenden Prüfungen im regulären Betrieb ergänzen die isolierten Integrationstests und ersetzen keinen vollständigen Import-/E2E-Testlauf.

Der Datenbankcontainer wurde weder ersetzt noch neu gestartet; das Volume `pgvector-data` blieb unverändert eingebunden. Vorherige und anschließende SQL-Zählung ergaben jeweils 10.378 Zeilen. Ports, Pod-Zuordnung, Geräte einschließlich GPU, Mounts und Startkonfiguration der APIs wurden erhalten und abgeglichen; lediglich automatisch vergebene Container-Hostnamen änderten sich. Die bisherigen API-Container bleiben gestoppt mit dem Suffix `-before-ts03-20261121` als Rückweg erhalten. Den ausführlichen Prüfnachweis führt [TS-03 in Kapitel 11.2](11-2-technische-schulden.md#ts-03--requestvalidierung-und-fehlerverträge--p1--abgeschlossen). Die weiteren Zielmaßnahmen dieses Konzepts bleiben davon unberührt.

## Umsetzungsstand TS-08 (22.11.2026)

Retrievalvalidierung, kontrollierte Antworten ohne Kontext und robuste Metriken sind in `rag/app.py` umgesetzt. Jeder Treffer benötigt eine nichtleere String-`chunk_id` und String-`chunktext`; ungültige Antworten einschließlich ungültigem JSON liefern 502 Problem Details. Leere Texte werden nach vollständiger Vertragsprüfung aus Kontext und Quellliste entfernt. Bleibt kein Text, erfolgt HTTP 200 mit `status: no_context`, `chunks: []`, `metrics: null` und Ablehnungsantwort ohne Generierung. Retrievalausfälle lösen diesen Erfolgspfad nicht aus.

Bei vorhandener Modellantwort bleiben die Metrikfelder erhalten: nicht verfügbare oder ungültige Einzelwerte sind null, gemessene Nullwerte bleiben 0. Tokenzahlen sind nichtnegative Integer ohne Booleans. `answer_rate` ist nur bei gültiger positiver Generierungsdauer und gültiger Tokenzahl definiert; nicht endliche Raten sind null. 129 Unit-Tests bestanden, einschließlich 18 zusätzlicher TS-08-Prüfungen. Die übrigen offenen Maßnahmen dieses Konzepts und die fehlende Garantie fachlicher Beantwortbarkeit bleiben bestehen.

TS-08-Prüfnachweis (22.11.2026): Isolierte Podman-Regression mit python -m pytest -c tests/pytest.ini tests/podman --include-rag --include-reranker --tb=short erfolgreich: 6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert (128,99 Sekunden). Die TS-08-Sonderfälle sind durch deterministische Unit-Tests abgesichert; ein echter Modelltest für eine fachlich nicht beantwortbare Frage wurde nicht ausgeführt. Reguläre API-Container wurden für diese Änderung nicht aktualisiert.

### TS-08: Ausrollen und Betriebsprüfung (22.11.2026)

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` neu gebaut. Die laufenden API-Container wurden mit ihren zuvor ausgelesenen Startparametern ersetzt und ihre Image-IDs gegen die aktuellen regulären Tags geprüft. Ports, Pod-Zuordnung, Startkommando, Benutzer, Arbeitsverzeichnis, Restart-Policy, Umgebungsvariablen (außer automatisch vergebenem HOSTNAME), GPU-Geräte und Mounts stimmen mit den Vorgängern überein. Die vorherigen API-Container bleiben gestoppt mit dem Suffix `-before-ts08-20261122` als Rückweg erhalten.

Die anschließenden lesenden Betriebsprüfungen bestanden: RFC-9457-Fehlerantworten aller drei APIs; Reranker-Health mit geladenem Modell und echte Bewertung zweier Dokumente; vollständige RAG-Abfrage mit Embedding, Retrieval und Generierung sowie zwei Quellchunks (`pg3060-552`, `pg3061-301`). Eine zusätzliche echte RAG-Anfrage mit einer zufälligen, unbenutzten Set-ID prüfte leeres Retrieval ohne Datenänderung: HTTP 200, `status: no_context`, `chunks: []`, `metrics: null` und kontrollierte Ablehnungsantwort. Das Überspringen der Generierung ist zusätzlich durch die Unit-Tests mit nicht aufgerufenem Generierungs-Mock abgesichert.

Datenbankcontainer `vectordb` und Volume `pgvector-data` wurden bei diesem Ausrollen weder ersetzt noch neu gestartet oder verändert. Die SQL-Zählung und Vector-API ergaben weiterhin 10.378 Datensätze. Der reguläre Betrieb verwendet damit TS-08; frühere Hinweise zum noch ausstehenden Ausrollen beschreiben den Stand vor diesem Schritt. Ein echter Modelltest zur fachlichen Nichtbeantwortbarkeit bei nichtleerem Kontext ist weiterhin kein Bestandteil dieses Nachweises.

### CLI-Fehlerbehandlung und TS-08 (22.11.2026)

`interact.py` verwendet gemeinsame Retrievalvalidierung und Metrikaufbereitung aus `rag_common/rag_results.py`, die auch die RAG-API nutzt. Fehlerhafte Treffer werden nicht als leerer Kontext behandelt. Bei leeren Treffern oder ausschließlich leeren Texten endet die CLI mit kontrollierter Ablehnungsantwort (`no_context`), ohne Export, Reranking oder Generierung. Wenn Reranking keine verwertbaren Dokumente liefert, entfällt ebenfalls die Generierung.

HTTP-Fehler erscheinen verständlich mit Verarbeitungsschritt, tatsächlichem HTTP-Status, `title`/`detail` und vorhandener Typ-URI/Request-ID; rohe Fehlerbodys werden nicht ausgegeben. Timeout und Nichterreichbarkeit erhalten eigene Meldungen. Fehler gehen auf stderr. Exitcode 0 bedeutet Erfolg (auch ohne Kontext), 1 einen Verarbeitungs-/Exportabbruch und 2 ungültige CLI-Argumente. Exportfehler führen zum Abbruch statt zum stillen Fortsetzen. Es gibt keine automatischen Wiederholungen.

Alle HTTP-Aufrufe verwenden getrennte Verbindungs-/Antwortzeitlimits: 5 Sekunden Verbindung, 300 Sekunden Embedding, 60 Sekunden Retrieval sowie 600 Sekunden Generierung und Reranking. Dies sind Requests-Verbindungs-/Lesezeitlimits, kein Gesamtbudget des gesamten Laufs. Fehlende oder ungültige Metriken werden als „nicht verfügbar“ dargestellt; Nullzeiten verursachen keine Division durch null. Der CLI ruft Ollama, Vector-API und Reranker weiterhin direkt auf; seine Modellwahl bleibt unabhängig von der RAG-API.

CLI-Integrationsnachweis (22.11.2026): Isolierte Podman-Regression mit --include-rag --include-reranker: 6 bestanden, 3 optionale Ollama-/Import-/RAG-E2E-Tests nicht aktiviert (137 Sekunden), da keine vollständige Ingestion oder Modellqualitätsprüfung erforderlich war. Zusätzlich bestand der direkte Aufruf von interact.py mit echtem Ollama-Embedding und einer unbenutzten Set-ID: kontrollierte no_context-Antwort, Exitcode 0, keine Generierung und kein Export. Die regulären API-Container wurden für die gemeinsame Codeextraktion nicht neu ausgerollt; geprüft wurden neu gebaute isolierte API-Images.

### Ausrollen des gemeinsamen RAG-Moduls (22.11.2026)

Die regulären Images `localhost/vectorapi:local`, `localhost/rag-api:local` und `localhost/reranker:local` wurden mit `scripts/build_image.py` einschließlich `rag_common/rag_results.py` neu gebaut und die drei laufenden API-Container mit den bisherigen Startparametern ersetzt. Aktuelle Image-IDs wurden mit den regulären Tags abgeglichen; das gemeinsame Modul wurde in jedem Container erfolgreich vom Paketpfad `/rag_common/rag_results.py` importiert. Die Apps nehmen den übergeordneten Paketpfad wie bisher beim Start in den Python-Suchpfad auf.

Die anschließenden lesenden Betriebsprüfungen bestanden: RFC-9457-Fehlerantworten aller drei APIs einschließlich Medientyp, Status und Request-ID; Reranker-Health und echte Bewertung zweier Dokumente; vollständige RAG-Abfrage mit Antwort und zwei Quellchunks (`pg3060-552`, `pg3061-301`). Eine zusätzliche RAG-Abfrage mit zufälliger unbenutzter Set-ID lieferte HTTP 200 mit `status: no_context`, `chunks: []` und `metrics: null`.

Datenbankcontainer `vectordb` wurde weder ersetzt noch neu gestartet; Volume `pgvector-data` blieb eingebunden. SQL- und API-Zählung bestätigten weiterhin 10.378 Datensätze. Ports, Pod-Zuordnung, Mounts, GPU-Geräte, Restart-Policy, Startkommando, Benutzer, Arbeitsverzeichnis und Umgebungsvariablen (außer automatisch vergebenem HOSTNAME) der APIs wurden gegen die Vorgänger abgeglichen und erhalten. Die vorherigen API-Container bleiben gestoppt mit Suffix `-before-shared-module-20261122` als Rückweg erhalten. Die zuvor dokumentierte noch ausstehende Ausrollung der gemeinsamen Codeextraktion ist damit erfolgt; der Nachweis mit 146 Unit-Tests und 6 isolierten Podman-Integrationstests wird durch diese Betriebsprüfung ergänzt.
