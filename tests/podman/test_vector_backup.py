"""Restore a backup of the current Vector schema in the isolated test stack."""
import subprocess
from uuid import uuid4

import pytest


@pytest.mark.podman
def test_restore_current_vector_schema(podman_stack):
    container = podman_stack["db_container"]
    source = "backup_" + uuid4().hex
    target = source + "_restore"

    def command(*args, data=None):
        return subprocess.run(
            ["podman", "exec", "-i", container, *args],
            input=data, capture_output=True, check=True,
        ).stdout

    def query(database, statement):
        return command("psql", "-XAt", "-v", "ON_ERROR_STOP=1", "-U", "admin",
                       "-d", database, "-c", statement)

    try:
        command("createdb", "-U", "admin", source)
        command("psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", "admin", "-d", source,
                "-f", "/docker-entrypoint-initdb.d/init.sql")
        query(source, "INSERT INTO vectors (chunk_id, embedding_set_id, vector, chunktext) "
                      "VALUES ('chunk', 'set', array_fill(0.5::real, ARRAY[1024])::vector, 'text')")
        backup = command("pg_dump", "-U", "admin", "-d", source, "-Fc")
        command("createdb", "-U", "admin", target)
        command("pg_restore", "--exit-on-error", "-U", "admin", "-d", target, data=backup)
        assert query(target, "SELECT * FROM vectors") == query(source, "SELECT * FROM vectors")
        for value in ("NULL", "''", "'   '", r"E' \n\r '"):
            with pytest.raises(subprocess.CalledProcessError):
                query(target, f"UPDATE vectors SET chunktext = {value}")
            with pytest.raises(subprocess.CalledProcessError):
                query(target, "INSERT INTO vectors (chunk_id, embedding_set_id, chunktext) "
                              f"VALUES ('new', 'set', {value})")
        with pytest.raises(subprocess.CalledProcessError):
            query(target, "INSERT INTO vectors (chunk_id, embedding_set_id, chunktext) "
                          "VALUES ('chunk', 'set', 'duplicate')")
    finally:
        command("dropdb", "--if-exists", "-U", "admin", target)
        command("dropdb", "--if-exists", "-U", "admin", source)
