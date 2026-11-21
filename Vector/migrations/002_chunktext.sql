BEGIN;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'vectors' AND column_name = 'metadata') THEN
        ALTER TABLE public.vectors RENAME COLUMN metadata TO chunktext;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'vectors' AND column_name = 'chunktext') THEN
        RAISE EXCEPTION 'vectors.chunktext fehlt';
    END IF;
END $$;
COMMIT;
