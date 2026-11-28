# PostgreSQL 17 mit vorinstalliertem pgvector 0.8.0 auf Debian Trixie
FROM docker.io/pgvector/pgvector:0.8.0-pg17-trixie@sha256:0f5e199db9a7e94ee03a6e00365a7c670e54a3e5516fc6a56ac3952e26a3b9c1

# Init-Skript wie im ConfigMap: wird beim ersten Start automatisch ausgeführt
COPY init.sql /docker-entrypoint-initdb.d/init.sql

# Entspricht den K8s-Umgebungsvariablen
ENV POSTGRES_USER=admin \
    POSTGRES_PASSWORD=admin \
    POSTGRES_DB=vector_db \
    PGDATA=/var/lib/postgresql/data/pgdata

EXPOSE 5432

# Optional: Healthcheck ähnlich K8s Readiness
HEALTHCHECK --interval=30s --timeout=5s --retries=5 CMD pg_isready -U "$POSTGRES_USER" || exit 1
