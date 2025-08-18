from flask import Flask, request, jsonify
import os
import json
import psycopg2
from psycopg2 import pool, OperationalError

DB_NAME = os.getenv("POSTGRES_DB", "vector_db")
DB_USER = os.getenv("DB_USER", "admin")
DB_PASSWORD = os.getenv("DB_PASSWORD", "admin")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))

app = Flask(__name__)

db_pool = None
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        minconn=1, maxconn=10,
        dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD,
        host=DB_HOST, port=DB_PORT
    )
    if db_pool:
        app.logger.info("DB-Connection-Pool erstellt")
except OperationalError as e:
    app.logger.error(f"DB-Pool Fehler: {e}")

def get_conn():
    global db_pool
    if not db_pool:
        raise RuntimeError("DB-Pool nicht verfügbar")
    conn = db_pool.getconn()
    # kurze Probe – bei Fehler neue Verbindung ziehen
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    except Exception:
        db_pool.putconn(conn, close=True)
        conn = db_pool.getconn()
    return conn

@app.route("/chunks", methods=["GET"])
def count_chunks():
    """Optionaler Filter: ?embedding=...  -> zählt Zeilen"""
    if not db_pool:
        return jsonify({"error": "DB nicht verfügbar"}), 500
    embedding = request.args.get("embedding")
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            if embedding:
                cur.execute("SELECT COUNT(*) FROM vectors WHERE embedding = %s", (embedding,))
            else:
                cur.execute("SELECT COUNT(*) FROM vectors")
            (cnt,) = cur.fetchone()
        return jsonify({"count": cnt})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route("/chunk/<chunk_id>", methods=["GET"])
def get_chunk(chunk_id):
    """GET /chunk/<chunk_id>[?embedding=...] -> eine Zeile"""
    if not db_pool:
        return jsonify({"error": "DB nicht verfügbar"}), 500
    embedding = request.args.get("embedding")
    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            if embedding:
                cur.execute("""
                    SELECT id, chunk_id, embedding, vector, metadata
                    FROM vectors
                    WHERE chunk_id = %s AND embedding = %s
                    LIMIT 1
                """, (chunk_id, embedding))
            else:
                cur.execute("""
                    SELECT id, chunk_id, embedding, vector, metadata
                    FROM vectors
                    WHERE chunk_id = %s
                    LIMIT 1
                """, (chunk_id,))
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "nicht gefunden"}), 404
            cols = [d[0] for d in cur.description]
            return jsonify(dict(zip(cols, row)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route("/chunk", methods=["POST"])
def upsert_chunk():
    """
    Body (JSON): {chunk_id, embedding, vector, metadata}
    - vector: String im pgvector-Format, z.B. '[0.1, 0.2, 0.3]'
    """
    if not db_pool:
        return jsonify({"error": "DB nicht verfügbar"}), 500
    data = request.get_json(force=True)
    chunk_id = data["chunk_id"]
    embedding = data["embedding"]
    vector = data["vector"]            # erwartetes String-Format
    metadata = json.dumps(data.get("metadata")) if isinstance(data.get("metadata"), (dict, list)) else data.get("metadata")

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            # einfache „replace“-Semantik
            cur.execute("""
                DELETE FROM vectors WHERE chunk_id = %s AND embedding = %s
            """, (chunk_id, embedding))
            cur.execute("""
                INSERT INTO vectors (chunk_id, embedding, vector, metadata)
                VALUES (%s, %s, %s::VECTOR, %s)
            """, (chunk_id, embedding, vector, metadata))
        conn.commit()
        return jsonify({"message": "Vector stored"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route("/chunk", methods=["DELETE"])
def delete_chunk():
    """
    Body (JSON): {chunk_id, embedding}
    """
    if not db_pool:
        return jsonify({"error": "DB nicht verfügbar"}), 500
    data = request.get_json(force=True)
    chunk_id = data["chunk_id"]
    embedding = data["embedding"]

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM vectors WHERE chunk_id = %s AND embedding = %s
            """, (chunk_id, embedding))
        conn.commit()
        return jsonify({"message": "deleted"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

@app.route("/search", methods=["POST"])
def search_vectors():
    """
    Body (JSON): {vector, num_results?, metric?('euclidean'|'cosine'), embedding?}
    - vector: String im pgvector-Format, z.B. '[0.1, 0.2, 0.3]'
    """
    if not db_pool:
        return jsonify({"error": "DB nicht verfügbar"}), 500
    data = request.get_json(force=True)
    query_vector = data["vector"]
    num_results = int(data.get("num_results", 10))
    metric = data.get("metric", "euclidean")
    embedding_filter = data.get("embedding")

    distance_op = "<->" if metric == "euclidean" else "<#>"

    conn = None
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            if embedding_filter:
                sql = f"""
                    SELECT id, chunk_id, embedding, vector, metadata,
                           vector {distance_op} %s::VECTOR AS distance
                    FROM vectors
                    WHERE embedding = %s
                    ORDER BY vector {distance_op} %s::VECTOR
                    LIMIT %s
                """
                cur.execute(sql, (query_vector, embedding_filter, query_vector, num_results))
            else:
                sql = f"""
                    SELECT id, chunk_id, embedding, vector, metadata,
                           vector {distance_op} %s::VECTOR AS distance
                    FROM vectors
                    ORDER BY vector {distance_op} %s::VECTOR
                    LIMIT %s
                """
                cur.execute(sql, (query_vector, query_vector, num_results))
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            db_pool.putconn(conn)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5500)
