"""Real schema migration on an independent disposable database, including backup restore."""
from pathlib import Path
import subprocess
import uuid
import pytest
from scripts.migrate_embedding_set_id import migrate


@pytest.mark.podman
@pytest.mark.parametrize("migration", [
    "001_embedding_set_id.sql", "002_chunktext.sql", "003_required_chunktext.sql",
])
def test_migration_preserves_vectors_and_backup(podman_stack, migration):
    db_container = podman_stack["db_container"]
    database = "migration_" + uuid.uuid4().hex
    restored = database + "_restore"
    def command(*args, **kw):
        return subprocess.run(["podman", "exec", "-i", db_container, *args], check=True, capture_output=True, **kw)
    def sql(database, text):
        return command("psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-U", "admin", "-d", database, input=text.encode()).stdout
    set_column = "embedding" if migration.startswith("001") else "embedding_set_id"
    source_text_column = "chunktext" if migration.startswith("003") else "metadata"
    text_column = "metadata" if migration.startswith("001") else "chunktext"
    backup_dir = Path("backups") / database
    try:
        command("createdb", "-U", "admin", database)
        sql(database, "CREATE EXTENSION vector; CREATE TABLE vectors (id serial primary key, chunk_id text not null, embedding text not null, vector vector(3), metadata text, UNIQUE(chunk_id, embedding)); INSERT INTO vectors(chunk_id,embedding,vector,metadata) VALUES ('c','legacy','[1,2,3]','text');")
        if set_column == "embedding_set_id":
            sql(database, "ALTER TABLE vectors RENAME COLUMN embedding TO embedding_set_id")
        migration_sql = (Path("Vector/migrations") / migration).read_text(encoding="utf-8-sig")
        if source_text_column == "chunktext":
            sql(database, "ALTER TABLE vectors RENAME COLUMN metadata TO chunktext")
            sql(database, "UPDATE vectors SET chunktext = E' \\n\\r '")
            with pytest.raises(subprocess.CalledProcessError):
                sql(database, migration_sql)
            assert sql(database, "SELECT length(chunktext) FROM vectors") == b"4\n"
            sql(database, "UPDATE vectors SET chunktext = 'text'")
        before = sql(database, f"SELECT id,chunk_id,{set_column},vector,{source_text_column} FROM vectors")
        backup = migrate(db_container, "admin", database, backup_dir, migration)
        assert sql(database, f"SELECT id,chunk_id,embedding_set_id,vector,{text_column} FROM vectors") == before
        # Idempotence and retained unique constraint.
        sql(database, migration_sql)
        if source_text_column == "chunktext":
            for value in ("NULL", "''", "'   '", r"E' \n\r '"):
                with pytest.raises(subprocess.CalledProcessError):
                    sql(database, f"UPDATE vectors SET chunktext = {value}")
                with pytest.raises(subprocess.CalledProcessError):
                    sql(database, "INSERT INTO vectors(chunk_id, embedding_set_id, chunktext) "
                                  f"VALUES ('new', 'legacy', {value})")
        assert b"UNIQUE (chunk_id, embedding_set_id)" in sql(database, "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='vectors'::regclass")
        command("createdb", "-U", "admin", restored)
        command("pg_restore", "-U", "admin", "-d", restored, input=backup.read_bytes())
        assert sql(restored, f"SELECT id,chunk_id,{set_column},vector,{source_text_column} FROM vectors") == before
    finally:
        command("dropdb", "--if-exists", "-U", "admin", restored)
        command("dropdb", "--if-exists", "-U", "admin", database)
        if backup_dir.exists():
            for file in backup_dir.iterdir():
                file.unlink()
            backup_dir.rmdir()
