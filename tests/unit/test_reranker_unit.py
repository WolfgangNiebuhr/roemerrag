"""Integration tests for the cross-encoder reranker."""

import math
from unittest.mock import Mock

import pytest

from reranker import app as reranker_app


def test_reranker_component_validates_request_and_handles_empty_documents(monkeypatch):
    monkeypatch.setattr(reranker_app, "MODEL", Mock())
    client = reranker_app.app.test_client()

    assert client.post("/rerank", json={"query": "q"}).status_code == 400
    assert client.post("/rerank", json={"query": 12, "documents": []}).status_code == 400
    empty = client.post("/rerank", json={"query": "q", "documents": []})
    assert empty.status_code == 200
    assert empty.get_json() == {"ranked_documents": []}
    reranker_app.MODEL.predict.assert_not_called()


def test_reranker_component_scores_and_sorts_documents(monkeypatch):
    model = Mock()
    model.predict.return_value = [0.1, 0.9, -0.2]
    monkeypatch.setattr(reranker_app, "MODEL", model)
    client = reranker_app.app.test_client()

    response = client.post("/rerank", json={
        "query": "machine learning",
        "documents": ["first", "second", "third"],
    })

    assert response.status_code == 200
    ranked = response.get_json()["ranked_documents"]
    assert [item["original_index"] for item in ranked] == [1, 0, 2]
    assert [item["text"] for item in ranked] == ["second", "first", "third"]
    assert [item["score"] for item in ranked] == [0.9, 0.1, -0.2]
    model.predict.assert_called_once_with([
        ["machine learning", "first"],
        ["machine learning", "second"],
        ["machine learning", "third"],
    ])


def test_reranker_component_returns_error_when_model_prediction_fails(monkeypatch):
    model = Mock()
    model.predict.side_effect = RuntimeError("inference failed")
    monkeypatch.setattr(reranker_app, "MODEL", model)
    client = reranker_app.app.test_client()

    response = client.post("/rerank", json={"query": "q", "documents": ["doc"]})

    assert response.status_code == 500
    assert "inference failed" in response.get_json()["error"]
