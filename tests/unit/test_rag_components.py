"""Integration tests for the RAG API."""

import json
from unittest.mock import Mock, patch

import numpy as np
import pytest
import requests

from rag import app as rag_app, embedding, generation, reranking, retrieval, transport
from rag_common.rag_results import InvalidResults, generation_metrics


TEST_OLLAMA_URL = "http://ollama.test:12345"


@pytest.fixture(autouse=True)
def fixed_ollama_endpoint(monkeypatch):
    for step in (embedding, generation):
        monkeypatch.setattr(step, "resolve_ollama_base_url", lambda: TEST_OLLAMA_URL)


def test_rag_api_success_with_mocked_dependencies():
    query = "Wer beherrschte das westliche Mittelmeer?"
    vector = [3.0, 4.0] + [0.0] * 1022
    retrieved = [
        {"chunktext": "Rom kontrollierte große Teile des westlichen Mittelmeers.", "chunk_id": "chunk-rome-1", "vector": [1.] + [0.] * 1023},
        {"chunktext": "Karthago war Roms bedeutender Rivale.", "chunk_id": "chunk-carthage-2"},
    ]
    ollama_embedding = Mock(status_code=200)
    ollama_embedding.json.return_value = {"embedding": vector}
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

    with patch("requests.post", side_effect=[ollama_embedding, vector_response, ollama_answer]) as post:
        client = rag_app.app.test_client()
        response = client.post("/process", json={"query": query, "metric": "cosine", "num_results": 2})

    assert response.status_code == 200
    body = response.get_json()
    assert body["response"] == "Rom beherrschte große Teile des westlichen Mittelmeers."
    assert body["chunks"] == ["chunk-rome-1", "chunk-carthage-2"]
    assert all("vector" not in row for row in body["retrieved_results"])
    assert body["metrics"]["total_duration"] == 2.0
    assert body["metrics"]["prompt_tokens"] == 20
    assert body["metrics"]["answer_tokens"] == 10

    assert post.call_count == 3
    embedding_call, vector_call, answer_call = post.call_args_list
    assert all(
        call.kwargs["headers"] == {"X-Request-ID": response.headers["X-Request-ID"]}
        for call in post.call_args_list
    )
    assert embedding_call.args[0] == f"{TEST_OLLAMA_URL}/api/embeddings"
    assert embedding_call.kwargs["json"] == {"model": embedding.EMBEDDING_MODEL_NAME, "prompt": query}
    assert vector_call.args[0] == retrieval.VECTOR_API_URL
    vector_payload = vector_call.kwargs["json"]
    assert vector_payload["vector"] == [0.6, 0.8] + [0.0] * 1022
    assert "include_vector" not in vector_payload
    assert vector_payload["embedding_set_id"] == rag_app.EMBEDDING_SET_ID
    assert vector_payload["metric"] == "cosine" and vector_payload["num_results"] == 2
    assert answer_call.args[0] == f"{TEST_OLLAMA_URL}/api/generate"
    assert answer_call.kwargs["timeout"] == (transport.CONNECT_TIMEOUT, transport.READ_TIMEOUTS["generation"])
    answer_payload = answer_call.kwargs["json"]
    assert answer_payload["model"] == generation.ANSWER_MODEL_NAME
    assert "Rom kontrollierte große Teile" in answer_payload["prompt"]
    assert "Karthago war Roms bedeutender Rivale." in answer_payload["prompt"]
    assert query in answer_payload["prompt"]


def test_generate_embedding_normalizes_vector(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"embedding": [3.0, 4.0] + [0.0] * 1022}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)

    result = embedding.generate_embedding("test query")

    assert result.tolist() == pytest.approx([0.6, 0.8] + [0.0] * 1022)
    post.assert_called_once_with(
        f"{TEST_OLLAMA_URL}/api/embeddings",
        json={"model": embedding.EMBEDDING_MODEL_NAME, "prompt": "test query"},
        timeout=(5, 300), headers={},
    )


@pytest.mark.parametrize("vector", [None, [], [0.0] * 1024])
def test_generate_embedding_rejects_missing_or_zero_vector(monkeypatch, vector):
    response = Mock(status_code=200)
    response.json.return_value = {"embedding": vector}
    monkeypatch.setattr("requests.post", Mock(return_value=response))

    with pytest.raises(transport.InvalidProviderResponse):
        embedding.generate_embedding("test query")


def test_generate_embedding_rejects_http_error(monkeypatch):
    response = Mock(status_code=503, text="model unavailable")
    monkeypatch.setattr("requests.post", Mock(return_value=response))

    with pytest.raises(transport.ProviderUnavailable, match="Embedding is unavailable"):
        embedding.generate_embedding("test query")


def test_retrieve_hits_sends_filters_and_rejects_non_list(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"results": []}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)

    with pytest.raises(InvalidResults, match="Erwartet wurde eine Liste"):
        retrieval.retrieve_hits(np.array([0.6, 0.8]), "embed-v1", "cosine", 3)

    post.assert_called_once_with(
        retrieval.VECTOR_API_URL,
        json={"vector": [0.6, 0.8], "embedding_set_id": "embed-v1", "num_results": 3, "metric": "cosine"},
        timeout=(5, 60), headers={},
    )


def test_generate_answer_converts_metrics_and_reports_http_error(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {
        "response": "answer", "total_duration": 2_000_000_000,
        "load_duration": 500_000_000, "prompt_eval_duration": 250_000_000,
        "eval_duration": 1_000_000_000, "prompt_eval_count": 12, "eval_count": 8,
    }
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)

    answer, metrics = generation.generate_answer("context", "question")

    assert answer == "answer"
    assert metrics == {
        "total_duration": 2.0, "generation_duration": 2.0, "load_duration": 0.5,
        "prompt_eval_duration": 0.25, "eval_duration": 1.0,
        "prompt_tokens": 12, "answer_tokens": 8, "answer_rate": 8.0,
    }
    assert post.call_args.args[0] == f"{TEST_OLLAMA_URL}/api/generate"
    assert post.call_args.kwargs["json"]["prompt"] == "Kontext:\ncontext\n\nFrage: question"

    post.return_value = Mock(status_code=500, text="generation failed")
    with pytest.raises(transport.ProviderUnavailable, match="Generation is unavailable"):
        generation.generate_answer("context", "question")

@pytest.mark.parametrize("fields, expected_set", [
    ({}, rag_app.EMBEDDING_SET_ID),
    ({"embedding_set_id": "new"}, "new"),
])
def test_process_selects_embedding_set(monkeypatch, fields, expected_set):
    monkeypatch.setattr(embedding, "generate_embedding", Mock(return_value=[1]))
    search = Mock(return_value=[{"chunktext": "text", "chunk_id": "c"}])
    monkeypatch.setattr(retrieval, "retrieve_hits", search)
    monkeypatch.setattr(generation, "generate_answer", Mock(return_value=("answer", {})))
    response = rag_app.app.test_client().post("/process", json={"query": "q", **fields})
    assert response.status_code == 200
    assert search.call_args.args[1] == expected_set


def test_cli_reranking_keeps_chunktext_and_chunk_identity(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"model": "model", "ranked_documents": [
        {"text": "second", "original_index": 1, "score": 0.9},
    ]}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)
    rows = [{"chunk_id": "a", "chunktext": "first"}, {"chunk_id": "b", "chunktext": "second"}]
    assert reranking.rerank_results("q", rows, "model", 1) == [{"chunk_id": "b", "chunktext": "second"}]
    assert post.call_args.kwargs["json"]["documents"] == ["first", "second"]

@pytest.mark.parametrize('results', [None, {}, [None], [{}], [{'chunk_id': 1, 'chunktext': 'text'}], [{'chunk_id': 'c', 'chunktext': None}]])
@pytest.mark.parametrize('endpoint', ['/process', '/evaluate/retrieve'])
def test_invalid_retrieval_is_502_without_generation(monkeypatch, results, endpoint):
    vector = np.array([1.0])
    embed_result = (vector, {}) if endpoint == '/evaluate/retrieve' else vector
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(return_value=embed_result))
    upstream = Mock(status_code=200)
    upstream.json.return_value = results
    monkeypatch.setattr("requests.post", Mock(return_value=upstream))
    generate = Mock()
    monkeypatch.setattr(generation, 'generate_answer', generate)
    response = rag_app.app.test_client().post(endpoint, json={'query': 'q'})
    assert response.status_code == 502
    assert response.json['type'] == 'urn:rag:problem:upstream-invalid-response'
    assert response.json['stage'] == 'retrieval'
    generate.assert_not_called()


@pytest.mark.parametrize('results', [[], [{'chunk_id': 'c', 'chunktext': '  '}]])
def test_no_context_skips_generation(monkeypatch, results):
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(retrieval, 'retrieve_hits', Mock(return_value=results))
    generate = Mock()
    monkeypatch.setattr(generation, 'generate_answer', generate)
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
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    answer, metrics = generation.generate_answer('context', 'question')
    assert answer == 'answer'
    assert metrics['answer_rate'] is None
    assert metrics['total_duration'] is None

def test_invalid_retrieval_json_maps_to_problem(monkeypatch):
    response = Mock(status_code=200)
    response.json.side_effect = ValueError('private upstream body')
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(return_value=np.array([1])))
    result = rag_app.app.test_client().post('/process', json={'query': 'q'})
    assert result.status_code == 502
    assert result.mimetype == 'application/problem+json'
    assert result.json['type'] == 'urn:rag:problem:upstream-invalid-response'
    assert result.json['stage'] == 'retrieval'
    assert result.json['detail'] == 'Retrieval returned invalid JSON.'


def test_unavailable_retrieval_does_not_become_no_context(monkeypatch):
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(return_value=np.array([1])))
    monkeypatch.setattr("requests.post", Mock(return_value=Mock(status_code=503)))
    generate = Mock()
    monkeypatch.setattr(generation, 'generate_answer', generate)
    response = rag_app.app.test_client().post('/process', json={'query': 'q'})
    assert response.status_code == 503
    assert response.json['type'] == 'urn:rag:problem:dependency-unavailable'
    assert response.json['stage'] == 'retrieval'
    generate.assert_not_called()


@pytest.mark.parametrize("path,payload,stage", [
    ("/evaluate/retrieve", {"query": "q"}, "embedding"),
    ("/evaluate/generate", {"query": "q", "results": [{"chunk_id": "c", "chunktext": "text"}]}, "generation"),
])
def test_ollama_resolution_failure_returns_safe_problem(monkeypatch, path, payload, stage):
    error = rag_app.OllamaResolutionError("http://private-ollama.test:11434: private upstream body")
    for step in (embedding, generation):
        monkeypatch.setattr(step, "resolve_ollama_base_url", Mock(side_effect=error))
    post = Mock()
    monkeypatch.setattr("requests.post", post)

    response = rag_app.app.test_client().post(path, json=payload)

    assert response.status_code == response.json["status"] == 503
    assert response.mimetype == "application/problem+json"
    assert response.json["type"] == "urn:rag:problem:dependency-unavailable"
    assert response.json["stage"] == stage
    assert response.json["detail"] == "Ollama ist nicht erreichbar."
    assert "private-ollama.test" not in response.text
    assert "private upstream body" not in response.text
    post.assert_not_called()


def test_metrics_zero_tokens_and_invalid_counts():
    metrics = generation_metrics({'eval_duration': 1000000000, 'eval_count': 0, 'prompt_eval_count': 1.5})
    assert metrics['answer_rate'] == 0
    assert metrics['prompt_tokens'] is None


@pytest.mark.parametrize("mapping", [[{"original_index": True, "score": 0.9}],
    [{"original_index": 2, "score": 0.9}],
    [{"original_index": 0, "score": 0.9}, {"original_index": 0, "score": 0.8}], None])
def test_reranking_rejects_invalid_mapping(monkeypatch, mapping):
    response = Mock(status_code=200)
    response.json.return_value = {"ranked_documents": mapping}
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    with pytest.raises(transport.InvalidProviderResponse):
        reranking.rerank_results("q", [{"chunk_id":"c", "chunktext":"text"}], "m", 1)


@pytest.mark.parametrize("endpoint", ["/process", "/evaluate/rerank"])
@pytest.mark.parametrize("invalid_score", [
    {"score": float("nan")}, {"score": float("inf")}, {"score": -float("inf")},
    {"score": True}, {"score": "0.5"}, {"score": None}, {},
])
def test_rag_rejects_invalid_score_beyond_top_k(monkeypatch, endpoint, invalid_score):
    rows = [{"chunk_id": "a", "chunktext": "first"}, {"chunk_id": "b", "chunktext": "second"}]
    monkeypatch.setattr(embedding, "generate_embedding", Mock(return_value=[1]))
    monkeypatch.setattr(retrieval, "retrieve_hits", Mock(return_value=rows))
    generate = Mock()
    monkeypatch.setattr(generation, "generate_answer", generate)
    response = Mock(status_code=200)
    response.json.return_value = {"ranked_documents": [
        {"original_index": 0, "score": 0.9}, {"original_index": 1, **invalid_score},
    ]}
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    payload = {"query": "q", "top_k": 1}
    if endpoint == "/evaluate/rerank":
        payload["results"] = rows

    result = rag_app.app.test_client().post(endpoint, json=payload)

    assert result.status_code == 502
    assert result.json["type"] == "urn:rag:problem:upstream-invalid-response"
    assert result.json["stage"] == "reranking"
    generate.assert_not_called()


def test_rag_preserves_reranker_bad_gateway_status(monkeypatch):
    monkeypatch.setattr("requests.post", Mock(return_value=Mock(status_code=502)))
    result = rag_app.app.test_client().post("/evaluate/rerank", json={
        "query": "q", "results": [{"chunk_id": "a", "chunktext": "first"}],
    })
    assert result.status_code == 502
    assert result.json["stage"] == "reranking"


@pytest.mark.parametrize("top_k", [-1, True, "1", 1.5])
def test_reranking_validation_before_embedding(monkeypatch, top_k):
    embed = Mock()
    monkeypatch.setattr(embedding, "generate_embedding", embed)
    assert rag_app.app.test_client().post('/process', json={'query':'q', 'top_k':top_k}).status_code == 400
    embed.assert_not_called()


@pytest.mark.parametrize("selected", [[], [{"chunk_id":"b", "chunktext":"second"}]])
def test_process_reranks_and_preserves_original_results(monkeypatch, selected):
    rows = [{"chunk_id":"a", "chunktext":"first"}, {"chunk_id":"b", "chunktext":"second"}]
    monkeypatch.setattr(embedding, "generate_embedding", Mock(return_value=[1]))
    monkeypatch.setattr(retrieval, "retrieve_hits", Mock(return_value=rows))
    rerank = Mock(return_value=selected)
    monkeypatch.setattr(reranking, "rerank_results", rerank)
    generate = Mock(return_value=("answer", {}))
    monkeypatch.setattr(generation, "generate_answer", generate)
    response = rag_app.app.test_client().post('/process', json={'query':'q', 'top_k':1,
                                            'reranker':'rerank', 'answer_model':'answer-model'})
    assert response.status_code == 200
    assert response.json['retrieved_results'] == rows
    assert response.json['selected_results'] == selected
    assert response.json['reranking']['model'] == 'rerank'
    rerank.assert_called_once_with('q', rows, 'rerank', 1, with_scores=True, post=rag_app.upstream_post)
    if selected:
        generate.assert_called_once_with('second', 'q', 'answer-model', post=rag_app.upstream_post)
    else:
        assert response.json['status'] == 'no_context'
        generate.assert_not_called()


@pytest.mark.parametrize('stage,attempts', [('embedding',2), ('generation',1)])
def test_transport_retries_are_bounded(monkeypatch, stage, attempts):
    post = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr("requests.post", post)
    with pytest.raises(transport.ProviderUnavailable):
        transport.upstream_post('url', {}, stage)
    assert post.call_count == attempts


def test_cli_and_http_equivalent_configuration(monkeypatch):
    import interact
    import sys
    rows = [{'chunk_id':'c', 'chunktext':'text'}]
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(retrieval, 'retrieve_hits', Mock(return_value=rows))
    monkeypatch.setattr(generation, 'generate_answer', Mock(return_value=('answer', {})))
    client = rag_app.app.test_client()
    calls = []
    def request_api(url, payload, operation, timeout):
        calls.append(url)
        return client.post('/process', json=payload).json
    monkeypatch.setattr(interact, 'post_json', request_api)
    export = Mock()
    monkeypatch.setattr(interact, 'export_results', export)
    monkeypatch.setattr(sys, 'argv', ['interact.py', '--query','q', '--top_k','0'])
    assert interact.main() == 0
    assert calls == [interact.RAG_API_URL]
    export.assert_called_once_with('q', rows)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, [1], "1"])
def test_embedding_invalid_provider_vectors(monkeypatch, value):
    response = Mock(status_code=200)
    response.json.return_value = {"embedding": [value] + [0.0] * 1023}
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    with pytest.raises(transport.InvalidProviderResponse, match='Embedding returned an invalid vector'):
        embedding.generate_embedding('q')


@pytest.mark.parametrize("path", ["/process", "/evaluate/retrieve"])
def test_wrong_provider_dimension_fails_before_retrieval(monkeypatch, path):
    provider = Mock(status_code=200, json=lambda: {"embedding": [1.0] * 1023})
    post = Mock(return_value=provider)
    monkeypatch.setattr("requests.post", post)
    response = rag_app.app.test_client().post(path, json={"query": "q"})
    assert response.status_code == 502
    assert response.json["type"] == "urn:rag:problem:upstream-invalid-response"
    assert response.json["stage"] == "embedding"
    post.assert_called_once()


@pytest.mark.parametrize('body', [{}, {'response':None}, {'response':3}, []])
def test_generation_rejects_invalid_provider_answer(monkeypatch, body):
    response = Mock(status_code=200)
    response.json.return_value = body
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    with pytest.raises(transport.InvalidProviderResponse, match='Generation returned an invalid answer'):
        generation.generate_answer('text', 'q')


@pytest.mark.parametrize('endpoint', ['rerank', 'generate'])
def test_invalid_client_results_remain_a_validation_problem(monkeypatch, endpoint):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    response = rag_app.app.test_client().post('/evaluate/' + endpoint, json={
        'query': 'q', 'results': [{'chunk_id': 'c', 'chunktext': None}],
    })
    assert response.status_code == 400
    assert response.json['type'] == 'urn:rag:problem:invalid-request'
    assert response.json['stage'] == 'validation'
    assert response.json['errors'][0]['pointer'] == '/results'
    post.assert_not_called()


@pytest.mark.parametrize('value', [None, '', ' ', 42])
def test_invalid_answer_model_rejected_before_embedding(monkeypatch, value):
    embed = Mock()
    monkeypatch.setattr(embedding, 'generate_embedding', embed)
    assert rag_app.app.test_client().post('/process', json={'query':'q','answer_model':value}).status_code == 400
    embed.assert_not_called()


def test_answer_model_configuration_defaults_and_override():
    import os
    import subprocess
    import sys
    environment = dict(os.environ)
    environment.pop('ANSWER_MODEL', None)
    code = 'from rag.embedding_config import ANSWER_MODEL; print(ANSWER_MODEL)'
    result = subprocess.check_output([sys.executable, '-c', code], env=environment, text=True)
    assert result.strip() == 'gemma4:e4b'
    environment['ANSWER_MODEL'] = 'custom-model'
    assert subprocess.check_output([sys.executable, '-c', code], env=environment, text=True).strip() == 'custom-model'


@pytest.mark.parametrize('mode', ['plain', 'rerank', 'empty', 'empty_rerank'])
def test_pipeline_timings_include_all_steps_and_no_context(monkeypatch, mode):
    from types import SimpleNamespace
    clock = iter(range(20))
    fake_time = SimpleNamespace(monotonic=lambda: next(clock))
    monkeypatch.setattr(rag_app, "time", fake_time)
    monkeypatch.setattr(reranking, "time", fake_time)
    rows = [{'chunk_id':'c', 'chunktext':'text'}]
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(retrieval, 'retrieve_hits', Mock(return_value=[] if mode == 'empty' else rows))
    monkeypatch.setattr(reranking, 'rerank_results', Mock(return_value=[] if mode == 'empty_rerank' else rows))
    generate = Mock(return_value=('answer', {}))
    monkeypatch.setattr(generation, 'generate_answer', generate)
    enabled = mode in ('rerank', 'empty_rerank')
    body = rag_app.app.test_client().post('/process', json={'query':'q', 'top_k':1 if enabled else 0}).json
    assert body['timings'] == {'embedding_duration':1, 'retrieval_duration':1,
                               'pipeline_duration':7 if enabled else 5}
    if enabled:
        assert body['reranking']['duration'] == 1
    if mode in ('empty', 'empty_rerank'):
        assert body['metrics'] is None
        generate.assert_not_called()
    else:
        generate.assert_called_once()


def test_generation_duration_has_compatible_alias():
    metrics = generation_metrics({'total_duration':1500000000})
    assert metrics['generation_duration'] == metrics['total_duration'] == 1.5


@pytest.mark.parametrize('payload', [{}, {'query':'q'}, {'query':'q','results':[{}]},
    {'query':'q','results':'bad'}, {'query':'q','results':[{'chunk_id':'c','chunktext':None}]}])
@pytest.mark.parametrize('endpoint', ['rerank','generate'])
def test_evaluation_validates_before_dependencies(monkeypatch, payload, endpoint):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    response = rag_app.app.test_client().post('/evaluate/' + endpoint, json=payload)
    assert response.status_code == 400
    post.assert_not_called()


def test_evaluation_chain_is_reusable_and_isolated(monkeypatch):
    rows = [{'chunk_id':'a','chunktext':'first','distance':0.1},
            {'chunk_id':'b','chunktext':'second','distance':0.2}]
    embed = Mock(return_value=(np.array([1.0]), {'prompt_tokens':3}))
    search = Mock(return_value=rows)
    monkeypatch.setattr(embedding, 'generate_embedding', embed)
    monkeypatch.setattr(retrieval, 'retrieve_hits', search)
    response = Mock(status_code=200)
    response.json.return_value = {'ranked_documents':[{'original_index':1,'score':0.9}]}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)
    generate = Mock(return_value=('answer', {'generation_duration':1}))
    monkeypatch.setattr(generation, 'generate_answer', generate)
    client = rag_app.app.test_client()
    retrieved = client.post('/evaluate/retrieve', json={'query':'q','top_k':1,
        'answer_model':'model','system_prompt':'system','user_prompt':'{question}: {context}'}).json
    assert retrieved['results'] == rows
    assert 'diagnostics' not in retrieved
    assert 'vector' not in retrieved
    assert retrieved['metrics']['embedding']['prompt_tokens'] == 3
    post.assert_not_called()
    generate.assert_not_called()
    embed.reset_mock()
    search.reset_mock()
    ranked_response = client.post('/evaluate/rerank', json=retrieved['next_request'])
    assert ranked_response.status_code == 200
    ranked = ranked_response.json
    assert ranked['results'][0]['chunk_id'] == 'b'
    assert ranked['results'][0]['distance'] == 0.2
    assert ranked['results'][0]['rerank_score'] == 0.9
    assert ranked['results'][0]['original_index'] == 1
    embed.assert_not_called()
    search.assert_not_called()
    post.reset_mock()
    result = client.post('/evaluate/generate', json=ranked['next_request'])
    assert result.status_code == 200
    assert result.json['context'] == 'second'
    assert result.json['metrics']['generation_duration'] == 1
    generate.assert_called_once_with('second','q','model', system_prompt='system', user_prompt='{question}: {context}',
                                     post=rag_app.upstream_post)
    post.assert_not_called()
    embed.assert_not_called()
    search.assert_not_called()


@pytest.mark.parametrize('endpoint', ['rerank','generate'])
def test_empty_evaluation_does_not_call_provider(monkeypatch, endpoint):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    response = rag_app.app.test_client().post('/evaluate/' + endpoint, json={'query':'q','results':[]})
    assert response.status_code == 200
    assert response.json['status'] == 'no_context'
    post.assert_not_called()


@pytest.mark.parametrize("top_k, only_blank, expected_chunks, expected_context", [
    (1, False, ["b"], "second"),
    (0, False, ["a", "b"], "first\nsecond"),
    (1, True, [], ""),
])
def test_process_and_evaluation_share_business_steps(
    monkeypatch, top_k, only_blank, expected_chunks, expected_context,
):
    rows = [{"chunk_id": "blank", "chunktext": " \t", "distance": 0.1}]
    if not only_blank:
        rows.extend([
            {"chunk_id": "a", "chunktext": "first", "distance": 0.2},
            {"chunk_id": "b", "chunktext": "second", "distance": 0.3},
        ])

    def embed(query, with_metrics=False, *, post):
        vector = np.array([1.0])
        return (vector, {}) if with_metrics else vector

    monkeypatch.setattr(embedding, "generate_embedding", embed)
    found = Mock(status_code=200)
    found.json.return_value = rows
    ranked = Mock(status_code=200)
    ranked.json.return_value = {"ranked_documents": [{"original_index": 1, "score": 0.9}]}
    reranker = Mock(return_value=ranked)

    def post(url, payload, stage):
        if stage == "retrieval":
            return found
        assert stage == "reranking"
        return reranker(url, payload, stage)

    monkeypatch.setattr(rag_app, "upstream_post", post)
    generator = Mock(return_value=("answer", {"answer_tokens": 1}))
    monkeypatch.setattr(generation, "generate_answer", generator)

    steps = Mock()
    business_steps = [
        (embedding, "embed_query"), (retrieval, "retrieve_hits"),
        (reranking, "select_hits"), (generation, "generate_from_hits"),
    ]
    expected_steps = [name for _, name in business_steps]
    for module, name in business_steps:
        spy = Mock(wraps=getattr(module, name))
        steps.attach_mock(spy, name)
        monkeypatch.setattr(module, name, spy)

    client = rag_app.app.test_client()
    payload = {"query": "q", "top_k": top_k, "answer_model": "answer-model", "reranker": "rerank"}
    process = client.post("/process", json=payload)
    assert process.status_code == 200
    assert [call[0] for call in steps.mock_calls] == expected_steps
    steps.reset_mock()

    retrieved = client.post("/evaluate/retrieve", json=payload)
    assert retrieved.status_code == 200
    assert retrieved.json["results"] == rows
    selected = client.post("/evaluate/rerank", json=retrieved.json["next_request"])
    assert selected.status_code == 200
    generated = client.post("/evaluate/generate", json=selected.json["next_request"])
    assert generated.status_code == 200
    assert [call[0] for call in steps.mock_calls] == expected_steps

    for field in ("status", "response", "metrics", "chunks"):
        assert process.json[field] == generated.json[field]
    assert process.json["chunks"] == expected_chunks
    assert generated.json["context"] == expected_context
    assert process.json["selected_results"] == [
        {"chunk_id": row["chunk_id"], "chunktext": row["chunktext"]}
        for row in generated.json["results"]
    ]
    if top_k and not only_blank:
        assert [call.args[1]["documents"] for call in reranker.call_args_list] == [
            ["first", "second"], ["first", "second"],
        ]
        assert selected.json["results"][0]["original_index"] == 1
        assert selected.json["results"][0]["rerank_score"] == 0.9
    else:
        reranker.assert_not_called()
    if expected_chunks:
        assert [call.args for call in generator.call_args_list] == [
            (expected_context, "q", "answer-model"), (expected_context, "q", "answer-model"),
        ]
    else:
        assert process.json["status"] == "no_context"
        generator.assert_not_called()


def test_retrieve_accepts_cached_vector(monkeypatch):
    embed = Mock()
    search = Mock(return_value=[])
    monkeypatch.setattr(embedding, 'generate_embedding', embed)
    monkeypatch.setattr(retrieval, 'retrieve_hits', search)
    vector = [1.0] + [0.0] * 1023
    response = rag_app.app.test_client().post('/evaluate/retrieve', json={
        'query': 'q', 'vector': vector,
        'include_query_vector': True,
    })
    assert response.status_code == 200
    assert response.json['vector'] == vector
    assert 'vector' not in response.json['next_request']
    assert not search.call_args.kwargs['include_vector']
    assert response.json['embedding_model'] is None
    assert response.json['timings']['embedding_duration'] is None
    embed.assert_not_called()


def test_retrieval_diagnostics_preserve_hits_and_compare_reference(monkeypatch):
    embed = Mock(side_effect=[
        (np.array([1.] + [0.] * 1023), {}),
        np.array([-1.] + [0.] * 1023),
    ])
    rows = [
        {'chunk_id': 'a', 'chunktext': 'first', 'vector': [0.6, 0.8] + [0.] * 1022, 'distance': 0.4},
        {'chunk_id': 'b', 'chunktext': 'second', 'vector': [0.] * 1024, 'distance': 1.0},
    ]
    monkeypatch.setattr(embedding, 'generate_embedding', embed)
    search = Mock(return_value=rows)
    monkeypatch.setattr(retrieval, 'retrieve_hits', search)
    response = rag_app.app.test_client().post('/evaluate/retrieve', json={
        'query': 'question', 'metric': 'cosine', 'include_distances': True, 'reference_text': 'gold',
    })
    assert response.status_code == 200
    body = response.json
    assert search.call_args.kwargs['include_vector'] is True
    assert 'vector' not in body
    assert body['results'] == body['next_request']['results']
    assert body['results'] == [
        {'chunk_id': 'a', 'chunktext': 'first', 'distance': 0.4},
        {'chunk_id': 'b', 'chunktext': 'second', 'distance': 1.0},
    ]
    assert 'reference_text' not in body['next_request']
    assert body['diagnostics']['hits'][0] == {
        'chunk_id': 'a', 'distance': 0.4, 'cosine_similarity': pytest.approx(0.6),
        'euclidean_distance': pytest.approx((0.4**2 + 0.8**2)**0.5),
    }
    assert body['diagnostics']['hits'][1] == {
        'chunk_id': 'b', 'distance': 1.0, 'cosine_similarity': None, 'euclidean_distance': 1.0,
    }
    assert body['diagnostics']['reference'] == {'cosine_similarity': -1.0, 'euclidean_distance': 2.0}
    assert [entry.args for entry in embed.call_args_list] == [('question',), ('gold',)]


@pytest.mark.parametrize('fields, pointer', [
    ({'include_distances': 1}, '/include_distances'),
    ({'include_query_vector': 'true'}, '/include_query_vector'),
    ({'reference_text': ' '}, '/reference_text'),
    ({'reference_text': 'gold', 'vector': [1.] * 1024}, '/reference_text'),
])
def test_invalid_diagnostics_options_are_rejected_before_provider_access(monkeypatch, fields, pointer):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    result = rag_app.app.test_client().post('/evaluate/retrieve', json={'query': 'q', **fields})
    assert result.status_code == 400
    assert result.json['stage'] == 'validation'
    assert result.json['errors'][0]['pointer'] == pointer
    post.assert_not_called()


@pytest.mark.parametrize('stored_vector', [None, json.dumps([1.] + [0.] * 1023),
                                          [True] + [0.] * 1023, [1.0]])
def test_retrieval_diagnostics_reject_invalid_stored_vectors(monkeypatch, stored_vector):
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(return_value=(np.array([1.] + [0.] * 1023), {})))
    monkeypatch.setattr(retrieval, 'retrieve_hits', Mock(return_value=[
        {'chunk_id': 'c', 'chunktext': 'text', 'vector': stored_vector, 'distance': 0},
    ]))
    result = rag_app.app.test_client().post('/evaluate/retrieve', json={'query': 'q', 'include_distances': True})
    assert result.status_code == 502
    assert result.json['type'] == 'urn:rag:problem:upstream-invalid-response'
    assert result.json['stage'] == 'retrieval'


@pytest.mark.parametrize('template', ['{unknown}', '{context.__class__}', '{context!r}', '{'])
def test_evaluate_prompt_template_validation(monkeypatch, template):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    response = rag_app.app.test_client().post('/evaluate/generate', json={
        'query':'q','results':[], 'user_prompt':template})
    assert response.status_code == 400
    post.assert_not_called()


def test_rag_actuator_exposes_configured_models_without_provider_calls(monkeypatch):
    get = Mock(side_effect=AssertionError("health and info must not call providers"))
    monkeypatch.setattr(requests, "get", get)
    client = rag_app.app.test_client()

    response = client.get("/actuator/health")
    assert response.status_code == 200
    assert set(response.json) == {"status", "build"}
    assert response.json["status"] == "UP"
    assert client.get("/actuator/info").json == {
        "configuredModels": {
            "embedding": embedding.EMBEDDING_MODEL_NAME,
            "answer": generation.ANSWER_MODEL_NAME,
            "reranker": reranking.RERANKER_MODEL,
        },
    }
    assert client.get("/actuator/health/liveness").status_code == 404
    assert client.get("/actuator/health/readiness").status_code == 404
    get.assert_not_called()


def test_health_bounds_wait_and_shares_running_check(monkeypatch):
    from threading import Event

    from flask import Flask

    from rag_common.health import install_actuator

    release = Event()
    started = Event()
    finished = Event()

    def blocked_check():
        started.set()
        try:
            return release.wait(5)
        finally:
            finished.set()

    app = Flask(__name__)
    check = Mock(side_effect=blocked_check)
    monkeypatch.setenv("RAG_BUILD_TIME", "2026-11-27T14:20:00+00:00")
    install_actuator(app, check=check, info=dict, timeout=0.05)

    client = app.test_client()
    try:
        for _ in range(2):
            response = client.get("/actuator/health")
            assert response.status_code == 503
            assert response.json == {"status": "DOWN", "build": {"time": "2026-11-27T14:20:00+00:00"}}
            assert not finished.is_set()
        assert started.wait(1)
        check.assert_called_once()
    finally:
        release.set()
        assert finished.wait(1)
