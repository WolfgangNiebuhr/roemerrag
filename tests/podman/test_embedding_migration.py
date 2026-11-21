"""Real schema migration on an independent disposable database, including backup restore."""
from pathlib import Path
import subprocess
import uuid
import pytest
from scripts.migrate_embedding_set_id import migrate


@pytest.mark.podman
@pytest.mark.parametrize("migration", ["001_embedding_set_id.sql", "002_chunktext.sql"])
def test_migration_preserves_vectors_and_backup(podman_stack, migration):
    db_container = podman_stack["db_container"]
    database = "migration_" + uuid.uuid4().hex
    restored = database + "_restore"
    def command(*args, **kw):
        return subprocess.run(["podman", "exec", "-i", db_container, *args], check=True, capture_output=True, **kw)
    def sql(database, text):
        return command("psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-U", "admin", "-d", database, input=text.encode()).stdout
    is_chunktext = migration == "002_chunktext.sql"
    set_column = "embedding_set_id" if is_chunktext else "embedding"
    text_column = "chunktext" if is_chunktext else "metadata"
    backup_dir = Path("backups") / database
    try:
        command("createdb", "-U", "admin", database)
        sql(database, "CREATE EXTENSION vector; CREATE TABLE vectors (id serial primary key, chunk_id text not null, embedding text not null, vector vector(3), metadata text, UNIQUE(chunk_id, embedding)); INSERT INTO vectors(chunk_id,embedding,vector,metadata) VALUES ('c','legacy','[1,2,3]','text');")
        if is_chunktext:
            sql(database, "ALTER TABLE vectors RENAME COLUMN embedding TO embedding_set_id")
        before = sql(database, f"SELECT id,chunk_id,{set_column},vector,metadata FROM vectors")
        backup = migrate(db_container, "admin", database, backup_dir, migration)
        assert sql(database, f"SELECT id,chunk_id,embedding_set_id,vector,{text_column} FROM vectors") == before
        # Idempotence and retained unique constraint.
        sql(database, (Path("Vector/migrations") / migration).read_text(encoding="utf-8-sig"))
        assert b"UNIQUE (chunk_id, embedding_set_id)" in sql(database, "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='vectors'::regclass")
        command("createdb", "-U", "admin", restored)
        command("pg_restore", "-U", "admin", "-d", restored, input=backup.read_bytes())
        assert sql(restored, f"SELECT id,chunk_id,{set_column},vector,metadata FROM vectors") == before
    finally:
        command("dropdb", "--if-exists", "-U", "admin", restored)
        command("dropdb", "--if-exists", "-U", "admin", database)
        if backup_dir.exists():
            for file in backup_dir.iterdir():
                file.unlink()
            backup_dir.rmdir()
