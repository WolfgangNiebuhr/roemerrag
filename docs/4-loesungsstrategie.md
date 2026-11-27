<!--

purpose: "Kompakte Zusammenfassung der prägenden Architekturentscheidungen mit Bezug zu Zielen und Randbedingungen."
agent_instructions:
  - "Diese Anweisungen gelten für das gesamte Kapitel 4 und bleiben im HTML-Kommentar."
  - "Nach arc42 nur grundlegende Lösungsansätze und Entscheidungen aufnehmen, die die Architektur prägen. Dazu gehören der grobe Systemzuschnitt, wesentliche Technologieentscheidungen und Ansätze zur Erreichung der wichtigsten Qualitätsziele."
  - "Pro Ansatz knapp erläutern, was gewählt wurde und warum. Die Begründung auf Projektziele, Qualitätsziele oder maßgebliche Randbedingungen beziehen."
  - "Für Details auf die Bausteinsicht (5), Laufzeitsicht (6), Verteilungssicht (7), Querschnittskonzepte (8) oder Architekturentscheidungen (9) verweisen. Schnittstellendetails, Abläufe, Konfigurationswerte und ausführliche Alternativenabwägungen dort pflegen."
  - "Gültige Änderungen direkt in den fachlich passenden Abschnitt einarbeiten und überholte Aussagen ersetzen. Datierte Nachträge, Änderungshistorie, Prüfnachweise und Ausrollstände ausschließlich in ../changelog.md pflegen."

-->

# 4 Lösungsstrategie nach arc42 – Römer-RAG

Die Strategie richtet sich an den [Qualitätszielen aus Kapitel 1](1-einfuehrung-und-ziele.md#12-qualitätsziele) aus.

## Verantwortlichkeiten und Abhängigkeiten

Der Dienstschnitt orientiert sich an Domain-Driven Design (DDD) und folgt den fachlichen Zuständigkeiten. Nach dem Prinzip der **Single Responsibility** liegt jede Regel bei dem Baustein, der für sie verantwortlich ist. Das unterstützt die **Erweiterbarkeit**, weil Änderungen lokal bleiben können. [Bausteinsicht](5-bausteinsicht.md#52-ebene-1--whitebox)

**Separation of Concerns** gilt zwischen Diensten und innerhalb der Bausteine. Belange, die sich unabhängig voneinander ändern, werden getrennt und über klar definierte Schnittstellen verbunden. Das gilt auch für neue Funktionen und Strategien, etwa wenn ein Verarbeitungsschritt unabhängig von seiner Orchestrierung oder seinem Daten- und Modellzugriff geändert werden soll. Die Übersetzung interner Fehler an der HTTP-Grenze ist ein Anwendungsbeispiel. [Importkonzept](8-4-importkonzept.md#841-ziel-und-leitentscheidung) · [Fehlerkonzept](8-3-error-handling.md#831-ziele-und-verantwortlichkeiten)

## Vergleichbare Experimente

Austauschbare Importstrategien, wiederverwendbare Zwischenartefakte und getrennte Embedding-Sets unterstützen die **Erweiterbarkeit**, weil bestehende Varianten für Vergleiche verfügbar bleiben. Zustandslose Evaluationsendpunkte nutzen dieselben Providerfunktionen wie der reguläre RAG-Ablauf und erlauben es, einzelne Schritte gezielt zu variieren und zu wiederholen. [Importkonzept](8-4-importkonzept.md#841-ziel-und-leitentscheidung) · [Embedding-Sets](8-2-embedding-sets.md#pflege-und-aussagekraft) · [Evaluationsentscheidung](9-architekturentscheidungen.md#stateless-evaluationsendpunkte)

## Testbarkeit

Containerfreie Unit- und Vertragstests prüfen Änderungen an Experimenten schnell. Isolierte Integrationstests prüfen das Zusammenspiel der betroffenen Dienste mit eigenen Testdaten. [Testkonzept](8-1-testkonzept.md#teststufen-und-ausführung)

## Plattformkompatibilität

Containerisierte Dienste und konfigurierbare Dienstadressen halten plattformabhängige Anpassungen möglichst in der Bereitstellung. Windows mit PowerShell, Podman und Ollama ist die dokumentierte Referenzumgebung. Der Betrieb auf weiteren Plattformen ist gesondert nachzuweisen. [Verteilungssicht](7-verteilungssicht.md#73-ports-und-netzwerkgrenzen)
