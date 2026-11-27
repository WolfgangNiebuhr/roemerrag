# 1 Einführung und Ziele  (draft)

## 1.1 Aufgabenstellung

Das RAG-System dient dazu, unterschiedliche Parameter und Strategien für Retrieval Augmented Generation experimentell zu untersuchen und ihre Ergebnisse zu vergleichen. Texte zur römischen Geschichte bilden den Beispielkorpus. Der Experimentator importiert Texte, variiert Verarbeitung und Modelle, stellt Fragen und beurteilt die gefundenen Textstellen, generierten Antworten und verfügbaren Metriken.

Das System unterstützt folgende Aufgaben:

- Texte in Chunks zerlegen, optional mit Keywords anreichern, Embeddings erzeugen und zusammen mit dem Quelltext speichern.
- Importvarianten über Set-Kennungen auswählen und Retrieval mit unterschiedlichen Suchparametern untersuchen.
- Antworten aus gefundenen Textabschnitten generieren und Quell-Chunk-IDs sowie Generierungsmetriken ausgeben.
- Modelle und Reranking über lokale Werkzeuge beziehungsweise HTTP-Schnittstellen erproben. Die RAG-API kann Retrievaltreffer vor der Antwortgenerierung durch den separaten Reranker neu bewerten lassen. [Laufzeitsicht](6-laufzeitsicht.md#61-fragebeantwortung)

Neue Ideen sollen sich schrittweise als Experimente ergänzen lassen. Das Projekt ist eine lokale Experimentierumgebung; eine fachlich korrekte Modellantwort ist durch den RAG-Ablauf allein nicht garantiert. Komponenten und aktueller Funktionsumfang stehen in der [Bausteinsicht](5-bausteinsicht.md).

## 1.2 Qualitätsziele

Die folgenden drei Qualitäten sind gefordert. Die Szenarien beschreiben Zielkriterien, keine pauschal bereits nachgewiesenen Eigenschaften.

| Qualität | Bedeutung für den Experimentator | Konkretes Prüfszenario |
|---|---|---|
| Erweiterbarkeit | Neue Ideen, Verarbeitungsstrategien und Experimente können mit überschaubaren, lokal begrenzten Änderungen ergänzt werden. | Eine weitere Chunking-, Anreicherungs- oder Retrievalstrategie wird ergänzt und gezielt ausgewählt. Bestehende Varianten bleiben nutzbar; ein Vergleich mit der bisherigen Strategie ist möglich. |
| Testbarkeit | Änderungen für neue Experimente lassen sich prüfen, damit bestehende Funktionen und Experimente weiterhin funktionieren. | Vor der Änderung werden relevante Verträge durch Tests abgesichert. Nach Ergänzung eines Experiments bestehen die bisherigen containerfreien Tests und die betroffenen Integrationstests; neue Verarbeitungswege und Fehlerfälle sind gezielt geprüft. |
| Kompatibilität | Das System soll auf verschiedenen Plattformen lauffähig sein. Plattformabhängige Einrichtung soll sich auf dokumentierte Konfiguration und Startschritte begrenzen. | Auf einer weiteren Zielplattform werden Images gebaut, Dienste gestartet, ein kleiner Korpus importiert und eine RAG-Anfrage erfolgreich ausgeführt. Plattformabhängige Netzwerkadressen und Pfade werden dokumentiert; der reguläre Ablauf benötigt keine plattformspezifische Änderung der fachlichen Verarbeitung. |

Für die Kompatibilität ist Windows mit PowerShell, Podman und Ollama die aktuell dokumentierte Referenzumgebung. Ein erfolgreicher Betrieb auf weiteren Plattformen ist separat nachzuweisen. Eine verbindliche Plattformmatrix ist bisher nicht festgelegt. Plattformkompatibilität bedeutet keine bitgleichen Modellantworten auf unterschiedlicher Hardware.

Das [Testkonzept](8-1-testkonzept.md) beschreibt die vorhandenen Teststufen und ihre Grenzen. Offene Verbesserungen stehen im [Schuldenregister](11-2-technische-schulden.md); sie gelten nur bei ausdrücklicher Markierung als Risiken im [Risikoregister](11-1-risiken.md).

## 1.3 Stakeholder

| Stakeholder | Rolle | Interesse und Erwartungen |
|---|---|---|
| Projektinhaber (du) | Experimentator | Neue Ideen selbstständig umsetzen, Parameter und Strategien vergleichen, Auswirkungen anhand von Quellen und Metriken beurteilen und bestehende Experimente durch Tests erhalten. Die Umgebung soll auf verschiedenen Plattformen nutzbar sein. |

Es gibt genau einen Stakeholder. Import, Abfragen, Analyse, Entwicklung und lokaler Betrieb sind Tätigkeiten desselben Experimentators und begründen keine weiteren Stakeholderrollen.
