"""Container integration test for the RAG HTTP endpoint."""

import pytest

from common import request


@pytest.mark.rag
@pytest.mark.podman
def test_rag_api_rejects_empty_query(rag_url):
    missing = request(rag_url, "/process", "POST", {"query": ""}, 400)
    assert missing["type"] == "urn:rag:problem:invalid-request"
