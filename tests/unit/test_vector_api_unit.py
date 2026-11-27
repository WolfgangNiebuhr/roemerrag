"""Unit tests for Vector API route logic with a mocked PostgreSQL pool."""

import importlib.util
from pathlib import Path
import sys
import types
from unittest.mock import MagicMock

import pytest

@pytest.fixture
def vector_module(monkeypatch):
    class OperationalError(Exception):
        pass

    def no_database_pool(**kwargs):
        raise OperationalError("unit test has no database")

    psycopg2_stub = types.ModuleType("psycopg2")
    psycopg2_stub.OperationalError = OperationalError
    psycopg2_stub.pool = types.SimpleNamespace(ThreadedConnectionPool=no_database_pool)
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg2_stub)
    module_name = "vector_app_under_test"
    app_path = Path(__file__).resolve().parents[2] / "Vector" / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def database(monkeypatch, vector_module):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.description = [(name,) for name in ("id", "chunk_id", "embedding_set_id", "vector", "chunktext", "distance")]
    connection = MagicMock()
    connection.closed = False
    connection.cursor.return_value = cursor
    pool = MagicMock()
    pool.getconn.return_value = connection
    monkeypatch.setitem(vars(vector_module), "db_pool", pool)
    return vector_module, pool, connection, cursor


def test_count_chunks_uses_embedding_filter_and_returns_count(database):
    vector_app, pool, connection, cursor = database
    cursor.fetchone.return_value = (7,)

    response = vector_app.app.test_client().get("/chunks?embedding_set_id=embed-a")

    assert response.status_code == 200
    assert response.get_json() == {"chunks": 7}
    assert cursor.execute.call_args_list[0].args[1] == ("embed-a",)
    assert "WHERE embedding_set_id = %s" in cursor.execute.call_args_list[0].args[0]
    pool.putconn.assert_called_once_with(connection)


def test_search_uses_cosine_operator_and_filter_parameters(database):
    vector_app, pool, connection, cursor = database
    cursor.fetchall.return_value = [(1, "chunk-1", "embed-a", "[1,0]", "text", -0.9)]

    response = vector_app.app.test_client().post("/search", json={
        "vector": [0.9, 0.1] + [0.0] * 1022, "embedding_set_id": "embed-a", "metric": "cosine", "num_results": 4,
    })

    assert response.status_code == 200
    assert response.get_json() == [{
        "id": 1, "chunk_id": "chunk-1", "embedding_set_id": "embed-a",
        "vector": "[1,0]", "chunktext": "text", "distance": -0.9,
    }]
    sql, parameters = cursor.execute.call_args_list[0].args
    assert "vector <=> %s::VECTOR" in sql
    assert "WHERE embedding_set_id = %s" in sql
    assert parameters == ([0.9, 0.1] + [0.0] * 1022, "embed-a", [0.9, 0.1] + [0.0] * 1022, 4)
    pool.putconn.assert_called_once_with(connection)


def test_api_reports_unavailable_database_pool(vector_module, monkeypatch):
    monkeypatch.setitem(vars(vector_module), "db_pool", None)

    response = vector_module.app.test_client().get("/chunks")

    assert response.status_code == 503
    assert response.json["type"] == "urn:rag:problem:dependency-unavailable"


def test_search_rejects_unsupported_metric_without_database_call(database):
    vector_app, pool, _, _ = database
    response = vector_app.app.test_client().post("/search", json={"vector": [1, 0], "metric": "inner_product", "embedding_set_id": "set-a"})
    assert response.status_code == 400
    pool.getconn.assert_not_called()

def test_find_chunks_uses_parameterized_ilike_query(database):
    vector_app, pool, connection, cursor = database
    cursor.fetchall.return_value = [("chunk-1",), ("chunk-2",)]
    response = vector_app.app.test_client().get("/find?query=%25rome%25&embedding_set_id=set-a")
    assert response.status_code == 200
    assert response.get_json() == {"chunk_ids": ["chunk-1", "chunk-2"]}
    assert cursor.execute.call_args_list[0].args == (
        "SELECT chunk_id FROM vectors WHERE embedding_set_id = %s AND chunktext ILIKE %s",
        ("set-a", "%rome%"),
    )
    pool.putconn.assert_called_once_with(connection)


def test_api_recovers_when_database_becomes_available(vector_module, monkeypatch):
    client = vector_module.app.test_client()
    assert client.get("/chunks").status_code == 503
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = (7,)
    connection = MagicMock()
    connection.closed = False
    connection.cursor.return_value = cursor
    recovered_pool = MagicMock()
    recovered_pool.getconn.return_value = connection
    factory = MagicMock(return_value=recovered_pool)
    monkeypatch.setitem(vars(vector_module.psycopg2.pool), "ThreadedConnectionPool", factory)
    response = client.get("/chunks")
    assert response.status_code == 200
    assert response.get_json() == {"chunks": 7}
    assert client.get("/chunks").status_code == 200
    factory.assert_called_once()

@pytest.mark.parametrize("path,method", [("/chunks", "get"), ("/chunks/c", "get"), ("/find", "get"), ("/vectors", "post"), ("/chunks", "delete"), ("/search", "post")])
def test_legacy_embedding_parameter_is_rejected_before_sql(database, path, method):
    module, pool, _, _ = database
    client = module.app.test_client()
    fields = {"embedding": "b", "query": "rom", "chunk_id": "c", "document_id": "rom",
              "from": 1, "vector": [1] * 1024}
    response = getattr(client, method)(path, **({"query_string": fields} if method == "get" else {"json": fields}))
    assert response.status_code == 400
    location = {"parameter": "embedding"} if method == "get" else {"pointer": "/embedding"}
    assert response.get_json()["errors"][0].items() >= location.items()
    pool.getconn.assert_not_called()


def test_write_uses_set_id_database_column(database):
    module, _, connection, cursor = database
    chunktext = " \r\nRom\n "
    response = module.app.test_client().post(
        "/vectors", json={"chunk_id": "c", "embedding_set_id": "set", "vector": [1] * 1024, "chunktext": chunktext},
    )
    assert response.status_code == 201
    assert "embedding_set_id" in cursor.execute.call_args.args[0]
    assert cursor.execute.call_args.args[1][:2] == ("c", "set")
    assert cursor.execute.call_args.args[1][3] == chunktext
    connection.commit.assert_called_once()


@pytest.mark.parametrize("fields", [{}, {"chunktext": None}, {"chunktext": ""}, {"chunktext": "   "},
                                    {"chunktext": " \n\r "}, {"chunktext": 1}])
def test_invalid_chunktext_rejected_before_sql(database, fields):
    module, pool, _, _ = database
    response = module.app.test_client().post("/vectors", json={
        "chunk_id": "c", "embedding_set_id": "set", "vector": [1] * 1024, **fields,
    })
    assert response.status_code == 400
    pool.getconn.assert_not_called()


@pytest.mark.parametrize("failure", ["sql", "commit", "rollback", "return"])
def test_transaction_cleanup(database, failure):
    module, pool, conn, cursor = database
    cursor.fetchone.return_value = (1,)
    original = RuntimeError("original")
    if failure in ("sql", "rollback"):
        cursor.execute.side_effect = original
    if failure == "commit":
        conn.commit.side_effect = original
    if failure == "rollback":
        conn.rollback.side_effect = RuntimeError("cleanup")
    if failure == "return":
        pool.putconn.side_effect = RuntimeError("return")
    response = module.app.test_client().get("/chunks")
    assert response.status_code == (503 if failure == "return" else 500)
    if failure != "return":
        conn.rollback.assert_called_once()
    if failure == "rollback":
        pool.putconn.assert_called_once_with(conn, close=True)
    if failure == "return":
        conn.close.assert_called_once()


def test_pool_exhaustion_is_503(database):
    module, pool, conn, cursor = database
    pool.getconn.side_effect = RuntimeError("exhausted")
    assert module.app.test_client().get("/chunks").status_code == 503
    pool.putconn.assert_not_called()


def test_read_commits(database):
    module, pool, conn, cursor = database
    cursor.fetchone.return_value = (1,)
    assert module.app.test_client().get("/chunks").status_code == 200
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()


def test_liveness_does_not_initialize_pool(vector_module, monkeypatch):
    initialize = MagicMock()
    monkeypatch.setitem(vars(vector_module), "ensure_db_pool", initialize)
    assert vector_module.app.test_client().get("/health/live").get_json() == {"status": "alive"}
    initialize.assert_not_called()


def test_readiness_uses_transaction(database):
    module, pool, conn, cursor = database
    assert module.app.test_client().get("/health/ready").status_code == 200
    conn.commit.assert_called_once()


def test_readiness_translates_schema_failure(database):
    module, _, conn, cursor = database
    cursor.execute.side_effect = RuntimeError("private database error")
    response = module.app.test_client().get("/health/ready")
    assert response.status_code == 503
    assert response.json["type"] == "urn:rag:problem:dependency-unavailable"
    assert response.json["stage"] == "storage"
    assert response.json["detail"] == "Database is unavailable."
    conn.rollback.assert_called_once()


def test_initializing_request_does_not_wait_for_lock(vector_module):
    vector_module.pool_init_lock.acquire()
    try:
        assert vector_module.app.test_client().get("/health/ready").status_code == 503
    finally:
        vector_module.pool_init_lock.release()
