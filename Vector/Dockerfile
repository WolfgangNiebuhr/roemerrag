# PostgreSQL 17 + pgvector aus Source bauen (entspricht dem K8s initContainer)
FROM postgres:17

# pgvector bauen und installieren
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates git build-essential postgresql-server-dev-17 \
 && update-ca-certificates \
 && git config --system http.sslCAInfo /etc/ssl/certs/ca-certificates.crt \
 && git clone --depth 1 https://github.com/pgvector/pgvector.git /tmp/pgvector \
 && make -C /tmp/pgvector \
 && make -C /tmp/pgvector install \
 && rm -rf /tmp/pgvector /var/lib/apt/lists/*

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
