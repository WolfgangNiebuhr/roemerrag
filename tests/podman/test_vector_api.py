"""Integration tests for PostgreSQL/pgvector and the Vector API."""

from common import request
import pytest


def vector(first):
    return [first] + [0.0] * 1023


@pytest.mark.podman
def test_vector_api(vector_url, test_id):
    embedding_a = "podman-test-a-" + test_id
    embedding_b = "podman-test-b-" + test_id
    ids = ["podman-a-" + test_id, "podman-b-" + test_id]
    a = {"chunk_id": ids[0], "embedding": embedding_a, "vector": vector(1), "chunktext": "alpha"}
    b = {"chunk_id": ids[1], "embedding_set_id": embedding_b, "vector": vector(0.9), "chunktext": "beta"}
    for chunk in (a, b):
        assert request(vector_url, "/vectors", "POST", chunk, 201)["message"] == "Vector stored"

    assert request(vector_url, "/chunks?embedding=" + embedding_a)["chunks"] == 1
    assert request(vector_url, "/chunks?embedding_set_id=" + embedding_b)["chunks"] == 1
    assert request(vector_url, "/chunks/" + ids[0] + "?embedding=" + embedding_a)["chunktext"] == "alpha"
    a["chunktext"] = "alpha-updated"
    assert request(vector_url, "/vectors", "POST", a, 201)["message"] == "Vector stored"
    assert request(vector_url, "/chunks?embedding=" + embedding_a)["chunks"] == 1
    assert request(vector_url, "/chunks/" + ids[0] + "?embedding=" + embedding_a)["chunktext"] == "alpha-updated"

    query = {"vector": vector(0.92), "num_results": 1, "metric": "euclidean"}
    filtered = request(vector_url, "/search", "POST", {**query, "embedding_set_id": embedding_a})
    assert "metadata" not in filtered[0]
    assert filtered[0]["chunktext"] == "alpha-updated"
    assert filtered[0]["embedding_set_id"] == filtered[0]["embedding"] == embedding_a
    assert len(filtered) == 1 and filtered[0]["chunk_id"] == ids[0], filtered
    unfiltered = request(vector_url, "/search", "POST", query)
    assert len(unfiltered) == 1 and unfiltered[0]["chunk_id"] == ids[1], unfiltered
    cosine = request(vector_url, "/search", "POST", {**query, "metric": "cosine", "embedding": embedding_a})
    assert len(cosine) == 1 and cosine[0]["chunk_id"] == ids[0], cosine
    found = request(vector_url, "/find?query=%25alpha-updated%25")
    assert ids[0] in found["chunk_ids"], found
    assert request(vector_url, "/chunks/missing-" + test_id, expected=404)["type"] == "urn:rag:problem:not-found"

    for chunk_id, embedding in zip(ids, (embedding_a, embedding_b)):
        assert request(vector_url, "/chunk", "DELETE", {"chunk_id": chunk_id, "embedding": embedding})["message"] == "deleted"
    assert request(vector_url, "/chunks?embedding=" + embedding_a)["chunks"] == 0
    assert request(vector_url, "/chunks?embedding_set_id=" + embedding_b)["chunks"] == 0


@pytest.mark.podman
def test_parallel_upserts_preserve_identity(vector_url, test_id):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    payload = {"chunk_id": "parallel-" + test_id, "embedding_set_id": test_id,
               "vector": vector(1), "chunktext": "initial"}
    barrier = Barrier(6)
    def write(index):
        barrier.wait(timeout=30)
        request(vector_url, "/vectors", "POST", {**payload, "chunktext": str(index)}, 201)
    with ThreadPoolExecutor(max_workers=6) as executor:
        list(executor.map(write, range(6)))
    path = "/chunks/" + payload["chunk_id"] + "?embedding_set_id=" + test_id
    initial = request(vector_url, path)
    request(vector_url, "/vectors", "POST", payload, 201)
    assert request(vector_url, path)["id"] == initial["id"]
    assert request(vector_url, "/chunks?embedding_set_id=" + test_id)["chunks"] == 1
    request(vector_url, "/chunk", "DELETE", payload)


@pytest.mark.podman
def test_sql_failure_rolls_back_and_reuses_connection(podman_stack):
    import subprocess
    script = """
import app
import psycopg2
from psycopg2.extensions import TRANSACTION_STATUS_IDLE
app.ensure_db_pool()
with app.transaction() as conn:
    with conn.cursor() as cursor:
        cursor.execute("CREATE TEMP TABLE ts06_rollback (value integer)")
try:
    with app.transaction() as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO ts06_rollback VALUES (1)")
            cursor.execute("SELECT 1 / 0")
except psycopg2.errors.DivisionByZero:
    pass
else:
    raise AssertionError("SQL failure expected")
reused = app.db_pool.getconn()
assert reused is conn
assert reused.get_transaction_status() == TRANSACTION_STATUS_IDLE
app.db_pool.putconn(reused)
with app.transaction() as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM ts06_rollback")
        assert cursor.fetchone() == (0,)
assert conn.get_transaction_status() == TRANSACTION_STATUS_IDLE
assert app.app.test_client().get("/chunks").status_code == 200
app.db_pool.closeall()
"""
    container = "rag-test-vector-" + podman_stack["id"]
    subprocess.run(["podman", "exec", container, "python", "-c", script],
                   check=True, capture_output=True, text=True, timeout=30)
