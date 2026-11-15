"""Real-model ingestion, retrieval and answer generation against an isolated stack."""

import math
from pathlib import Path

import pytest

from common import request
from Ingest.chunking import split_text_into_chunks


@pytest.mark.podman
@pytest.mark.rag
@pytest.mark.ollama
def test_early_rome_question_end_to_end(vector_url, rag_url, test_id, e2e_ollama_url):
    # Match the models configured in rag/app.py, independently of the optional
    # standalone embedding test's environment overrides.
    model = "snowflake-arctic-embed2"
    variant = "rome-e2e-" + test_id
    corpus = Path(__file__).parent / "fixtures" / "early_rome.txt"
    chunks = split_text_into_chunks(str(corpus), size=300, overlap=0)
    assert len(chunks) == 3
    chunk_ids = [f"rome-e2e-{test_id}-{index}" for index in range(len(chunks))]

    try:
        for chunk_id, text in zip(chunk_ids, chunks):
            result = request(
                e2e_ollama_url, "/api/embeddings", "POST",
                {"model": model, "prompt": text}, timeout=300,
            )
            vector = result.get("embedding")
            assert isinstance(vector, list) and len(vector) == 1024, result
            assert all(isinstance(value, (int, float)) and math.isfinite(value) for value in vector)
            norm = math.sqrt(sum(value * value for value in vector))
            assert norm > 0
            request(vector_url, "/vectors", "POST", {
                "chunk_id": chunk_id,
                "embedding": variant,
                "vector": [value / norm for value in vector],
                "metadata": text,
            }, expected=201)

        assert request(vector_url, "/chunks?embedding=" + variant)["chunks"] == len(chunks)
        for chunk_id, text in zip(chunk_ids, chunks):
            stored = request(vector_url, f"/chunks/{chunk_id}?embedding={variant}")
            assert stored["metadata"] == text

        result = request(rag_url, "/process", "POST", {
            "query": "Wer beherrschte in der Frühzeit Roms das westliche Mittelmeer",
            "filter": variant,
            "metric": "euclidean",
            "num_results": 1,
        }, timeout=1000)

        assert result["chunks"] == [chunk_ids[0]], result
        answer = result["response"]
        assert isinstance(answer, str) and answer.strip(), result
        assert any(name in answer.casefold() for name in ("karthag", "carthag")), answer
        metrics = result["metrics"]
        for key in (
            "total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
            "prompt_tokens", "answer_tokens", "answer_rate",
        ):
            value = metrics[key]
            assert isinstance(value, (int, float)) and math.isfinite(value) and value >= 0, metrics
        assert metrics["prompt_tokens"] > 0, metrics
        assert metrics["answer_tokens"] > 0, metrics
    finally:
        for chunk_id in chunk_ids:
            request(vector_url, "/chunk", "DELETE", {"chunk_id": chunk_id, "embedding": variant})
