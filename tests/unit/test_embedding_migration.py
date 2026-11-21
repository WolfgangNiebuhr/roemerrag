"""A failed backup or archive verification must never execute the migration."""
import subprocess
from tempfile import TemporaryDirectory
import pytest
from scripts import migrate_embedding_set_id as migration


@pytest.mark.parametrize("sql_migration", ["001_embedding_set_id.sql", "002_chunktext.sql"])
@pytest.mark.parametrize("failure", ["dump", "verify"])
def test_backup_failure_prevents_schema_change(monkeypatch, failure, sql_migration):
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        if "pg_dump" in args:
            if failure == "dump":
                raise subprocess.CalledProcessError(1, args)
            kwargs["stdout"].write(b"archive")
        elif "pg_restore" in args:
            raise subprocess.CalledProcessError(1, args)
        else:
            pytest.fail("SQL must not execute after failed backup")
    monkeypatch.setattr(migration, "run", run)
    with TemporaryDirectory(prefix="rag-migration-test-") as directory:
        with pytest.raises(subprocess.CalledProcessError):
            migration.migrate("test-db", "admin", "test", directory, sql_migration)
    assert not any("psql" in call for call in calls)
