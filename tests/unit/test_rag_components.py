"""Integration tests for the RAG API."""

import json
from unittest.mock import Mock, patch

import pytest

from rag import app as rag_app


@pytest.fixture(autouse=True)
def fixed_ollama_endpoint(monkeypatch):
    monkeypatch.setattr("rag.app.resolve_ollama_base_url", lambda: rag_app.OLLAMA_BASE_URL)


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

    with patch("requests.post", side_effect=[ollama_embedding, vector_response, ollama_answer]) as post:
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
    monkeypatch.setattr("requests.post", post)

    result = rag_app.generate_embedding("test query")

    assert result.tolist() == pytest.approx([0.6, 0.8])
    post.assert_called_once_with(
        rag_app.OLLAMA_EMBEDDING_URL,
        json={"model": rag_app.EMBEDDING_MODEL_NAME, "prompt": "test query"},
        timeout=(5, 300), headers={},
    )


@pytest.mark.parametrize("embedding", [None, [], [0.0, 0.0]])
def test_generate_embedding_rejects_missing_or_zero_vector(monkeypatch, embedding):
    response = Mock(status_code=200)
    response.json.return_value = {"embedding": embedding}
    monkeypatch.setattr("requests.post", Mock(return_value=response))

    with pytest.raises(rag_app.InvalidProviderResponse):
        rag_app.generate_embedding("test query")


def test_generate_embedding_rejects_http_error(monkeypatch):
    response = Mock(status_code=503, text="model unavailable")
    monkeypatch.setattr("requests.post", Mock(return_value=response))

    with pytest.raises(rag_app.ProviderUnavailable, match="Embedding is unavailable"):
        rag_app.generate_embedding("test query")


def test_search_vectors_sends_filters_and_rejects_non_list(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"results": []}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)

    with pytest.raises(rag_app.InvalidResults, match="Erwartet wurde eine Liste"):
        rag_app.search_vectors(rag_app.np.array([0.6, 0.8]), "embed-v1", "cosine", 3)

    post.assert_called_once_with(
        rag_app.VECTOR_API_URL,
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

    answer, metrics = rag_app.generate_answer("context", "question")

    assert answer == "answer"
    assert metrics == {
        "total_duration": 2.0, "generation_duration": 2.0, "load_duration": 0.5,
        "prompt_eval_duration": 0.25, "eval_duration": 1.0,
        "prompt_tokens": 12, "answer_tokens": 8, "answer_rate": 8.0,
    }
    assert post.call_args.args[0] == rag_app.OLLAMA_ANSWER_URL
    assert post.call_args.kwargs["json"]["prompt"] == "Kontext:\ncontext\n\nFrage: question"

    post.return_value = Mock(status_code=500, text="generation failed")
    with pytest.raises(rag_app.ProviderUnavailable, match="Generation is unavailable"):
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
    response = Mock(status_code=200)
    response.json.return_value = {"model": "model", "ranked_documents": [{"text": "second", "original_index": 1}]}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)
    rows = [{"chunk_id": "a", "chunktext": "first"}, {"chunk_id": "b", "chunktext": "second"}]
    assert rag_app.rerank_results("q", rows, "model", 1) == [{"chunk_id": "b", "chunktext": "second"}]
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
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    answer, metrics = rag_app.generate_answer('context', 'question')
    assert answer == 'answer'
    assert metrics['answer_rate'] is None
    assert metrics['total_duration'] is None

def test_invalid_retrieval_json_maps_to_problem(monkeypatch):
    response = Mock(status_code=200)
    response.json.side_effect = ValueError('private upstream body')
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    monkeypatch.setattr(rag_app, 'generate_embedding', Mock(return_value=rag_app.np.array([1])))
    result = rag_app.app.test_client().post('/process', json={'query': 'q'})
    assert result.status_code == 502
    assert result.mimetype == 'application/problem+json'
    assert result.json['type'] == 'urn:rag:problem:upstream-invalid-response'
    assert result.json['stage'] == 'retrieval'
    assert result.json['detail'] == 'Retrieval returned invalid JSON.'


def test_unavailable_retrieval_does_not_become_no_context(monkeypatch):
    monkeypatch.setattr(rag_app, 'generate_embedding', Mock(return_value=rag_app.np.array([1])))
    monkeypatch.setattr("requests.post", Mock(return_value=Mock(status_code=503)))
    generate = Mock()
    monkeypatch.setattr(rag_app, 'generate_answer', generate)
    response = rag_app.app.test_client().post('/process', json={'query': 'q'})
    assert response.status_code == 503
    assert response.json['type'] == 'urn:rag:problem:dependency-unavailable'
    assert response.json['stage'] == 'retrieval'
    generate.assert_not_called()


def test_metrics_zero_tokens_and_invalid_counts():
    metrics = rag_app.generation_metrics({'eval_duration': 1000000000, 'eval_count': 0, 'prompt_eval_count': 1.5})
    assert metrics['answer_rate'] == 0
    assert metrics['prompt_tokens'] is None


@pytest.mark.parametrize("mapping", [[{"original_index": True}], [{"original_index": 2}],
    [{"original_index": 0}, {"original_index": 0}], None])
def test_reranking_rejects_invalid_mapping(monkeypatch, mapping):
    response = Mock(status_code=200)
    response.json.return_value = {"ranked_documents": mapping}
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    with pytest.raises(rag_app.InvalidProviderResponse):
        rag_app.rerank_results("q", [{"chunk_id":"c", "chunktext":"text"}], "m", 1)


@pytest.mark.parametrize("top_k", [-1, True, "1", 1.5])
def test_reranking_validation_before_embedding(monkeypatch, top_k):
    embed = Mock()
    monkeypatch.setattr(rag_app, "generate_embedding", embed)
    assert rag_app.app.test_client().post('/process', json={'query':'q', 'top_k':top_k}).status_code == 400
    embed.assert_not_called()


@pytest.mark.parametrize("selected", [[], [{"chunk_id":"b", "chunktext":"second"}]])
def test_process_reranks_and_preserves_original_results(monkeypatch, selected):
    rows = [{"chunk_id":"a", "chunktext":"first"}, {"chunk_id":"b", "chunktext":"second"}]
    monkeypatch.setattr(rag_app, "generate_embedding", Mock(return_value=[1]))
    monkeypatch.setattr(rag_app, "search_vectors", Mock(return_value=rows))
    rerank = Mock(return_value=selected)
    monkeypatch.setattr(rag_app, "rerank_results", rerank)
    generate = Mock(return_value=("answer", {}))
    monkeypatch.setattr(rag_app, "generate_answer", generate)
    response = rag_app.app.test_client().post('/process', json={'query':'q', 'top_k':1,
                                            'reranker':'rerank', 'answer_model':'answer-model'})
    assert response.status_code == 200
    assert response.json['retrieved_results'] == rows
    assert response.json['selected_results'] == selected
    assert response.json['reranking']['model'] == 'rerank'
    rerank.assert_called_once_with('q', rows, 'rerank', 1)
    if selected:
        generate.assert_called_once_with('second', 'q', 'answer-model')
    else:
        assert response.json['status'] == 'no_context'
        generate.assert_not_called()


@pytest.mark.parametrize('stage,attempts', [('embedding',2), ('generation',1)])
def test_transport_retries_are_bounded(monkeypatch, stage, attempts):
    import requests
    post = Mock(side_effect=requests.Timeout())
    monkeypatch.setattr("requests.post", post)
    with pytest.raises(rag_app.ProviderUnavailable):
        rag_app.upstream_post('url', {}, stage)
    assert post.call_count == attempts


def test_expired_budget_prevents_upstream_request(monkeypatch):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    with rag_app.app.test_request_context('/process'):
        rag_app.g.deadline = 0
        with pytest.raises(rag_app.ProviderUnavailable):
            rag_app.upstream_post('url', {}, 'retrieval')
    post.assert_not_called()


def test_cli_and_http_equivalent_configuration(monkeypatch):
    import interact
    import sys
    rows = [{'chunk_id':'c', 'chunktext':'text'}]
    monkeypatch.setattr(rag_app, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(rag_app, 'search_vectors', Mock(return_value=rows))
    monkeypatch.setattr(rag_app, 'generate_answer', Mock(return_value=('answer', {})))
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


@pytest.mark.parametrize('embedding', [[float('nan')], [float('inf')], [True], [[1]], ['1']])
def test_embedding_invalid_provider_vectors(monkeypatch, embedding):
    response = Mock(status_code=200)
    response.json.return_value = {'embedding':embedding}
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    with pytest.raises(rag_app.InvalidProviderResponse, match='Embedding returned an invalid vector'):
        rag_app.generate_embedding('q')


@pytest.mark.parametrize('body', [{}, {'response':None}, {'response':3}, []])
def test_generation_rejects_invalid_provider_answer(monkeypatch, body):
    response = Mock(status_code=200)
    response.json.return_value = body
    monkeypatch.setattr("requests.post", Mock(return_value=response))
    with pytest.raises(rag_app.InvalidProviderResponse, match='Generation returned an invalid answer'):
        rag_app.generate_answer('text', 'q')


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


def test_analysis_uses_shared_provider_functions():
    import analyze
    assert analyze.generate_embedding is rag_app.generate_embedding
    assert analyze._search_vectors is rag_app.search_vectors
    assert analyze._generate_answer is rag_app.generate_answer


@pytest.mark.parametrize('value', [None, '', ' ', 42])
def test_invalid_answer_model_rejected_before_embedding(monkeypatch, value):
    embed = Mock()
    monkeypatch.setattr(rag_app, 'generate_embedding', embed)
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
    monkeypatch.setattr("rag.app.time", SimpleNamespace(monotonic=lambda: next(clock)))
    rows = [{'chunk_id':'c', 'chunktext':'text'}]
    monkeypatch.setattr(rag_app, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(rag_app, 'search_vectors', Mock(return_value=[] if mode == 'empty' else rows))
    monkeypatch.setattr(rag_app, 'rerank_results', Mock(return_value=[] if mode == 'empty_rerank' else rows))
    generate = Mock(return_value=('answer', {}))
    monkeypatch.setattr(rag_app, 'generate_answer', generate)
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
    metrics = rag_app.generation_metrics({'total_duration':1500000000})
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
    embed = Mock(return_value=(rag_app.np.array([1.0]), {'prompt_tokens':3}))
    search = Mock(return_value=rows)
    monkeypatch.setattr(rag_app, 'generate_embedding', embed)
    monkeypatch.setattr(rag_app, 'search_vectors', search)
    response = Mock(status_code=200)
    response.json.return_value = {'ranked_documents':[{'original_index':1,'score':0.9}]}
    post = Mock(return_value=response)
    monkeypatch.setattr("requests.post", post)
    generate = Mock(return_value=('answer', {'generation_duration':1}))
    monkeypatch.setattr(rag_app, 'generate_answer', generate)
    client = rag_app.app.test_client()
    retrieved = client.post('/evaluate/retrieve', json={'query':'q','top_k':1,
        'answer_model':'model','system_prompt':'system','user_prompt':'{question}: {context}'}).json
    assert retrieved['results'] == rows
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
    generate.assert_called_once_with('second','q','model', system_prompt='system', user_prompt='{question}: {context}')
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


@pytest.mark.parametrize('vector_as_string', [False, True])
def test_retrieve_accepts_cached_vector(monkeypatch, vector_as_string):
    embed = Mock()
    search = Mock(return_value=[])
    monkeypatch.setattr(rag_app, 'generate_embedding', embed)
    monkeypatch.setattr(rag_app, 'search_vectors', search)
    vector = [1.0] + [0.0] * 1023
    response = rag_app.app.test_client().post('/evaluate/retrieve', json={
        'query': 'q', 'vector': json.dumps(vector) if vector_as_string else vector,
    })
    assert response.status_code == 200
    assert response.json['vector'] == vector
    assert response.json['embedding_model'] is None
    assert response.json['timings']['embedding_duration'] is None
    embed.assert_not_called()


@pytest.mark.parametrize('template', ['{unknown}', '{context.__class__}', '{context!r}', '{'])
def test_evaluate_prompt_template_validation(monkeypatch, template):
    post = Mock()
    monkeypatch.setattr("requests.post", post)
    response = rag_app.app.test_client().post('/evaluate/generate', json={
        'query':'q','results':[], 'user_prompt':template})
    assert response.status_code == 400
    post.assert_not_called()
