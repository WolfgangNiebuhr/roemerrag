# 8.2 Zuordnung von Embedding-Sets und Verarbeitungsparametern

Stand: 21.11.2026. Dieses manuell gepflegte Verzeichnis ordnet `embedding_set_id` den Parametern der Datenaufbereitung zu. Die Entscheidung zur manuellen Pflege steht in [Abschnitt 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026); das bewusst verbleibende Risiko beschreibt [R-01](11-1-risiken.md#r-01--manuelle-zuordnung-von-importvarianten--akzeptiertes-risiko).

## Pflege und Aussagekraft

Vor einem Import die tatsächlich verwendeten Parameter und die Set-ID hier eintragen. Ändern sich Chunking, Anreicherung, Prompts, Embeddingmodell oder Normalisierung, manuell eine neue Set-ID vergeben und einen neuen Eintrag anlegen. Bestehende Zuordnungen nicht nachträglich auf eine andere Konfiguration umdeuten. Wiederholungsimporte mit gleicher Verarbeitung dürfen dieselbe Kennung verwenden; die Importlaufverwaltung bleibt Thema von TS-05.

Umgebungsvariablen können die Defaults für Modell und Set überschreiben. Maßgeblich für einen Eintrag sind die beim Import tatsächlich verwendeten Werte. Es gibt keine technische Prüfung, automatische Identitätsbildung oder Speicherung dieser Konfiguration in der Datenbank. Bei Evaluationen die verwendete Set-ID festhalten; Retrieval- und Generierungsparameter wie Suchmetrik, Trefferzahl, Reranker und Antwortmodell gehören zum jeweiligen Versuch.

Ein aktueller Codezustand belegt nicht die historische Herkunft bereits gespeicherter Vektoren. Fehlende Angaben bleiben ausdrücklich unbekannt. Die Pflege dieses Verzeichnisses erfordert weder eine Datenmigration noch ein erneutes Embedding.

## Verzeichnis

| `embedding_set_id` | Zugeordnete Verarbeitung | Nachweisstand |
|---|---|---|
| `snowflake-arctic-embed2-v2` | Unten dokumentierter aktueller Standard von Import3 | Aus dem Code vom 21.11.2026 abgeleitet. Nicht als vollständiger Herkunftsnachweis aller Bestandsvektoren bestätigt. |
| `embedding1` | Unbekannt | Bei der Bestandsaufnahme zur Set-ID-Migration vorgefunden; ursprüngliche Parameter nicht belegt. |
| `embedding2` | Unbekannt | Bei der Bestandsaufnahme zur Set-ID-Migration vorgefunden; ursprüngliche Parameter nicht belegt. |

### `snowflake-arctic-embed2-v2`: dokumentierter Import3-Standard

| Parameter | Wert / Verfahren |
|---|---|
| Importpfad | [Ingest/import3.py](../Ingest/import3.py), `process_file` |
| Quelle | UTF-8-Textdateien; vollständige Dateiliste und Inhaltsstände des historischen Bestands unbekannt |
| Chunking | LangChain `RecursiveCharacterTextSplitter`, Zeichenbasis, `chunk_size=1000`, `chunk_overlap=150` |
| Trennzeichen | In dieser Reihenfolge: `"\n\n"`, `".\n"`, `". "`; siehe [chunking.py](../Ingest/chunking.py) |
| Keyword-Anreicherung | Aktiv, über Ollama `/api/chat`, Modell `gemma3:4b`, `temperature=0.0`, `stream=false`; siehe [gateway.py](../Ingest/gateway.py) |
| Keyword-Anzahl | Aus der Länge des ursprünglichen Chunks: unter 200 Zeichen Aufforderung zu einem Keyword; 200–399 zu 1, 400–599 zu 2, 600–799 zu 3, ab 800 zu 4 Keywords |
| Keyword-Prompts | Momentaufnahme unten; Implementierung: [keywords.py](../Ingest/keywords.py) |
| Eingabe fürs Embedding | Unveränderte Keyword-Antwort + `"\n"` + ursprünglicher Chunk; kein zusätzlicher Embedding-Prompt oder Präfix |
| Embeddingmodell | `snowflake-arctic-embed2`, Ollama `/api/embeddings`; tatsächliche Modellrevision unbekannt |
| Normalisierung | Division durch die L2-Norm des Embeddingvektors vor Speicherung |
| Dimension | 1024 laut Datenbankschema; Modell-/Dimensionswechsel benötigen gesonderte Prüfung |
| Gespeicherter Text | `chunktext` enthält denselben angereicherten Text, der eingebettet wird |
| Modell- und Softwarestände | Exakte Modellrevisionen und historische Bibliotheksstände unbekannt; siehe auch TS-15 |

Die Konfiguration folgt den Code-Defaults. Eine abweichende Belegung von `EMBEDDING_MODEL` oder `EMBEDDING_SET_ID` ist hier als eigene tatsächliche Zuordnung zu dokumentieren.

### Vorlage für weitere Sets

Für jede neue Set-ID einen eigenen Abschnitt mit folgenden Angaben ergänzen:

- Set-ID, Datum und Nachweisstand (geplant, tatsächlich verwendet oder historisch unvollständig belegt).
- Importpfad, Quelldateien und bekannte Inhaltsstände.
- Chunkingverfahren, Größe, Überlappung und Trennzeichen.
- Anreicherung einschließlich Modell, Optionen und vollständiger Promptfassung; bei deaktivierter Anreicherung ausdrücklich „keine“.
- Tatsächlich eingebetteter Textaufbau, Embeddingmodell, bekannte Revision, Dimension und Normalisierung.
- Bekannte Code-/Bibliotheksstände sowie verbleibende unbekannte Angaben.

## Keyword-Prompts des dokumentierten Import3-Standards

Die folgende Momentaufnahme gehört zum oben beschriebenen Codezustand. Sie bestätigt keine historische Promptfassung des gesamten Bestands. Schreibweisen einschließlich bestehender Tippfehler werden unverändert dokumentiert.

System-Prompt:

```text
Du bist ein Experte für die Analyse von Texten. Du extrahierst keywords aus Texten die als Kontext übergeben werden.Priorität der keywords: (1) ein zentraler Begriff, der den Kontext insgesamt charakterisiert, (2) Personen mit Titel/Attribut, (3) Götter/Orte/Ethnonyme, (4) zentrale Sachbegriffe. Titel-Regel: Wenn ein Name unmittelbar mit einem Titel/Attribut genannt wird (z. B. „König“, „Dr.“, „Göttin“), verwende die Kombination als EIN Keyword. Länge der Keywords: Es sollen nicht mehr als drei Wörter für ein keyword verwendet werden.Variante bei Mehrfachformen: Wenn derselbe Begriff in mehreren Sprachen/Schreibungen vorkommt, wähle die im Kontext erstgenannte Form.Span-Genauigkeit: Gib die exakte Zeichenkette aus dem Kontext wieder (inkl. Groß-/Kleinschreibung und Schreibweise; keine Normalisierung wie Umlaute ergänzen/ändern). Format: Gib mir die Antwort als kommaseparierte Liste, beginnend mit dem gefundenen zentralen Begriff und gefolgt von den gefundenen keywords. Keine Halluzinationen: Verwende ausschließlich Begriffe und Keywords, die genau so im Kontext stehen. 
```

User-Prompt (Platzhalter `{chunk}` und `{question}` werden ersetzt):

```text
<<BEGINN KONTEXT>>:
{chunk}
<<ENDE KONTEXT>>
Frage: {question}
Berücksichtige, dass als Antwort eusschließliche ien Mommaseparierte Liste von Keywords gewünscht ist, keine weiteren Erläuterungen oder Ergänzungen.
```

`{question}` bei weniger als 200 Zeichen:

```text
Generiere mir ein keyword aus dem Kontext. Das keyword soll prägnant, sachlich und inhaltlich beschreibend sein.
```

`{question}` ab 200 Zeichen (`{n_keywords}` entsprechend der Tabelle):

```text
generiere mir  {n_keywords} Keywords aus dem Kontext und gib mir diese als kommaseparierte Liste ohne weiteren Text.
```
