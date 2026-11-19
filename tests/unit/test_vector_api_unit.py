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
    psycopg2_stub.pool = types.SimpleNamespace(SimpleConnectionPool=no_database_pool)
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
    cursor.description = [(name,) for name in ("id", "chunk_id", "embedding", "vector", "metadata", "distance")]
    connection = MagicMock()
    connection.cursor.return_value = cursor
    pool = MagicMock()
    pool.getconn.return_value = connection
    monkeypatch.setattr(vector_module, "db_pool", pool)
    return vector_module, pool, connection, cursor


def test_count_chunks_uses_embedding_filter_and_returns_count(database):
    vector_app, pool, connection, cursor = database
    cursor.fetchone.return_value = (7,)

    response = vector_app.app.test_client().get("/chunks?embedding=embed-a")

    assert response.status_code == 200
    assert response.get_json() == {"chunks": 7}
    assert cursor.execute.call_args_list[0].args[0] == "SELECT 1"
    assert cursor.execute.call_args_list[1].args[1] == ("embed-a",)
    assert "WHERE embedding = %s" in cursor.execute.call_args_list[1].args[0]
    pool.putconn.assert_called_once_with(connection)


def test_search_uses_cosine_operator_and_filter_parameters(database):
    vector_app, pool, connection, cursor = database
    cursor.fetchall.return_value = [(1, "chunk-1", "embed-a", "[1,0]", "text", -0.9)]

    response = vector_app.app.test_client().post("/search", json={
        "vector": "[0.9,0.1]", "embedding": "embed-a", "metric": "cosine", "num_results": 4,
    })

    assert response.status_code == 200
    assert response.get_json() == [{
        "id": 1, "chunk_id": "chunk-1", "embedding": "embed-a",
        "vector": "[1,0]", "metadata": "text", "distance": -0.9,
    }]
    sql, parameters = cursor.execute.call_args_list[1].args
    assert "vector <=> %s::VECTOR" in sql
    assert "WHERE embedding = %s" in sql
    assert parameters == ("[0.9,0.1]", "embed-a", "[0.9,0.1]", 4)
    pool.putconn.assert_called_once_with(connection)


def test_api_reports_unavailable_database_pool(vector_module, monkeypatch):
    monkeypatch.setattr(vector_module, "db_pool", None)

    response = vector_module.app.test_client().get("/chunks")

    assert response.status_code == 500
    assert "error" in response.get_json()


def test_search_rejects_unsupported_metric_without_database_call(database):
    vector_app, pool, _, _ = database
    response = vector_app.app.test_client().post("/search", json={"vector": [1, 0], "metric": "inner_product"})
    assert response.status_code == 400
    pool.getconn.assert_not_called()

def test_find_chunks_uses_parameterized_ilike_query(database):
    vector_app, pool, connection, cursor = database
    cursor.fetchall.return_value = [("chunk-1",), ("chunk-2",)]
    response = vector_app.app.test_client().get("/find?query=%25rome%25")
    assert response.status_code == 200
    assert response.get_json() == {"chunk_ids": ["chunk-1", "chunk-2"]}
    assert cursor.execute.call_args_list[1].args == (
        "SELECT chunk_id FROM vectors WHERE metadata ILIKE %s", ("%rome%",)
    )
    pool.putconn.assert_called_once_with(connection)


def test_api_recovers_when_database_becomes_available(vector_module, monkeypatch):
    client = vector_module.app.test_client()
    assert client.get("/chunks").status_code == 500
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = (7,)
    connection = MagicMock()
    connection.cursor.return_value = cursor
    recovered_pool = MagicMock()
    recovered_pool.getconn.return_value = connection
    factory = MagicMock(return_value=recovered_pool)
    monkeypatch.setattr(vector_module.psycopg2.pool, "SimpleConnectionPool", factory)
    response = client.get("/chunks")
    assert response.status_code == 200
    assert response.get_json() == {"chunks": 7}
    assert client.get("/chunks").status_code == 200
    factory.assert_called_once()
