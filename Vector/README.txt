Kubernetes-Deployment: siehe k8s/README.txt.

Lokale Version via Podman

podman build -t vectordb:local .
podman volume create pgvector-data
podman run -d --name vectordb -p 127.0.0.1:5432:5432 -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vector_db -e PGDATA=/var/lib/postgresql/data/pgdata -v pgvector-data:/var/lib/postgresql/data localhost/vectordb:local

ohne Volume:
podman run -d --name vectordb -p 127.0.0.1:5432:5432 -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vector_db localhost/vectordb:local


Zusammen mit API-Image in einem Pod
podman build -f Dockerfile.api -t vectorapi:local .
podman pod create --name vectorpod -p 127.0.0.1:5432:5432 -p 127.0.0.1:5500:5500
podman volume create pgvector-data
podman run -d --name vectordb --pod vectorpod -e POSTGRES_USER=admin -e POSTGRES_PASSWORD=admin -e POSTGRES_DB=vector_db -e PGDATA=/var/lib/postgresql/data/pgdata -v pgvector-data:/var/lib/postgresql/data localhost/vectordb:local
podman run -d --name vector-api --pod vectorpod -e DB_HOST=127.0.0.1 -e DB_PORT=5432 -e DB_USER=admin -e DB_PASSWORD=admin -e POSTGRES_DB=vector_db localhost/vectorapi:local


named-Volume liegt meist auf C: !!!
Podman-VM auf D: umziehen (wenn du weiterhin Named Volumes nutzen willst)

WSL2-Backend: Du kannst die WSL-Distro exportieren und auf D: neu importieren:

# Maschine stoppen
podman machine stop

# Namen prüfen
podman machine list  # z.B. podman-machine-default

# Export + Reimport der WSL-Distro (Name ggf. anpassen)
wsl --export podman-machine-default D:\wsl\podman-machine-default.tar
wsl --unregister podman-machine-default
wsl --import podman-machine-default D:\wsl\podman-machine-default D:\wsl\podman-machine-default.tar --version 2

# VM wieder starten
podman machine start

# Gestoppten Pod wieder starten
podman pod start vectorpod

# Mit lokal installiertem psql direkt vom Windows-Host verbinden
psql -h 127.0.0.1 -p 5432 -U admin -d vector_db

# Mit psql im DB-Container verbinden
podman exec -it vectordb psql -U admin -d vector_db

# Aktuelles Schema: vectors(id, chunk_id, embedding_set_id, vector, chunktext).
# Quelltext steht in chunktext; metadata wird nicht mehr unterstützt.

# Vector-Api container neu starten
podman restart vector-api


############################

Zu testende Modelle für Keywords:
deepseek-r1:1.5b
gemma3:4b
qwen3:1.7b   oder :4b
llama3.2:3b         macht auch mist
phi4-mini:3.8b
granite3.2:2b !
granite3.1-dense:2b !  für summyrite, text classification u.a.
llama-guard3:1b mal testen
gemma4:e4b prüfen
