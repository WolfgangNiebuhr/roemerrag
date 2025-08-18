-- Datei: init.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS vectors (
  id SERIAL PRIMARY KEY,
  chunk_id TEXT NOT NULL,
  embedding TEXT NOT NULL,
  vector VECTOR(1024),
  metadata TEXT,
  UNIQUE (chunk_id, embedding)
);

-- HNSW-Index (euklidische Distanz)
-- CREATE INDEX IF NOT EXISTS vectors_vector_idx ON vectors USING ivfflat (vector) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS vectors_vector_idx ON vectors USING hnsw (vector vector_l2_ops);
