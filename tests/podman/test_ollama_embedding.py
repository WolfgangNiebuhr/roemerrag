"""Integration tests for the host Ollama embedding API."""

import json
import math
import urllib.error
import urllib.request

import pytest


@pytest.mark.ollama
def test_ollama_embedding(ollama_url, ollama_model):
    url = ollama_url
    payload = {
        "model": ollama_model,
        "prompt": "Was ist die Hauptstadt von Frankreich?",
    }

    def get_embedding():
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise AssertionError(f"Ollama returned HTTP {exc.code}: {exc.read()!r}") from exc
        vector = result.get("embedding")
        assert isinstance(vector, list) and vector, "Ollama response has no non-empty embedding list"
        assert all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector), (
            "embedding must contain only finite numeric values"
        )
        return vector

    first = get_embedding()
    second = get_embedding()
    assert len(first) == len(second), "embedding dimension changed between identical requests"
    assert first == second, "identical prompts returned different embeddings"
    print(f"Ollama embedding dimension: {len(first)}")
