<!--

purpose: "Technische und organisatorische Vorgaben und Konventionen, die den Gestaltungsspielraum einschränken."
agent_instructions:
  - Dies ist Teil einer  Architekturdokumentation nach Arc42
  - "Je Randbedingung die verbindliche Vorgabe und ihre Auswirkung auf Entwurf, Umsetzung oder Betrieb festhalten. Technische Vorgaben, organisatorische Vorgaben und Konventionen unterscheidbar halten."
  - "Gesetzte Vorgaben von gewählten Lösungsansätzen (4 und 9) und der aktuellen Infrastruktur (7) unterscheiden. Setup- und Bedienbefehle in der README pflegen."
  - "Gültige Änderungen direkt einarbeiten. Datierte Nachträge sowie Änderungs-, Prüf- und Ausrollnachweise ausschließlich in ../changelog.md pflegen."

-->

# 2 Randbedingungen  (draft)

## 2.1 Technische Randbedingungen

| Randbedingung | Bedeutung |
|---|---|
| Python | Anwendungen, Import, Analyse und Tests werden in Python entwickelt. |
| Podman | Der aktuelle lokale Containerbetrieb und die Integrationstests verwenden Podman. |
| PostgreSQL mit pgvector | Chunks, Set-Kennungen und Embeddings werden im vorhandenen relationalen Vektorspeicher gehalten. Das aktuelle Schema verwendet Vektoren mit 1024 Dimensionen; andere Dimensionen benötigen eine bewusste Anpassung. |
| Ollama | Lokale Embedding-, Keyword- und Antwortmodelle werden über Ollama bereitgestellt. Im dokumentierten Windows-Betrieb läuft Ollama außerhalb der Container als Hintergrund-App. |
| Windows und PowerShell als Referenz | Setup und Startbefehle sind für diese Umgebung dokumentiert. Das Qualitätsziel der Plattformkompatibilität bleibt bestehen; weitere Plattformen benötigen angepasste Startanleitungen und einen eigenen Funktionsnachweis. |
| Optionale GPU | Der Grundbetrieb muss ohne GPU möglich sein. GPU-Nutzung hängt von Plattform, Treibern und Modellbibliotheken ab. |
| Bestehende Daten | Manuell genutzte Datenbestände und Volumes sind zu erhalten. Schemaänderungen benötigen einen expliziten Migrationsweg mit Backup; Tests verwenden eigene Ressourcen. |

Konkrete Befehle und Voraussetzungen stehen im [README](../README.md). Die [Verteilungssicht](7-verteilungssicht.md) beschreibt die aktuelle Bereitstellung; sie ist kein Nachweis für den Betrieb auf allen Plattformen.

## 2.2 Organisatorische Randbedingungen

Der Experimentator legt Experimente und deren Parameter fest und beurteilt ihre Ergebnisse. Die Beispieltexte stammen aus dem Themengebiet römische Geschichte. Das System dient der Untersuchung von RAG-Strategien; Anforderungen eines exponierten Mehrbenutzer- oder Produktionsbetriebs sind nicht vereinbart.

Verzeichnisse namens `k8s` sind historische Referenzen und werden bei aktueller Analyse und Weiterentwicklung ausgeschlossen. Kubernetes-spezifische Dokumentation bestimmt den aktuellen Podman-Betrieb nicht.

## 2.3 Konventionen

- Befehle werden aus dem Projektstamm ausgeführt. Setup und Bedienung werden im README, Architekturentscheidungen und Sichten nach arc42 unter `docs` dokumentiert.
- Änderungen an Verhalten, Schnittstellen, Setup oder Architektur werden in der jeweils betroffenen Dokumentation nachgeführt.
- Containerfreie Tests und Integrationstests bleiben getrennt. Betroffene Teststufen werden passend zur Änderung ausgeführt; ausgelassene Prüfungen werden mit Grund benannt. Details stehen im [Testkonzept](8-1-testkonzept.md).
- Verarbeitungsvarianten werden durch `embedding_set_id` bezeichnet. Modellname und Set-Kennung sind unabhängig. Die tatsächlichen Parameter werden gemäß [Entscheidung 9.3](9-architekturentscheidungen.md#93-set-konfiguration-manuell-dokumentieren-21112026) manuell im [Set-ID-Verzeichnis](8-2-embedding-sets.md) gepflegt.
- Technische Schulden und ausdrücklich markierte Risiken werden in getrennten Registern geführt. Eine technische Schuld ist nicht automatisch ein Risiko.
