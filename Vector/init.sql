-- Datei: init.sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS vectors (
  id SERIAL PRIMARY KEY,
  chunk_id TEXT NOT NULL,
  embedding_set_id TEXT NOT NULL,
  vector VECTOR(1024),
  chunktext TEXT NOT NULL,
  CONSTRAINT vectors_chunktext_nonblank CHECK (length(btrim(chunktext, E' \n\r')) > 0),
  UNIQUE (chunk_id, embedding_set_id)
);

-- HNSW-Index (euklidische Distanz)
-- CREATE INDEX IF NOT EXISTS vectors_vector_idx ON vectors USING ivfflat (vector) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS vectors_vector_idx ON vectors USING hnsw (vector vector_l2_ops);
