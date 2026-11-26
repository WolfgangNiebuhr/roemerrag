"""Container integration test for the RAG HTTP endpoint."""

import pytest

from common import request


@pytest.mark.rag
@pytest.mark.podman
def test_rag_api_rejects_empty_query(rag_url):
    missing = request(rag_url, "/process", "POST", {"query": ""}, 400)
    assert missing["type"] == "urn:rag:problem:invalid-request"


@pytest.mark.rag
@pytest.mark.podman
def test_retrieval_diagnostics_for_stored_vector(rag_url, vector_url, test_id):
    variant = "diagnostics-" + test_id
    chunk_id = f"{variant}-1"
    try:
        request(vector_url, "/vectors", "POST", {
            "chunk_id": chunk_id, "embedding_set_id": variant, "chunktext": "Kontext",
            "vector": [0., 1.] + [0.] * 1022,
        }, 201)
        result = request(rag_url, "/evaluate/retrieve", "POST", {
            "query": "q", "embedding_set_id": variant, "metric": "cosine",
            "vector": [1., 0.] + [0.] * 1022, "include_distances": True,
        })
        assert result["diagnostics"]["hits"] == [{
            "chunk_id": chunk_id, "distance": 1.0, "cosine_similarity": 0.0,
            "euclidean_distance": pytest.approx(2**0.5),
        }]
        assert result["next_request"]["results"] == result["results"]
    finally:
        request(vector_url, "/chunks", "DELETE", {"document_id": variant, "embedding_set_id": variant, "from": 1})
