BEGIN;
ALTER TABLE public.vectors
    ALTER COLUMN chunktext SET NOT NULL,
    DROP CONSTRAINT IF EXISTS vectors_chunktext_nonblank;
ALTER TABLE public.vectors
    ADD CONSTRAINT vectors_chunktext_nonblank CHECK (length(btrim(chunktext, E' \n\r')) > 0);
COMMIT;
