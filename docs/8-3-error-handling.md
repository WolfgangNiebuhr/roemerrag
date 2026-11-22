# 8.3 Übergreifendes Error-Handling

Stand: 21.11.2026. Dieses Querschnittskonzept beschreibt den Zielzustand und den unten ausgewiesenen aktuellen Umsetzungsstand. Es gilt für RAG-API, Vector-API, Reranker sowie unterstützte Import- und Analysewerkzeuge. Die Umsetzung betrifft insbesondere TS-03, TS-05 bis TS-09, TS-13 und TS-17 aus [Kapitel 11.2](11-2-technische-schulden.md). Bausteine und Teststufen beschreiben die [Bausteinsicht](5-bausteinsicht.md) und das [Testkonzept](8-1-testkonzept.md).

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

TS-06 ist in Vector/app.py umgesetzt: zentraler Transaktionskontext, ThreadedConnectionPool (maximal zehn Verbindungen), atomarer Upsert mit stabiler ID. Poolersch?pfung ergibt 503; automatische Schreibwiederholungen erfolgen nicht. Unit- und isolierte Podman-Pruefungen bestehen: parallele Upserts, stabile IDs sowie SQL-Rollback und Poolwiederverwendung sind nachgewiesen (siehe Changelog).

## 8.3.6 Fachliche Ergebnisse und Importabschluss

Eine leere Suchtrefferliste ist ein erfolgreiches fachliches Ergebnis. Die RAG-API beendet dann die Verarbeitung ohne Generierung mit HTTP 200, `status: "no_context"`, `chunks: []` und einer kontrollierten Ablehnungsantwort. Nicht ausgeführte Generierungsmetriken werden als nicht vorhanden gekennzeichnet, nicht als gemessene Nullwerte. Ein Retrievalausfall darf niemals in eine leere Trefferliste umgewandelt werden.

Modell- und Strategiefallbacks sind nur ausdrücklich konfiguriert zulässig. Ein Ergebnis weist die tatsächlich verwendeten Modelle, Varianten und eine mögliche Degradierung aus, damit Evaluationen vergleichbar bleiben.

Der Import bricht im Standardmodus bei Fehlern ab. Optionales `--continue-on-error` erlaubt das Überspringen einzelner dauerhaft fehlerhafter Chunks; systemische Störungen führen nach begrenzten Wiederholungsversuchen weiterhin zum Abbruch. Jeder Lauf erzeugt eine Zusammenfassung mit erfolgreicher, fehlgeschlagener und noch nicht bearbeiteter Chunkanzahl sowie einen Fehlerbericht mit Lauf-ID, Chunk-ID, Set-ID, Schritt und Problemtyp. Die Wiederaufnahme muss gezielt fehlgeschlagene Chunks erfassen können und dieselbe Dokument-/Verarbeitungskonfiguration verwenden.

Vorgesehene CLI-Exitcodes: `0` für vollständigen Erfolg, `1` für Abbruch, `2` für ungültigen CLI-Aufruf und `3` für einen abgeschlossenen Lauf mit Teilfehlern. CLI-Berichte verwenden dieselben Typidentitäten, sind aber keine HTTP-Antworten und führen keinen künstlichen HTTP-Status ein.

## 8.3.7 Diagnose und Betriebszustand

Der HTTP-Eingang übernimmt eine in Format und Länge geprüfte `X-Request-ID` oder erzeugt eine neue Kennung. Diese wird an Abhängigkeiten weitergereicht und in der Antwort zurückgegeben. Pro Dienstfehler entsteht eine eindeutige `instance`; ein Import verwendet zusätzlich eine Lauf-ID.

Strukturierte Logs enthalten Dienst, Request-/Lauf-ID, Fehlerereignis, Verarbeitungsschritt, Problemtyp, Laufzeit und Retryversuch. Stacktraces und Ursachen werden an der verantwortlichen Grenze einmal protokolliert. Zugangsdaten, rohe Upstreamantworten, vollständige Fragen und Dokumenttexte gehören nicht in öffentliche Problemantworten und werden standardmäßig auch nicht geloggt.

Liveness prüft nur, ob der Prozess lebt, und löst keine Modellinitialisierung aus. Readiness beschreibt, ob der Dienst seine Aufgaben ausführen kann; fehlende erforderliche Abhängigkeiten oder Modelle führen zu 503 mit Problem Details. Prüfungen sind zeitlich begrenzt und berücksichtigen die tatsächlich benötigten Abhängigkeiten.

Vector-API (TS-07): `/health/live` prueft nur den Prozess; `/health/ready` prueft eine Transaktion auf den benoetigten Spalten der Tabelle vectors. Fehlende Bereitschaft ergibt 503 Problem Details. Initialisierung erfolgt bedarfsgesteuert und ohne wartende Initialisierungswarteschlange; spaetere Requests versuchen fehlgeschlagene Initialisierung erneut. connect_timeout, statement_timeout und lock_timeout betragen jeweils drei Sekunden (kein Gesamtbudget). Defekte Poolverbindungen werden verworfen; spaetere Probes stellen die Bereitschaft nach Datenbankwiederanlauf wieder fest.

## 8.3.8 Umsetzung und Abnahmekriterien

1. Gemeinsames Fehlerprofil und Typregister, frühe Validierung sowie zentrale Flask-Handler einführen. Die Umstellung vom bisherigen `{"error": ...}`-Format ist eine Schnittstellenänderung: unterstützte Clients, Tests und README gemeinsam aktualisieren.
2. Adapterfehler, Zeitlimits und Retrybudget sowie atomare Writes und sichere Poolbereinigung umsetzen.
3. Fachliche Ergebniszustände, Importberichte und Exitcodes, Wiederaufnahme und Readiness ergänzen.

Containerfreie Tests prüfen Medientyp, Top-Level-Problemobjekt, Typidentität, Feldtypen, Übereinstimmung von HTTP- und Bodystatus, Erhalt von HTTP-Fehlern und Headern, sichere Meldungen sowie Validierung vor Dienstzugriff. Weitere Tests prüfen Fehlerübersetzung, ungültige Upstreamantworten, Budget-/Retrygrenzen, Korrelationskennungen, leeren Kontext und Import-Teilfehler.

Isolierte Podman-Tests prüfen Rollback und Wiederverwendung nach SQL-Fehlern, atomare parallele Upserts, Pool-/Dienstausfälle, verzögerten Datenbankstart und Readiness. Bestehende Datenbestände und manuell genutzte Volumes bleiben erhalten. Teststufen und Ausführungsoptionen folgen [Kapitel 8.1](8-1-testkonzept.md). Die genannten Maßnahmen und Abnahmekriterien sind bis zu ihrer Umsetzung offene Zielzustände.

Historical change and verification records: [Changelog](../changelog.md).

## Aktueller Umsetzungsstand

TS-03 und TS-08 sind implementiert: gemeinsame frühe Requestvalidierung und RFC-9457-Problemantworten, validierte Retrievaltreffer, keine Generierung ohne Kontext und robuste Metriken. Die regulären API-Images enthalten `rag_common/rag_results.py`; CLI und RAG-API teilen dessen Retrievalvalidierung und Metrikaufbereitung. Bei ausschließlich leeren Texten gilt ebenfalls `no_context`; leere Texte werden erst nach vollständiger Vertragsprüfung aus Kontext und Quellliste entfernt. Nicht verfügbare Einzelmetriken sind null, gemessene Nullwerte bleiben 0; Tokenzahlen erfordern nichtnegative Integer ohne Booleans. Die Garantie fachlicher Beantwortbarkeit bei nichtleerem Kontext ist weiterhin nicht gegeben.

`interact.py` zeigt HTTP-Fehler mit Schritt, tatsächlichem Status, verständlichen Problemfeldern und vorhandener Request-ID auf stderr. Exitcode 0 steht für Erfolg einschließlich fehlendem Kontext, 1 für Verarbeitungs-/Exportabbruch und 2 für ungültige Argumente. Ohne Kontext entfallen Export, Reranking und Generierung. Ein leeres Rerankingergebnis unterbindet ebenfalls die Generierung. Argumentfehler werden auf Deutsch ausgegeben; Parameterabkürzungen sind deaktiviert.

Alle CLI-HTTP-Aufrufe verwenden 5 Sekunden Verbindungszeitlimit; Antwortzeitlimits sind 300 Sekunden für Embedding, 60 Sekunden für Retrieval und 600 Sekunden für Generierung/Reranking. Diese Lesezeitlimits sind kein Gesamtbudget; automatische Retries erfolgen nicht. Ungültige Metriken erscheinen als „nicht verfügbar“. Die CLI ruft die Dienste direkt auf und behält ihre eigene Modellwahl. Weitere Adapterklassifikation, Gesamtbudgets, Importabschluss und getrennte Readiness anderer Dienste bleiben Zielzustände.

## Abgrenzung von Implementierung und Zielkonzept

Die Abschnitte 8.3.1 bis 8.3.8 beschreiben auch noch offene Zielregeln. Implementiert sind die unten ausgewiesenen TS-03-/TS-08-Verträge und das CLI-Verhalten. Die RAG-API verwendet feste Requests-Zeitlimits von 300/60/600 Sekunden für Embedding/Retrieval/Generierung; ein gemeinsames Gesamtbudget und automatische Retries bestehen nicht. Der CLI hat getrennte feste Verbindungs-/Lesezeitlimits, keine konfigurierbaren Budgets.

Nicht alle Adapterfehler sind bereits als spezifische Problemtypen klassifiziert: Nicht erfolgreiche Retrieval-HTTP-Antworten werden derzeit als dependency-unavailable (503) ausgegeben; ungültiges Retrieval-JSON beziehungsweise Trefferverträge als upstream-invalid-response (502). Unerwartete Fehler einschließlich weiterer nicht speziell übersetzter Netzwerk-/Modellfehler erreichen den neutralen 500-Handler. Der derzeitige Handler setzt retryable auf false. Request-IDs werden am API-Eingang geprüft und zurückgegeben, aber noch nicht durch sämtliche ausgehenden Dienstaufrufe weitergereicht. Readiness-Trennung, explizite Transaktionsbereinigung sowie die beschriebenen Import-Exitcodes und Resume-Berichte sind weiterhin Zielmaßnahmen.
