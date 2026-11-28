"""Cross-service RFC 9457 and validation regression tests."""
import json
from unittest.mock import Mock
from uuid import UUID

import pytest
from flask import Flask
from rag import app as rag, embedding, generation, reranking, retrieval
from reranker import app as reranker
from rag_common.http_errors import install
from test_vector_api_unit import vector_module, database


def problem(response, status, kind):
    assert response.status_code == status
    assert response.mimetype == 'application/problem+json'
    body = response.json
    assert body['status'] == status
    assert body['type'] == kind
    assert 'error' not in body
    assert isinstance(body['title'], str) and body['title']
    assert isinstance(body['detail'], str)
    UUID(body['instance'].removeprefix('urn:uuid:'))
    assert body['request_id'] == response.headers['X-Request-ID']
    assert type(body['retryable']) is bool
    return body


@pytest.mark.parametrize("path", ["/vectors", "/search", "/evaluate/retrieve"])
def test_vector_list_strings_are_rejected_before_io(vector_module, monkeypatch, path):
    initialize = Mock()
    embed = Mock()
    search = Mock()
    monkeypatch.setattr(vector_module, "ensure_db_pool", initialize)
    monkeypatch.setattr(embedding, "generate_embedding", embed)
    monkeypatch.setattr(retrieval, "retrieve_hits", search)
    service = rag if path == "/evaluate/retrieve" else vector_module
    response = service.app.test_client().post(path, json={
        "query": "q", "embedding_set_id": "set", "chunk_id": "c", "chunktext": "Text",
        "vector": json.dumps([1.0] + [0.0] * 1023),
    })
    body = problem(response, 400, "urn:rag:problem:invalid-request")
    assert body["errors"] == [{"pointer": "/vector", "detail": body["detail"]}]
    initialize.assert_not_called()
    embed.assert_not_called()
    search.assert_not_called()


@pytest.mark.parametrize('payload', [None, [], 123, {}, {'query': ' '}, {'query': 3},
    {'query': 'q', 'metric': []}, {'query': 'q', 'metric': 'bad'},
    *[{'query': 'q', 'num_results': x} for x in [True, 0, -1, 101, '2', 1.5]],
    {'query': 'q', 'embedding_set_id': None}, {'query': 'q', 'embedding_set_id': ' '}])
def test_rag_validation_precedes_embedding(monkeypatch, payload):
    embed = Mock()
    monkeypatch.setattr(embedding, 'generate_embedding', embed)
    response = rag.app.test_client().post('/process', json=payload)
    assert problem(response, 400, 'urn:rag:problem:invalid-request')['stage'] == 'validation'
    embed.assert_not_called()


@pytest.mark.parametrize('path', ['/process', '/evaluate/retrieve', '/evaluate/rerank', '/evaluate/generate'])
@pytest.mark.parametrize('fields', [{'filter': 'old'}, {'filter': 'old', 'embedding_set_id': 'old'}])
def test_rag_rejects_removed_set_alias_before_provider_call(monkeypatch, path, fields):
    embed = Mock()
    search = Mock()
    rerank = Mock()
    generate = Mock()
    monkeypatch.setattr(embedding, 'generate_embedding', embed)
    monkeypatch.setattr(retrieval, 'retrieve_hits', search)
    monkeypatch.setattr(reranking, 'rerank_results', rerank)
    monkeypatch.setattr(generation, 'generate_answer', generate)
    response = rag.app.test_client().post(path, json={
        'query': 'q', 'results': [{'chunk_id': 'c', 'chunktext': 'Text'}], **fields,
    })
    body = problem(response, 400, 'urn:rag:problem:invalid-request')
    assert body['errors'] == [{'pointer': '/filter', 'detail': body['detail']}]
    embed.assert_not_called()
    search.assert_not_called()
    rerank.assert_not_called()
    generate.assert_not_called()


@pytest.mark.parametrize('payload', [123, {}, {'query': ' ', 'documents': []},
    {'query': 'q', 'documents': None}, {'query': 'q', 'documents': [' ']},
    {'query': 'q', 'documents': [False]}, {'query': 'q', 'documents': [], 'model': None}])
def test_reranker_validation_precedes_loading(monkeypatch, payload):
    load = Mock()
    monkeypatch.setattr(reranker, 'load_model', load)
    problem(reranker.app.test_client().post('/rerank', json=payload), 400, 'urn:rag:problem:invalid-request')
    load.assert_not_called()


@pytest.mark.parametrize('path,method,payload', [
    ('/vectors', 'post', {}), ('/vectors', 'post', {'chunk_id': 4}),
    ('/chunks', 'delete', {}), ('/search', 'post', {'embedding_set_id': 'set-a', 'vector': [1]}),
    ('/search', 'post', {'embedding_set_id': 'set-a', 'vector': [1]*1024, 'num_results': 'abc'}),
    ('/search', 'post', {'embedding_set_id': 'set-a', 'vector': [1]*1024, 'metric': {}}),
    ('/search', 'post', {'embedding_set_id': 'set-a', 'vector': [float('nan')]*1024}),
    ('/search', 'post', {'embedding_set_id': 'set-a', 'vector': [True]*1024}),
    ('/search', 'post', {'embedding_set_id': 'set-a', 'vector': [0]*1024, 'metric': 'cosine'}),
    ('/chunks?embedding_set_id=', 'get', None), ('/chunks/c?embedding_set_id=', 'get', None),
    ('/find', 'get', None),
    ('/chunks/c?embedding_set_id=set&include_vector=1', 'get', None),
    ('/search', 'post', {'embedding_set_id': 'set', 'vector': [1] * 1024, 'include_vector': 'true'}),
])
def test_vector_validation_precedes_pool_initialization(vector_module, monkeypatch, path, method, payload):
    initialize = Mock()
    monkeypatch.setitem(vars(vector_module), "ensure_db_pool", initialize)
    response = getattr(vector_module.app.test_client(), method)(path, json=payload)
    assert problem(response, 400, 'urn:rag:problem:invalid-request')['stage'] == 'validation'
    initialize.assert_not_called()


@pytest.mark.parametrize("path,method,payload", [
    ("/chunks/c", "get", None),
    ("/find?query=rome", "get", None),
    ("/search", "post", {"vector": [1] * 1024}),
])
def test_vector_reads_require_set_before_database(vector_module, monkeypatch, path, method, payload):
    initialize = Mock()
    monkeypatch.setattr(vector_module, "ensure_db_pool", initialize)
    response = getattr(vector_module.app.test_client(), method)(path, json=payload)
    body = problem(response, 400, "urn:rag:problem:invalid-request")
    location = {"parameter": "embedding_set_id"} if method == "get" else {"pointer": "/embedding_set_id"}
    assert body["errors"] == [{**location, "detail": body["detail"]}]
    initialize.assert_not_called()


@pytest.mark.parametrize('path', ['/chunks?embedding_set_id=', '/chunks/c?embedding_set_id=', '/find'])
def test_invalid_vector_head_does_not_initialize_pool(vector_module, monkeypatch, path):
    initialize = Mock()
    monkeypatch.setattr(vector_module, 'ensure_db_pool', initialize)

    response = vector_module.app.test_client().head(path)

    assert response.status_code == 400
    assert response.mimetype == 'application/problem+json'
    assert response.data == b''
    initialize.assert_not_called()


def test_invalid_requests_keep_field_locations_and_correlation(vector_module, monkeypatch):
    initialize = Mock()
    monkeypatch.setattr(vector_module, 'ensure_db_pool', initialize)
    client = vector_module.app.test_client()
    headers = {'X-Request-ID': 'vector-validation'}
    cases = [
        (client.get('/find', headers=headers), 'parameter', 'query'),
        (client.post('/search', json={'metric': 'invalid', 'embedding_set_id': 'set-a'},
                     headers=headers), 'pointer', '/metric'),
    ]
    for response, location, field in cases:
        body = problem(response, 400, 'urn:rag:problem:invalid-request')
        assert body['stage'] == 'validation'
        assert body['request_id'] == 'vector-validation'
        assert body['errors'] == [{location: field, 'detail': body['detail']}]
    initialize.assert_not_called()


@pytest.mark.parametrize("fields", [
    {}, {"from": 0}, {"from": True}, {"from": 1.0}, {"from": 2, "to": 1},
    {"from": 1, "to": None}, {"from": 1, "to": "2"}, {"from": 1, "to": True},
    {"from": 1, "document_id": ""}, {"from": 1, "chunk_id": "rom-1"},
])
def test_delete_range_validation_precedes_pool_initialization(vector_module, monkeypatch, fields):
    initialize = Mock()
    monkeypatch.setattr(vector_module, "ensure_db_pool", initialize)
    response = vector_module.app.test_client().delete("/chunks", json={
        "embedding_set_id": "test", "document_id": "rom", **fields,
    })
    problem(response, 400, "urn:rag:problem:invalid-request")
    initialize.assert_not_called()


@pytest.mark.parametrize('module,path', [(rag, '/process'), (reranker, '/rerank')])
def test_malformed_json_and_http_errors(module, path):
    client = module.app.test_client()
    problem(client.post(path, data='{', content_type='application/json'), 400, 'urn:rag:problem:invalid-request')
    problem(client.get('/unknown'), 404, 'about:blank')
    response = client.get(path)
    problem(response, 405, 'about:blank')
    assert 'POST' in response.headers['Allow']


def test_internal_error_is_safe_and_correlated(monkeypatch, caplog):
    monkeypatch.setattr(embedding, 'generate_embedding', Mock(side_effect=RuntimeError('secret-password')))
    client = rag.app.test_client()
    first = client.post('/process', json={'query': 'q'}, headers={'X-Request-ID': 'test-123'})
    second = client.post('/process', json={'query': 'q'}, headers={'X-Request-ID': 'bad value'})
    body = problem(first, 500, 'urn:rag:problem:internal-error')
    assert body['request_id'] == 'test-123'
    assert 'secret-password' not in first.text
    assert 'secret-password' in caplog.text
    assert second.json['request_id'] != 'bad value'
    assert second.json['instance'] != body['instance']


def test_generic_http_handler_preserves_required_headers():
    from werkzeug.exceptions import Unauthorized
    app = Flask(__name__)
    install(app, default_stage='processing')
    @app.get('/auth')
    def auth():
        raise Unauthorized()
    problem(app.test_client().get('/auth'), 401, 'about:blank')
