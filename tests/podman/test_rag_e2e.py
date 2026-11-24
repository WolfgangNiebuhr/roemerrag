"""Real-model ingestion, retrieval and answer generation against an isolated stack."""

import math
from pathlib import Path

import pytest

from common import request
from Ingest.utils.chunking import split_text_into_chunks


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
                "chunktext": text,
            }, expected=201)

        assert request(vector_url, "/chunks?embedding=" + variant)["chunks"] == len(chunks)
        for chunk_id, text in zip(chunk_ids, chunks):
            stored = request(vector_url, f"/chunks/{chunk_id}?embedding={variant}")
            assert stored["chunktext"] == text

        result = request(rag_url, "/process", "POST", {
            "query": "Wer beherrschte in der Frühzeit Roms das westliche Mittelmeer",
            "filter": variant,
            "metric": "euclidean",
            "num_results": 1,
            "top_k": 0,
            "answer_model": "phi3:mini",
        }, timeout=1000)

        assert result["chunks"] == [chunk_ids[0]], result
        assert result["retrieved_results"] == result["selected_results"]
        assert result["reranking"] is None
        answer = result["response"]
        assert isinstance(answer, str) and answer.strip(), result
        assert any(name in answer.casefold() for name in ("karthag", "carthag")), answer
        for key in ("embedding_duration", "retrieval_duration", "pipeline_duration"):
            assert result["timings"][key] >= 0
        assert result["timings"]["pipeline_duration"] >= sum(result["timings"][key] for key in ("embedding_duration", "retrieval_duration"))
        metrics = result["metrics"]
        assert metrics["generation_duration"] == metrics["total_duration"]
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


@pytest.mark.podman
@pytest.mark.rag
@pytest.mark.reranker
@pytest.mark.ollama
def test_rag_reranking_through_api(vector_url, rag_url, test_id, e2e_ollama_url):
    variant = "rerank-api-" + test_id
    chunk = {"chunk_id":variant, "embedding_set_id":variant,
             "vector":[1.0] + [0.0] * 1023,
             "chunktext":"Karthago beherrschte das westliche Mittelmeer."}
    try:
        request(vector_url, '/vectors', 'POST', chunk, 201)
        result = request(rag_url, '/process', 'POST', {'query':'Wer beherrschte das westliche Mittelmeer?',
            'embedding_set_id':variant, 'top_k':1,
            'reranker':'cross-encoder/ms-marco-MiniLM-L6-v2', 'answer_model':'phi3:mini'}, timeout=1000)
        assert result['status'] == 'ok'
        assert result['chunks'] == [variant]
        assert result['selected_results'] == result['retrieved_results']
        assert result['reranking']['model'] == 'cross-encoder/ms-marco-MiniLM-L6-v2'
        assert result['reranking']['duration'] >= 0
    finally:
        request(vector_url, '/chunk', 'DELETE', chunk)


@pytest.mark.podman
@pytest.mark.rag
@pytest.mark.reranker
@pytest.mark.ollama
def test_evaluation_endpoints_chain(vector_url, rag_url, test_id, e2e_ollama_url):
    variant = 'evaluation-' + test_id
    chunk = {'chunk_id':variant, 'embedding_set_id':variant,
             'vector':[1.0]+[0.0]*1023, 'chunktext':'Karthago beherrschte das westliche Mittelmeer.'}
    try:
        request(vector_url, '/vectors', 'POST', chunk, 201)
        retrieved = request(rag_url, '/evaluate/retrieve', 'POST', {
            'query':'Wer beherrschte das westliche Mittelmeer?', 'embedding_set_id':variant,
            'top_k':1, 'answer_model':'phi3:mini'}, timeout=600)
        assert retrieved['results'][0]['chunk_id'] == variant
        assert len(retrieved['vector']) == 1024
        assert 'distance' in retrieved['results'][0]
        assert retrieved['timings']['retrieval_duration'] >= 0
        ranked = request(rag_url, '/evaluate/rerank', 'POST', retrieved['next_request'], timeout=600)
        assert ranked['results'][0]['chunk_id'] == variant
        assert isinstance(ranked['results'][0]['rerank_score'], (int,float))
        generated = request(rag_url, '/evaluate/generate', 'POST', ranked['next_request'], timeout=1000)
        assert generated['status'] == 'ok'
        assert generated['response'].strip()
        assert generated['chunks'] == [variant]
        assert generated['metrics']['generation_duration'] >= 0
        # The stored generation request can be replayed independently.
        assert generated['request'] == ranked['next_request']
    finally:
        request(vector_url, '/chunk', 'DELETE', chunk)
