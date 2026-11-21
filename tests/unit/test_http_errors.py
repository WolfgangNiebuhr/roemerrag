"""Cross-service RFC 9457 and validation regression tests."""
from unittest.mock import Mock
from uuid import UUID

import pytest
from flask import Flask
from rag import app as rag
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


@pytest.mark.parametrize('payload', [None, [], 123, {}, {'query': ' '}, {'query': 3},
    {'query': 'q', 'metric': []}, {'query': 'q', 'metric': 'bad'},
    *[{'query': 'q', 'num_results': x} for x in [True, 0, -1, 101, '2', 1.5]],
    {'query': 'q', 'filter': None}, {'query': 'q', 'filter': 'a', 'embedding_set_id': 'b'}])
def test_rag_validation_precedes_embedding(monkeypatch, payload):
    embed = Mock()
    monkeypatch.setattr(rag, 'generate_embedding', embed)
    response = rag.app.test_client().post('/process', json=payload)
    assert problem(response, 400, 'urn:rag:problem:invalid-request')['stage'] == 'validation'
    embed.assert_not_called()


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
    ('/chunk', 'delete', {}), ('/search', 'post', {'vector': [1]}),
    ('/search', 'post', {'vector': [1]*1024, 'num_results': 'abc'}),
    ('/search', 'post', {'vector': [1]*1024, 'metric': {}}),
    ('/search', 'post', {'vector': [float('nan')]*1024}),
    ('/search', 'post', {'vector': [True]*1024}),
    ('/search', 'post', {'vector': [0]*1024, 'metric': 'cosine'}),
    ('/chunks?embedding_set_id=', 'get', None), ('/find', 'get', None),
])
def test_vector_validation_precedes_pool_initialization(vector_module, monkeypatch, path, method, payload):
    initialize = Mock()
    monkeypatch.setattr(vector_module, 'ensure_db_pool', initialize)
    response = getattr(vector_module.app.test_client(), method)(path, json=payload)
    problem(response, 400, 'urn:rag:problem:invalid-request')
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
    monkeypatch.setattr(rag, 'generate_embedding', Mock(side_effect=RuntimeError('secret-password')))
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
    install(app, 'rag')
    @app.get('/auth')
    def auth():
        raise Unauthorized()
    problem(app.test_client().get('/auth'), 401, 'about:blank')
