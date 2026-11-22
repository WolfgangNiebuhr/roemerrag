"""Integration tests for the RAG API."""

from unittest.mock import Mock, patch

import pytest

from rag import app as rag_app


@pytest.fixture(autouse=True)
def fixed_ollama_endpoint(monkeypatch):
    monkeypatch.setattr(rag_app, "resolve_ollama_base_url", lambda: rag_app.OLLAMA_BASE_URL)


def test_rag_api_success_with_mocked_dependencies():
    query = "Wer beherrschte das westliche Mittelmeer?"
    embedding = [3.0, 4.0]
    retrieved = [
        {"chunktext": "Rom kontrollierte große Teile des westlichen Mittelmeers.", "chunk_id": "chunk-rome-1"},
        {"chunktext": "Karthago war Roms bedeutender Rivale.", "chunk_id": "chunk-carthage-2"},
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
    assert vector_payload["embedding_set_id"] == rag_app.EMBEDDING_SET_ID
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
        json={"vector": [0.6, 0.8], "embedding_set_id": "embed-v1", "num_results": 3, "metric": "cosine"},
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

@pytest.mark.parametrize("fields", [{"filter": "legacy"}, {"embedding_set_id": "new"}])
def test_process_accepts_explicit_set_aliases(monkeypatch, fields):
    monkeypatch.setattr(rag_app, "generate_embedding", Mock(return_value=[1]))
    search = Mock(return_value=[{"chunktext": "text", "chunk_id": "c"}])
    monkeypatch.setattr(rag_app, "search_vectors", search)
    monkeypatch.setattr(rag_app, "generate_answer", Mock(return_value=("answer", {})))
    response = rag_app.app.test_client().post("/process", json={"query": "q", **fields})
    assert response.status_code == 200
    assert search.call_args.args[1] == next(iter(fields.values()))


def test_process_rejects_conflicting_aliases_before_embedding(monkeypatch):
    embed = Mock()
    monkeypatch.setattr(rag_app, "generate_embedding", embed)
    response = rag_app.app.test_client().post("/process", json={"query": "q", "filter": "a", "embedding_set_id": "b"})
    assert response.status_code == 400
    embed.assert_not_called()


def test_cli_reranking_keeps_chunktext_and_chunk_identity(monkeypatch):
    import interact
    response = Mock(status_code=200)
    response.json.return_value = {"model": "model", "ranked_documents": [{"text": "second", "original_index": 1}]}
    post = Mock(return_value=response)
    monkeypatch.setattr(interact.requests, "post", post)
    rows = [{"chunk_id": "a", "chunktext": "first"}, {"chunk_id": "b", "chunktext": "second"}]
    assert interact.rerank_results("q", rows, "model", 1) == [{"chunk_id": "b", "chunktext": "second"}]
    assert post.call_args.kwargs["json"]["documents"] == ["first", "second"]

@pytest.mark.parametrize('results', [None, {}, [None], [{}], [{'chunk_id': 1, 'chunktext': 'text'}], [{'chunk_id': 'c', 'chunktext': None}]])
def test_invalid_retrieval_is_502_without_generation(monkeypatch, results):
    monkeypatch.setattr(rag_app, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(rag_app, 'search_vectors', Mock(return_value=results))
    generate = Mock()
    monkeypatch.setattr(rag_app, 'generate_answer', generate)
    response = rag_app.app.test_client().post('/process', json={'query': 'q'})
    assert response.status_code == 502
    assert response.json['type'] == 'urn:rag:problem:upstream-invalid-response'
    assert response.json['stage'] == 'retrieval'
    generate.assert_not_called()


@pytest.mark.parametrize('results', [[], [{'chunk_id': 'c', 'chunktext': '  '}]])
def test_no_context_skips_generation(monkeypatch, results):
    monkeypatch.setattr(rag_app, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(rag_app, 'search_vectors', Mock(return_value=results))
    generate = Mock()
    monkeypatch.setattr(rag_app, 'generate_answer', generate)
    response = rag_app.app.test_client().post('/process', json={'query': 'q'})
    assert response.status_code == 200
    assert response.json['status'] == 'no_context'
    assert response.json['chunks'] == []
    assert response.json['metrics'] is None
    generate.assert_not_called()


@pytest.mark.parametrize('value', [None, 0, -1, 'bad', True, float('nan'), float('inf')])
def test_invalid_optional_metrics_preserve_answer(monkeypatch, value):
    response = Mock(status_code=200)
    response.json.return_value = {'response': 'answer', 'eval_duration': value, 'eval_count': 2}
    monkeypatch.setattr(rag_app.requests, 'post', Mock(return_value=response))
    answer, metrics = rag_app.generate_answer('context', 'question')
    assert answer == 'answer'
    assert metrics['answer_rate'] is None
    assert metrics['total_duration'] is None

def test_invalid_retrieval_json_maps_to_problem(monkeypatch):
    response = Mock(status_code=200)
    response.json.side_effect = ValueError('private upstream body')
    monkeypatch.setattr(rag_app.requests, 'post', Mock(return_value=response))
    from rag_common.http_errors import Problem
    with pytest.raises(Problem) as caught:
        rag_app.search_vectors(rag_app.np.array([1]), 'set', 'cosine', 1)
    assert caught.value.kind == 'upstream-invalid-response'
    assert 'private' not in caught.value.detail


def test_unavailable_retrieval_does_not_become_no_context(monkeypatch):
    monkeypatch.setattr(rag_app, 'generate_embedding', Mock(return_value=rag_app.np.array([1])))
    monkeypatch.setattr(rag_app.requests, 'post', Mock(return_value=Mock(status_code=503)))
    generate = Mock()
    monkeypatch.setattr(rag_app, 'generate_answer', generate)
    response = rag_app.app.test_client().post('/process', json={'query': 'q'})
    assert response.status_code == 503
    generate.assert_not_called()


def test_metrics_zero_tokens_and_invalid_counts():
    metrics = rag_app.generation_metrics({'eval_duration': 1000000000, 'eval_count': 0, 'prompt_eval_count': 1.5})
    assert metrics['answer_rate'] == 0
    assert metrics['prompt_tokens'] is None
