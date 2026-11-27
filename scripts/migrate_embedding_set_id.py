"""Back up and migrate an existing Podman PostgreSQL database, without embedding."""
import argparse
from datetime import datetime
from pathlib import Path
import subprocess


def run(*args, **kwargs):
    return subprocess.run(["podman", *args], check=True, **kwargs)


def migrate(container, user, database, backup_dir, migration="001_embedding_set_id.sql"):
    sql = Path(__file__).resolve().parents[1] / "Vector/migrations" / migration
    sql_bytes = sql.read_bytes()
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".dump")
    # Binary file handle avoids PowerShell encoding/redirect corruption.
    with backup.open("xb") as output:
        run("exec", container, "pg_dump", "-U", user, "-d", database, "-Fc", stdout=output)
    if not backup.stat().st_size:
        raise RuntimeError("Empty backup; migration aborted")
    with backup.open("rb") as source:
        run("exec", "-i", container, "pg_restore", "--list", stdin=source, stdout=subprocess.DEVNULL)
    print(f"Verified backup: {backup.resolve()}", flush=True)
    run("exec", "-i", container, "psql", "-X", "-v", "ON_ERROR_STOP=1", "-U", user,
        "-d", database, input=sql_bytes)
    return backup


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="vectordb")
    parser.add_argument("--user", default="admin")
    parser.add_argument("--database", default="vector_db")
    parser.add_argument("--backup-dir", default="backups")
    parser.add_argument("--migration", choices=[
        "001_embedding_set_id.sql", "002_chunktext.sql", "003_required_chunktext.sql",
    ], default="001_embedding_set_id.sql")
    args = parser.parse_args()
    migrate(args.container, args.user, args.database, args.backup_dir, args.migration)
