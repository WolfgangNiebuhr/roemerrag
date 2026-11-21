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
    a = {"chunk_id": ids[0], "embedding": embedding_a, "vector": vector(1), "chunktext": "alpha"}
    b = {"chunk_id": ids[1], "embedding_set_id": embedding_b, "vector": vector(0.9), "chunktext": "beta"}
    for chunk in (a, b):
        assert request(vector_url, "/vectors", "POST", chunk, 201)["message"] == "Vector stored"

    assert request(vector_url, "/chunks?embedding=" + embedding_a)["chunks"] == 1
    assert request(vector_url, "/chunks?embedding_set_id=" + embedding_b)["chunks"] == 1
    assert request(vector_url, "/chunks/" + ids[0] + "?embedding=" + embedding_a)["chunktext"] == "alpha"
    a["chunktext"] = "alpha-updated"
    assert request(vector_url, "/vectors", "POST", a, 201)["message"] == "Vector stored"
    assert request(vector_url, "/chunks?embedding=" + embedding_a)["chunks"] == 1
    assert request(vector_url, "/chunks/" + ids[0] + "?embedding=" + embedding_a)["chunktext"] == "alpha-updated"

    query = {"vector": vector(0.92), "num_results": 1, "metric": "euclidean"}
    filtered = request(vector_url, "/search", "POST", {**query, "embedding_set_id": embedding_a})
    assert "metadata" not in filtered[0]
    assert filtered[0]["chunktext"] == "alpha-updated"
    assert filtered[0]["embedding_set_id"] == filtered[0]["embedding"] == embedding_a
    assert len(filtered) == 1 and filtered[0]["chunk_id"] == ids[0], filtered
    unfiltered = request(vector_url, "/search", "POST", query)
    assert len(unfiltered) == 1 and unfiltered[0]["chunk_id"] == ids[1], unfiltered
    cosine = request(vector_url, "/search", "POST", {**query, "metric": "cosine", "embedding": embedding_a})
    assert len(cosine) == 1 and cosine[0]["chunk_id"] == ids[0], cosine
    found = request(vector_url, "/find?query=%25alpha-updated%25")
    assert ids[0] in found["chunk_ids"], found
    assert request(vector_url, "/chunks/missing-" + test_id, expected=404)["type"] == "urn:rag:problem:not-found"

    for chunk_id, embedding in zip(ids, (embedding_a, embedding_b)):
        assert request(vector_url, "/chunk", "DELETE", {"chunk_id": chunk_id, "embedding": embedding})["message"] == "deleted"
    assert request(vector_url, "/chunks?embedding=" + embedding_a)["chunks"] == 0
    assert request(vector_url, "/chunks?embedding_set_id=" + embedding_b)["chunks"] == 0
