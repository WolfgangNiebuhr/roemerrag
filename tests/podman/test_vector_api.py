"""Integration tests for PostgreSQL/pgvector and the Vector API."""

from common import request
import pytest


def vector(first):
    return [first] + [0.0] * 1023


@pytest.mark.podman
def test_vector_api(vector_url, test_id):
    embedding_a = "podman-test-a-" + test_id
    embedding_b = "podman-test-b-" + test_id
    ids = ["podman-a-" + test_id, "podman-b-" + test_id]
    a = {"chunk_id": ids[0], "embedding": embedding_a, "vector": vector(1), "metadata": "alpha"}
    b = {"chunk_id": ids[1], "embedding": embedding_b, "vector": vector(0.9), "metadata": "beta"}
    for chunk in (a, b):
        assert request(vector_url, "/chunk", "POST", chunk, 201)["message"] == "Vector stored"

    assert request(vector_url, "/chunks?embedding=" + embedding_a)["count"] == 1
    assert request(vector_url, "/chunks?embedding=" + embedding_b)["count"] == 1
    assert request(vector_url, "/chunk/" + ids[0] + "?embedding=" + embedding_a)["metadata"] == "alpha"
    a["metadata"] = "alpha-updated"
    assert request(vector_url, "/chunk", "POST", a, 201)["message"] == "Vector stored"
    assert request(vector_url, "/chunks?embedding=" + embedding_a)["count"] == 1
    assert request(vector_url, "/chunk/" + ids[0] + "?embedding=" + embedding_a)["metadata"] == "alpha-updated"

    query = {"vector": vector(0.95), "num_results": 1, "metric": "euclidean"}
    filtered = request(vector_url, "/search", "POST", {**query, "embedding": embedding_a})
    assert len(filtered) == 1 and filtered[0]["chunk_id"] == ids[0], filtered
    unfiltered = request(vector_url, "/search", "POST", query)
    assert len(unfiltered) == 1 and unfiltered[0]["chunk_id"] == ids[1], unfiltered
    assert request(vector_url, "/chunk/missing-" + test_id, expected=404)["error"] == "nicht gefunden"

    for chunk_id, embedding in zip(ids, (embedding_a, embedding_b)):
        assert request(vector_url, "/chunk", "DELETE", {"chunk_id": chunk_id, "embedding": embedding})["message"] == "deleted"
    assert request(vector_url, "/chunks?embedding=" + embedding_a)["count"] == 0
    assert request(vector_url, "/chunks?embedding=" + embedding_b)["count"] == 0
