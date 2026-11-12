Kubernetes-Deployment für Vector

Die Kubernetes-Manifeste liegen in diesem Verzeichnis.
Die lokale Podman-Anleitung befindet sich in ../README.txt.
Die hier beschriebene SQL-Initialisierung ist in deploy-vectordb.yaml eingebettet.

🧱 Architekturüberblick
emptyDir-Volume für den Austausch von Artefakten (z. B. .so, .control, .sql)

InitContainer:

    installiert Build-Abhängigkeiten

    klont das pgvector-Repo

    kompiliert die Erweiterung

    kopiert die Artefakte ins Shared Volume

Hauptcontainer:

    PostgreSQL Image (postgres:<version>)

    verwendet das Volume, um die Extension-Dateien unter /usr/share/postgresql/extension/ und /usr/lib/postgresql/<version>/ bereitzustellen

--------------------------


Die Anweisung in der init.sql-Datei wird automatisch ausgeführt, wenn der PostgreSQL-Container startet. Dies geschieht durch das Standardverhalten des offiziellen PostgreSQL-Docker-Images.

Das Image führt alle SQL-Dateien, die sich im Verzeichnis /docker-entrypoint-initdb.d befinden, während der
Initialisierung der Datenbank aus. In dem vorgeschlagenen Szenario wird die init.sql-Datei über die ConfigMap
in dieses Verzeichnis gemountet. Sobald der Container startet, erkennt PostgreSQL die Datei und führt die darin
enthaltenen SQL-Befehle aus.


----------------

Bei Fehlern beim Start des postgres-containers wegen unpassender vector--x.y.z.sql : in das Log des Initcontainers schauen,
am Ende wird die config ausgebeben, darin steht die default-version, die beim mount im postgres-container angegeben werden muss

----------------
