"""Integration tests for the cross-encoder reranker."""

import math
from unittest.mock import Mock

import pytest

from reranker import app as reranker_app

@pytest.fixture(autouse=True)
def default_active_model(monkeypatch):
    monkeypatch.setattr(reranker_app, "ACTIVE_MODEL_NAME", reranker_app.MODEL_NAME)



def test_reranker_component_validates_request_and_handles_empty_documents(monkeypatch):
    monkeypatch.setattr(reranker_app, "MODEL", Mock())
    client = reranker_app.app.test_client()

    assert client.post("/rerank", json={"query": "q"}).status_code == 400
    assert client.post("/rerank", json={"query": 12, "documents": []}).status_code == 400
    empty = client.post("/rerank", json={"query": "q", "documents": []})
    assert empty.status_code == 200
    assert empty.get_json() == {"ranked_documents": [], "model": reranker_app.MODEL_NAME}
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
    assert response.json["type"] == "urn:rag:problem:internal-error"
    assert "inference failed" not in response.text

@pytest.fixture
def model_factory(monkeypatch):
    import sys
    import types
    factory = Mock(side_effect=lambda name, **kwargs: Mock(predict=Mock(return_value=[0.5])))
    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(CrossEncoder=factory))
    monkeypatch.setattr(reranker_app, "MODEL", None)
    monkeypatch.setattr(reranker_app, "ACTIVE_MODEL_NAME", None)
    return factory


def test_model_selection_switching_and_default(model_factory):
    client = reranker_app.app.test_client()
    for selected in ["model-a", "model-a", "model-b", reranker_app.MODEL_NAME]:
        fields = {} if selected == reranker_app.MODEL_NAME else {"model": selected}
        response = client.post("/rerank", json={"query": "q", "documents": ["doc"], **fields})
        assert response.status_code == 200
        assert response.json["model"] == selected
    assert [call.args[0] for call in model_factory.call_args_list] == ["model-a", "model-b", reranker_app.MODEL_NAME]
    assert all(call.kwargs == {"trust_remote_code": False} for call in model_factory.call_args_list)
    assert client.get("/health").json["model_name"] == reranker_app.MODEL_NAME


def test_failed_switch_keeps_previous_model_and_retries(model_factory):
    client = reranker_app.app.test_client()
    payload = {"query": "q", "documents": ["doc"]}
    assert client.post("/rerank", json={**payload, "model": "good"}).status_code == 200
    previous = reranker_app.MODEL
    model_factory.side_effect = RuntimeError("download failed")
    for _ in range(2):
        response = client.post("/rerank", json={**payload, "model": "missing"})
        assert response.status_code == 503
        assert response.json["type"] == "urn:rag:problem:model-unavailable"
        assert response.json["model"] == "missing"
    assert reranker_app.MODEL is previous
    assert reranker_app.ACTIVE_MODEL_NAME == "good"
    assert client.post("/rerank", json={**payload, "model": "good"}).status_code == 200
    assert model_factory.call_count == 3


@pytest.mark.parametrize("payload", [123, {"query": "q", "documents": [3]}, *[{"query": "q", "documents": ["doc"], "model": value} for value in [None, "", "  ", 123, []]]])
def test_invalid_request_does_not_load_model(model_factory, payload):
    assert reranker_app.app.test_client().post("/rerank", json=payload).status_code == 400
    model_factory.assert_not_called()


def test_empty_documents_do_not_load_selected_model(model_factory):
    response = reranker_app.app.test_client().post("/rerank", json={"query": "q", "documents": [], "model": "other"})
    assert response.json == {"ranked_documents": [], "model": "other"}
    model_factory.assert_not_called()


def test_concurrent_requests_keep_selected_model(monkeypatch, model_factory):
    from concurrent.futures import ThreadPoolExecutor
    def factory(name, **kwargs):
        assert reranker_app.MODEL_LOCK.locked()
        def predict(pairs):
            assert reranker_app.MODEL_LOCK.locked()
            assert reranker_app.ACTIVE_MODEL_NAME == name
            return [float(name[-1])]
        return Mock(predict=predict)
    model_factory.side_effect = factory
    def request_model(index):
        selected = f"model-{index % 2}"
        with reranker_app.app.test_client() as client:
            response = client.post("/rerank", json={"model": selected, "query": "q", "documents": ["doc"]})
            assert response.status_code == 200
            assert response.json["model"] == selected
            assert response.json["ranked_documents"][0]["score"] == float(index % 2)
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(request_model, range(20)))


def test_health_preserves_explicit_selection(model_factory):
    client = reranker_app.app.test_client()
    assert client.get("/health").json["model_name"] == reranker_app.MODEL_NAME
    client.post("/rerank", json={"model": "other", "query": "q", "documents": ["doc"]})
    assert client.get("/health").json["model_name"] == "other"
    assert model_factory.call_count == 2


def test_health_translates_model_load_failure(model_factory):
    model_factory.side_effect = RuntimeError("private model download failure")
    response = reranker_app.app.test_client().get("/health")
    assert response.status_code == 503
    assert response.json["type"] == "urn:rag:problem:model-unavailable"
    assert response.json["stage"] == "reranking"
    assert "model" not in response.json
    assert "private" not in response.text
