import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_common.http_errors import (
    Problem, install, invalid_request, json_object, problem_response, text_field, validating_request,
)
from rag_common.vector_contract import VectorInputError, parse_search_options, parse_vector
from flask import Flask, request, jsonify
import os
from threading import Lock
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, OperationalError

DB_NAME = os.getenv("POSTGRES_DB", "vector_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

app = Flask(__name__)
install(app, default_stage="storage")

db_pool = None
pool_init_lock = Lock()


class DatabaseUnavailable(RuntimeError):
    """The database cannot currently serve the requested operation."""


@app.errorhandler(DatabaseUnavailable)
def database_unavailable(error):
    return problem_response("dependency-unavailable", "Database is unavailable.")


def ensure_db_pool():
    """Retry initialization on later requests if PostgreSQL starts after the API."""
    global db_pool
    if not pool_init_lock.acquire(blocking=False):
        return
    try:
        if db_pool is not None:
            return
        try:
            db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=10,
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
                host=DB_HOST, port=DB_PORT, connect_timeout=3,
                options="-c statement_timeout=3000 -c lock_timeout=3000"
            )
            app.logger.info("DB-Connection-Pool erstellt")
        except OperationalError:
            app.logger.warning("Database pool initialization unavailable")
    finally:
        pool_init_lock.release()




@app.get("/health/live")
def liveness():
    """Process-only probe: never initialize or acquire a database connection."""
    return jsonify({"status": "alive"})


@app.get("/health/ready")
def readiness():
    check_database_ready()
    return jsonify({"status": "ready"})


def check_database_ready():
    try:
        with transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT chunk_id, embedding_set_id, vector, chunktext FROM vectors LIMIT 0")
    except DatabaseUnavailable:
        raise
    except Exception as exc:
        raise DatabaseUnavailable("Database readiness check failed.") from exc


@contextmanager
def transaction():
    if db_pool is None:
        ensure_db_pool()
    current_pool = db_pool
    if current_pool is None:
        raise DatabaseUnavailable("Database pool is unavailable.")
    try:
        conn = current_pool.getconn()
    except Exception as exc:
        raise DatabaseUnavailable("Could not acquire a database connection.") from exc
    discard = False
    failed = False
    try:
        yield conn
        conn.commit()
    except BaseException as exc:
        failed = True
        try:
            conn.rollback()
        except Exception:
            discard = True
        if isinstance(exc, psycopg2.OperationalError):
            discard = True
        raise
    finally:
        try:
            current_pool.putconn(conn, close=True) if discard or conn.closed else current_pool.putconn(conn)
        except Exception as exc:
            try:
                conn.close()
            except Exception:
                pass
            if not failed:
                raise DatabaseUnavailable("Could not return the database connection.") from exc

def resolve_set_id(data, *, required=False, query_parameter=False):
    if "embedding" in data:
        invalid_request("Verwende embedding_set_id als Set-Kennung.", "embedding",
                        query_parameter=query_parameter)
    return text_field(
        data, "embedding_set_id",
        required=required, query_parameter=query_parameter,
    )


def sql_vector(raw_vector, metric):
    try:
        parsed = parse_vector(raw_vector, metric)
    except VectorInputError as error:
        invalid_request(str(error), error.field)
    # Keep the existing pgvector text and psycopg2 list bindings.
    return raw_vector if isinstance(raw_vector, str) else parsed


def parse_delete_range(data):
    document_id = text_field(data, "document_id")
    start = data.get("from")
    if type(start) is not int or start < 1:
        invalid_request("from muss eine positive ganze Zahl sein.", "from")
    end = data.get("to")
    if "to" in data and (type(end) is not int or end < start):
        invalid_request("to muss eine ganze Zahl größer oder gleich from sein.", "to")
    if "chunk_id" in data:
        invalid_request("Für Löschungen document_id und from verwenden.", "chunk_id")
    return document_id + "-", str(start), str(end) if end is not None else None


@app.route("/chunks", methods=["GET"])
def count_chunks():
    """Optionaler Filter: ?embedding_set_id=...  -> zählt Zeilen"""
    with validating_request():
        embedding_set_id = resolve_set_id(request.args, query_parameter=True)
    with transaction() as conn:
        with conn.cursor() as cur:
            if embedding_set_id:
                cur.execute("SELECT COUNT(*) FROM vectors WHERE embedding_set_id = %s", (embedding_set_id,))
            else:
                cur.execute("SELECT COUNT(*) FROM vectors")
            (cnt,) = cur.fetchone()
        return jsonify({"chunks": cnt})

@app.route("/chunks/<chunk_id>", methods=["GET"])
def get_chunk(chunk_id):
    """GET /chunks/<chunk_id>?embedding_set_id=... -> eine Zeile"""
    with validating_request():
        embedding_set_id = resolve_set_id(request.args, required=True, query_parameter=True)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, chunk_id, embedding_set_id, vector, chunktext
                FROM vectors
                WHERE chunk_id = %s AND embedding_set_id = %s
            """, (chunk_id, embedding_set_id))
            row = cur.fetchone()
            if not row:
                raise Problem("not-found", "Der angefragte Chunk wurde nicht gefunden.")
            cols = [d[0] for d in cur.description]
            return jsonify(dict(zip(cols, row)))

@app.route("/vectors", methods=["POST"])
def upsert_chunk():
    """
    Body (JSON): {chunk_id, embedding_set_id, vector, chunktext}
    - vector: String im pgvector-Format, z.B. '[0.1, 0.2, 0.3]'
    """
    with validating_request():
        data = json_object()
        embedding_set_id = resolve_set_id(data, required=True)
        chunk_id = text_field(data, "chunk_id")
        chunktext = data.get("chunktext")
        if not isinstance(chunktext, str) or not chunktext.strip(" \n\r"):
            invalid_request("chunktext muss ein nichtleerer String sein.", "chunktext")
        vector = sql_vector(data.get("vector"), data.get("metric"))

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vectors (chunk_id, embedding_set_id, vector, chunktext)
                VALUES (%s, %s, %s::VECTOR, %s)
                ON CONFLICT (chunk_id, embedding_set_id) DO UPDATE
                SET vector = EXCLUDED.vector, chunktext = EXCLUDED.chunktext
            """, (chunk_id, embedding_set_id, vector, chunktext))
        return jsonify({"message": "Vector stored"}), 201

@app.delete("/chunks")
def delete_chunks():
    with validating_request():
        data = json_object()
        set_id = resolve_set_id(data, required=True)
        prefix, start, end = parse_delete_range(data)

    # Compare canonical decimal numbers by length, then by digit order.
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM vectors
                WHERE id IN (
                    SELECT id FROM (
                        SELECT id, substring(chunk_id FROM char_length(%(prefix)s) + 1) AS suffix
                        FROM vectors WHERE embedding_set_id = %(set_id)s AND starts_with(chunk_id, %(prefix)s)
                    ) AS document_chunks
                    WHERE suffix ~ '^[1-9][0-9]*$'
                      AND (length(suffix), suffix COLLATE "C") >= (length(%(start)s), %(start)s)
                      AND (%(end)s::text IS NULL OR
                           (length(suffix), suffix COLLATE "C") <= (length(%(end)s), %(end)s))
                )
            """, {"prefix": prefix, "set_id": set_id, "start": start, "end": end})
            deleted = cur.rowcount
    return jsonify({"deleted": deleted})


@app.route("/search", methods=["POST"])
def search_vectors():
    """
    Body (JSON): {vector, num_results?, metric?('euclidean'|'cosine'), embedding_set_id}
    - vector: String im pgvector-Format, z.B. '[0.1, 0.2, 0.3]'
    """
    with validating_request():
        data = json_object()
        embedding_filter = resolve_set_id(data, required=True)
        try:
            metric, num_results = parse_search_options(data, default_count=10)
        except VectorInputError as error:
            invalid_request(str(error), error.field)
        query_vector = sql_vector(data.get("vector"), metric)

    operators = {"euclidean": "<->", "cosine": "<=>"}
    distance_op = operators[metric]

    with transaction() as conn:
        with conn.cursor() as cur:
            sql = f"""
                SELECT id, chunk_id, embedding_set_id, vector, chunktext,
                       vector {distance_op} %s::VECTOR AS distance
                FROM vectors
                WHERE embedding_set_id = %s
                ORDER BY vector {distance_op} %s::VECTOR
                LIMIT %s
            """
            cur.execute(sql, (query_vector, embedding_filter, query_vector, num_results))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]
        return jsonify(rows)

@app.route("/find", methods=["GET"])
def find_chunks():
    """Find chunk IDs whose chunktext matches the ILIKE pattern in query."""
    with validating_request():
        search_query = text_field(request.args, "query", query_parameter=True)
        embedding_set_id = resolve_set_id(request.args, required=True, query_parameter=True)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT chunk_id FROM vectors WHERE embedding_set_id = %s AND chunktext ILIKE %s",
                        (embedding_set_id, search_query))
            chunk_ids = [row[0] for row in cur.fetchall()]
        return jsonify({"chunk_ids": chunk_ids})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500)
