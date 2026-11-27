"""Real import3 ingestion against host Ollama and the isolated Vector API."""

import os
from pathlib import Path
from Ingest import import3 as importer
from Ingest.utils import gateway

import pytest
import requests

from common import request


@pytest.mark.podman
@pytest.mark.ollama
def test_import3_with_real_keywords_and_embeddings(monkeypatch, vector_url, test_id):
    host = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    response = requests.get(host + "/api/tags", timeout=10)
    response.raise_for_status()
    available = {model["name"] for model in response.json()["models"]}
    required = {"snowflake-arctic-embed2:latest", "gemma3:4b"}
    assert not required - available, f"Run ollama pull for: {sorted(required - available)}"

    # Redirect configuration only: chunking, keywords, gateway, normalization and
    # storage all execute their production code with real HTTP requests.
    monkeypatch.setattr(importer, "OLLAMA_URL", host + "/api/embeddings")
    monkeypatch.setattr(importer, "VECTOR_API_URL", vector_url + "/vectors")
    monkeypatch.setattr(gateway, "OLLAMA_CHAT_URL", host + "/api/chat")
    variant = "import3-" + test_id
    monkeypatch.setattr("Ingest.import3.EMBEDDING_SET_ID", importer.MODEL_NAME + "-" + variant)
    embedding = importer.MODEL_NAME + "-" + variant
    corpus = Path(__file__).parent / "fixtures" / "early_rome.txt"
    chunks = importer.split_text_into_chunks(str(corpus), importer.CHUNK_SIZE, importer.OVERLAP)
    ids = [f"{corpus.stem}-{index + 1}" for index in range(len(chunks))]
    try:
        importer.process_file(str(corpus), start=1)
        assert request(vector_url, "/chunks?embedding_set_id=" + embedding)["chunks"] == len(chunks)
        for chunk_id, chunk in zip(ids, chunks):
            stored = request(vector_url, f"/chunks/{chunk_id}?embedding_set_id={embedding}")
            chunktext = stored["chunktext"]
            assert chunktext.endswith("\n" + chunk)
            keywords = chunktext[:-(len(chunk) + 1)]
            assert keywords.strip(), "Keyword model returned no enrichment"
            # Re-embedding the persisted text must find the same stored vector.
            vector = importer.generate_embedding(chunktext)
            assert len(vector) == 1024
            assert float(vector @ vector) == pytest.approx(1.0)
            hits = request(vector_url, "/search", "POST", {
                "vector": vector.tolist(), "embedding_set_id": embedding,
                "metric": "euclidean", "num_results": 1,
            })
            assert hits[0]["chunk_id"] == chunk_id
            assert hits[0]["distance"] == pytest.approx(0, abs=1e-5)
    finally:
        request(vector_url, "/chunks", "DELETE", {
            "document_id": corpus.stem, "embedding_set_id": embedding, "from": 1,
        })
