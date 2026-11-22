import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_common.http_errors import install, Problem
from flask import Flask, request, jsonify
import os
import json
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
install(app, "vector")

db_pool = None
pool_init_lock = Lock()


def ensure_db_pool():
    """Retry initialization on later requests if PostgreSQL starts after the API."""
    global db_pool
    with pool_init_lock:
        if db_pool is not None:
            return
        try:
            db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=1, maxconn=10,
                dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
                host=DB_HOST, port=DB_PORT, connect_timeout=3
            )
            app.logger.info("DB-Connection-Pool erstellt")
        except OperationalError as e:
            app.logger.error(f"DB-Pool Fehler: {e}")




@app.before_request
def initialize_database():
    if request.routing_exception is None:
        ensure_db_pool()


@contextmanager
def transaction():
    current_pool = db_pool
    try:
        conn = current_pool.getconn()
    except Exception as exc:
        raise Problem("dependency-unavailable", "Database is unavailable.") from exc
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
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            if not failed:
                raise Problem("dependency-unavailable", "Database is unavailable.")

def resolve_set_id(data, required=False):
    new = data.get("embedding_set_id")
    old = data.get("embedding")
    if "embedding_set_id" in data and "embedding" in data and new != old:
        from werkzeug.exceptions import BadRequest
        raise BadRequest("embedding_set_id und embedding widersprechen sich")
    value = new if "embedding_set_id" in data else old
    if required and (not isinstance(value, str) or not value.strip()):
        from werkzeug.exceptions import BadRequest
        raise BadRequest("embedding_set_id ist erforderlich")
    return value


def compatible_row(row):
    row["embedding"] = row["embedding_set_id"]
    return row


@app.route("/chunks", methods=["GET"])
def count_chunks():
    """Optionaler Filter: ?embedding_set_id=...  -> zählt Zeilen"""
    if not db_pool:
        raise Problem("dependency-unavailable", "Database is unavailable.")
    embedding_set_id = resolve_set_id(request.args)
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
    """GET /chunks/<chunk_id>[?embedding_set_id=...] -> eine Zeile"""
    if not db_pool:
        raise Problem("dependency-unavailable", "Database is unavailable.")
    embedding_set_id = resolve_set_id(request.args)
    with transaction() as conn:
        with conn.cursor() as cur:
            if embedding_set_id:
                cur.execute("""
                    SELECT id, chunk_id, embedding_set_id, vector, chunktext
                    FROM vectors
                    WHERE chunk_id = %s AND embedding_set_id = %s
                    LIMIT 1
                """, (chunk_id, embedding_set_id))
            else:
                cur.execute("""
                    SELECT id, chunk_id, embedding_set_id, vector, chunktext
                    FROM vectors
                    WHERE chunk_id = %s
                    LIMIT 1
                """, (chunk_id,))
            row = cur.fetchone()
            if not row:
                raise Problem("not-found", "Der angefragte Chunk wurde nicht gefunden.")
            cols = [d[0] for d in cur.description]
            return jsonify(compatible_row(dict(zip(cols, row))))

@app.route("/vectors", methods=["POST"])
def upsert_chunk():
    """
    Body (JSON): {chunk_id, embedding_set_id, vector, chunktext}
    - vector: String im pgvector-Format, z.B. '[0.1, 0.2, 0.3]'
    """
    if not db_pool:
        raise Problem("dependency-unavailable", "Database is unavailable.")
    data = request.get_json(force=True)
    chunk_id = data["chunk_id"]
    embedding_set_id = resolve_set_id(data, required=True)
    vector = data["vector"]            # erwartetes String-Format
    chunktext = json.dumps(data.get("chunktext")) if isinstance(data.get("chunktext"), (dict, list)) else data.get("chunktext")

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO vectors (chunk_id, embedding_set_id, vector, chunktext)
                VALUES (%s, %s, %s::VECTOR, %s)
                ON CONFLICT (chunk_id, embedding_set_id) DO UPDATE
                SET vector = EXCLUDED.vector, chunktext = EXCLUDED.chunktext
            """, (chunk_id, embedding_set_id, vector, chunktext))
        return jsonify({"message": "Vector stored"}), 201

@app.route("/chunk", methods=["DELETE"])
def delete_chunk():
    """
    Body (JSON): {chunk_id, embedding_set_id}
    """
    if not db_pool:
        raise Problem("dependency-unavailable", "Database is unavailable.")
    data = request.get_json(force=True)
    chunk_id = data["chunk_id"]
    embedding_set_id = resolve_set_id(data, required=True)

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM vectors WHERE chunk_id = %s AND embedding_set_id = %s
            """, (chunk_id, embedding_set_id))
        return jsonify({"message": "deleted"}), 200

@app.route("/search", methods=["POST"])
def search_vectors():
    """
    Body (JSON): {vector, num_results?, metric?('euclidean'|'cosine'), embedding_set_id?}
    - vector: String im pgvector-Format, z.B. '[0.1, 0.2, 0.3]'
    """
    if not db_pool:
        raise Problem("dependency-unavailable", "Database is unavailable.")
    data = request.get_json(force=True)
    query_vector = data["vector"]
    num_results = int(data.get("num_results", 10))
    metric = data.get("metric", "euclidean")
    embedding_filter = resolve_set_id(data)

    operators = {"euclidean": "<->", "cosine": "<=>"}
    if metric not in operators:
        return jsonify({"error": "Nur die Metriken 'euclidean' und 'cosine' werden unterstützt"}), 400
    distance_op = operators[metric]

    with transaction() as conn:
        with conn.cursor() as cur:
            if embedding_filter:
                sql = f"""
                    SELECT id, chunk_id, embedding_set_id, vector, chunktext,
                           vector {distance_op} %s::VECTOR AS distance
                    FROM vectors
                    WHERE embedding_set_id = %s
                    ORDER BY vector {distance_op} %s::VECTOR
                    LIMIT %s
                """
                cur.execute(sql, (query_vector, embedding_filter, query_vector, num_results))
            else:
                sql = f"""
                    SELECT id, chunk_id, embedding_set_id, vector, chunktext,
                           vector {distance_op} %s::VECTOR AS distance
                    FROM vectors
                    ORDER BY vector {distance_op} %s::VECTOR
                    LIMIT %s
                """
                cur.execute(sql, (query_vector, query_vector, num_results))
            cols = [d[0] for d in cur.description]
            rows = [compatible_row(dict(zip(cols, r))) for r in cur.fetchall()]
        return jsonify(rows)

@app.route("/find", methods=["GET"])
def find_chunks():
    """Find chunk IDs whose chunktext matches the ILIKE pattern in query."""
    if not db_pool:
        raise Problem("dependency-unavailable", "Database is unavailable.")
    search_query = request.args.get("query")
    if not search_query:
        return jsonify({"error": "Parameter 'query' fehlt"}), 400
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT chunk_id FROM vectors WHERE chunktext ILIKE %s", (search_query,))
            chunk_ids = [row[0] for row in cur.fetchall()]
        return jsonify({"chunk_ids": chunk_ids})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500)
