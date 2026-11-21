BEGIN;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'vectors' AND column_name = 'embedding') THEN
        ALTER TABLE public.vectors RENAME COLUMN embedding TO embedding_set_id;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'vectors' AND column_name = 'embedding_set_id') THEN
        RAISE EXCEPTION 'vectors.embedding_set_id fehlt';
    END IF;
END $$;
COMMIT;
