"""Integration tests for the RAG API."""

from unittest.mock import Mock, patch

import pytest

from rag import app as rag_app


def test_rag_api_success_with_mocked_dependencies():
    query = "Wer beherrschte das westliche Mittelmeer?"
    embedding = [3.0, 4.0]
    retrieved = [
        {"metadata": "Rom kontrollierte große Teile des westlichen Mittelmeers.", "chunk_id": "chunk-rome-1"},
        {"metadata": "Karthago war Roms bedeutender Rivale.", "chunk_id": "chunk-carthage-2"},
    ]
    ollama_embedding = Mock(status_code=200)
    ollama_embedding.json.return_value = {"embedding": embedding}
    vector_response = Mock(status_code=200)
    vector_response.json.return_value = retrieved
    ollama_answer = Mock(status_code=200)
    ollama_answer.json.return_value = {
        "response": "Rom beherrschte große Teile des westlichen Mittelmeers.",
        "total_duration": 2_000_000_000,
        "load_duration": 100_000_000,
        "prompt_eval_duration": 400_000_000,
        "eval_duration": 1_000_000_000,
        "prompt_eval_count": 20,
        "eval_count": 10,
    }

    with patch.object(rag_app.requests, "post", side_effect=[ollama_embedding, vector_response, ollama_answer]) as post:
        client = rag_app.app.test_client()
        response = client.post("/process", json={"query": query, "metric": "cosine", "num_results": 2})

    assert response.status_code == 200
    body = response.get_json()
    assert body["response"] == "Rom beherrschte große Teile des westlichen Mittelmeers."
    assert body["chunks"] == ["chunk-rome-1", "chunk-carthage-2"]
    assert body["metrics"]["total_duration"] == 2.0
    assert body["metrics"]["prompt_tokens"] == 20
    assert body["metrics"]["answer_tokens"] == 10

    assert post.call_count == 3
    embedding_call, vector_call, answer_call = post.call_args_list
    assert embedding_call.args[0] == rag_app.OLLAMA_EMBEDDING_URL
    assert embedding_call.kwargs["json"] == {"model": rag_app.EMBEDDING_MODEL_NAME, "prompt": query}
    assert vector_call.args[0] == rag_app.VECTOR_API_URL
    vector_payload = vector_call.kwargs["json"]
    assert vector_payload["vector"] == [0.6, 0.8]
    assert vector_payload["embedding"] == "snowflake-arctic-embed2"
    assert vector_payload["metric"] == "cosine" and vector_payload["num_results"] == 2
    assert answer_call.args[0] == rag_app.OLLAMA_ANSWER_URL
    answer_payload = answer_call.kwargs["json"]
    assert answer_payload["model"] == rag_app.ANSWER_MODEL_NAME
    assert "Rom kontrollierte große Teile" in answer_payload["prompt"]
    assert "Karthago war Roms bedeutender Rivale." in answer_payload["prompt"]
    assert query in answer_payload["prompt"]


def test_generate_embedding_normalizes_vector(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"embedding": [3.0, 4.0]}
    post = Mock(return_value=response)
    monkeypatch.setattr(rag_app.requests, "post", post)

    result = rag_app.generate_embedding("test query")

    assert result.tolist() == pytest.approx([0.6, 0.8])
    post.assert_called_once_with(
        rag_app.OLLAMA_EMBEDDING_URL,
        json={"model": rag_app.EMBEDDING_MODEL_NAME, "prompt": "test query"},
        timeout=300,
    )


@pytest.mark.parametrize("embedding", [None, [], [0.0, 0.0]])
def test_generate_embedding_rejects_missing_or_zero_vector(monkeypatch, embedding):
    response = Mock(status_code=200)
    response.json.return_value = {"embedding": embedding}
    monkeypatch.setattr(rag_app.requests, "post", Mock(return_value=response))

    with pytest.raises(ValueError):
        rag_app.generate_embedding("test query")


def test_generate_embedding_rejects_http_error(monkeypatch):
    response = Mock(status_code=503, text="model unavailable")
    monkeypatch.setattr(rag_app.requests, "post", Mock(return_value=response))

    with pytest.raises(Exception, match="model unavailable"):
        rag_app.generate_embedding("test query")


def test_search_vectors_sends_filters_and_rejects_non_list(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"results": []}
    post = Mock(return_value=response)
    monkeypatch.setattr(rag_app.requests, "post", post)

    with pytest.raises(Exception, match="Erwartet wurde eine Liste"):
        rag_app.search_vectors(rag_app.np.array([0.6, 0.8]), "embed-v1", "cosine", 3)

    post.assert_called_once_with(
        rag_app.VECTOR_API_URL,
        json={"vector": [0.6, 0.8], "embedding": "embed-v1", "num_results": 3, "metric": "cosine"},
        timeout=60,
    )


def test_generate_answer_converts_metrics_and_reports_http_error(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {
        "response": "answer", "total_duration": 2_000_000_000,
        "load_duration": 500_000_000, "prompt_eval_duration": 250_000_000,
        "eval_duration": 1_000_000_000, "prompt_eval_count": 12, "eval_count": 8,
    }
    post = Mock(return_value=response)
    monkeypatch.setattr(rag_app.requests, "post", post)

    answer, metrics = rag_app.generate_answer("context", "question")

    assert answer == "answer"
    assert metrics == {
        "total_duration": 2.0, "load_duration": 0.5,
        "prompt_eval_duration": 0.25, "eval_duration": 1.0,
        "prompt_tokens": 12, "answer_tokens": 8, "answer_rate": 8.0,
    }
    assert post.call_args.args[0] == rag_app.OLLAMA_ANSWER_URL
    assert post.call_args.kwargs["json"]["prompt"] == "Kontext:\ncontext\n\nFrage: question"

    post.return_value = Mock(status_code=500, text="generation failed")
    with pytest.raises(Exception, match="generation failed"):
        rag_app.generate_answer("context", "question")
