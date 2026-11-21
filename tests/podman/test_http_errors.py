"""HTTP contract tests against the actual TS-03 API images."""
import json
import urllib.error
import urllib.request

import pytest


@pytest.mark.podman
@pytest.mark.rag
@pytest.mark.reranker
def test_problem_contract_across_services(vector_url, rag_url, reranker_url):
    cases = [
        (vector_url, '/vectors', 'POST', {} ,400),
        (vector_url, '/search', 'POST', {'vector': [1]*1024, 'num_results': 'abc'}, 400),
        (rag_url, '/process', 'POST', {'query': 'q', 'metric': 'invalid'}, 400),
        (reranker_url, '/rerank', 'POST', 123, 400),
        (rag_url, '/process', 'GET', None, 405),
        (vector_url, '/unknown', 'GET', None, 404),
    ]
    for base, path, method, payload, expected in cases:
        request = urllib.request.Request(base + path, method=method,
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'X-Request-ID': 'ts03-integration'})
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=10)
        with caught.value as response:
            body = json.load(response)
            assert response.code == body['status'] == expected
            assert response.headers.get_content_type() == 'application/problem+json'
            assert body['request_id'] == response.headers['X-Request-ID'] == 'ts03-integration'
            assert body['instance'].startswith('urn:uuid:')
            assert body['type'] == ('urn:rag:problem:invalid-request' if expected == 400 else 'about:blank')
            assert 'error' not in body
            if expected == 405:
                assert 'POST' in response.headers['Allow']
