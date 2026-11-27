"""Real-model ingestion, retrieval and answer generation against an isolated stack."""

import math
from pathlib import Path

import pytest

from common import request
from Ingest import pipeline


@pytest.mark.podman
@pytest.mark.rag
@pytest.mark.ollama
def test_early_rome_question_end_to_end(
    vector_url, rag_url, test_id, e2e_ollama_url, tmp_path, monkeypatch,
):
    models = request(e2e_ollama_url, "/api/tags")["models"]
    assert "gemma3:4b" in {model["name"] for model in models}, "Run ollama pull gemma3:4b"
    variant = "rome-e2e-" + test_id
    corpus = Path(__file__).parent / "fixtures" / "early_rome.txt"
    monkeypatch.setenv("IMPORT_VECTOR_URL", vector_url + "/vectors")
    monkeypatch.setenv("OLLAMA_HOST_URL", e2e_ollama_url)
    config = tmp_path / "experiment.json"
    output = tmp_path / "run"
    pipeline.write_json(config, {
        "format_version": 1, "name": "early-rome-e2e", "embedding_set_id": variant,
        "chunking": {"strategy": "recursive", "parameters": {"size": 300, "overlap": 0}},
        "enrichment": {"strategy": "keywords", "parameters": {"model": "gemma3:4b"}},
        "embedding": {"model": "snowflake-arctic-embed2"},
    })

    try:
        assert pipeline.main(["--file", str(corpus), "--config", str(config),
                              "--output-dir", str(output)]) == 0
        chunks = pipeline.read_json(output / "embeddings.json")["chunks"]
        chunk_ids = [f"{corpus.stem}-{index}" for index in range(1, 4)]
        assert [row["chunk_id"] for row in chunks] == chunk_ids
        assert request(vector_url, f"/chunks?embedding_set_id={variant}")["chunks"] == len(chunks)
        for row in chunks:
            assert row["enrichment"].strip()
            stored = request(vector_url, f"/chunks/{row['chunk_id']}?embedding_set_id={variant}")
            assert stored["chunktext"] == row["enrichment"] + "\n" + row["source_text"]

        result = request(rag_url, "/process", "POST", {
            "query": "Wer beherrschte in der Frühzeit Roms das westliche Mittelmeer",
            "embedding_set_id": variant,
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
        request(vector_url, "/chunks", "DELETE", {
            "document_id": corpus.stem, "embedding_set_id": variant, "from": 1,
        })


@pytest.mark.podman
@pytest.mark.rag
@pytest.mark.reranker
@pytest.mark.ollama
def test_rag_reranking_through_api(vector_url, rag_url, test_id, e2e_ollama_url):
    variant = "rerank-api-" + test_id
    chunk = {"chunk_id":f"{variant}-1", "embedding_set_id":variant,
             "vector":[1.0] + [0.0] * 1023,
             "chunktext":"Karthago beherrschte das westliche Mittelmeer."}
    try:
        request(vector_url, '/vectors', 'POST', chunk, 201)
        result = request(rag_url, '/process', 'POST', {'query':'Wer beherrschte das westliche Mittelmeer?',
            'embedding_set_id':variant, 'top_k':1,
            'reranker':'cross-encoder/ms-marco-MiniLM-L6-v2', 'answer_model':'phi3:mini'}, timeout=1000)
        assert result['status'] == 'ok'
        assert result['chunks'] == [chunk["chunk_id"]]
        assert result['selected_results'] == result['retrieved_results']
        assert result['reranking']['model'] == 'cross-encoder/ms-marco-MiniLM-L6-v2'
        assert result['reranking']['duration'] >= 0
    finally:
        request(vector_url, '/chunks', 'DELETE', {
            'document_id': variant, 'embedding_set_id': variant, 'from': 1,
        })


@pytest.mark.podman
@pytest.mark.rag
@pytest.mark.reranker
@pytest.mark.ollama
def test_evaluation_endpoints_chain(vector_url, rag_url, test_id, e2e_ollama_url):
    variant = 'evaluation-' + test_id
    chunk = {'chunk_id':f'{variant}-1', 'embedding_set_id':variant,
             'vector':[1.0]+[0.0]*1023, 'chunktext':'Karthago beherrschte das westliche Mittelmeer.'}
    try:
        request(vector_url, '/vectors', 'POST', chunk, 201)
        retrieved = request(rag_url, '/evaluate/retrieve', 'POST', {
            'query':'Wer beherrschte das westliche Mittelmeer?', 'embedding_set_id':variant,
            'top_k':1, 'answer_model':'phi3:mini', 'include_distances':True,
            'reference_text':chunk['chunktext']}, timeout=600)
        assert retrieved['results'][0]['chunk_id'] == chunk['chunk_id']
        assert len(retrieved['vector']) == 1024
        assert 'distance' in retrieved['results'][0]
        assert retrieved['diagnostics']['hits'][0]['chunk_id'] == chunk['chunk_id']
        assert -1 <= retrieved['diagnostics']['reference']['cosine_similarity'] <= 1
        assert retrieved['diagnostics']['reference']['euclidean_distance'] >= 0
        assert retrieved['timings']['retrieval_duration'] >= 0
        ranked = request(rag_url, '/evaluate/rerank', 'POST', retrieved['next_request'], timeout=600)
        assert ranked['results'][0]['chunk_id'] == chunk['chunk_id']
        assert isinstance(ranked['results'][0]['rerank_score'], (int,float))
        generated = request(rag_url, '/evaluate/generate', 'POST', ranked['next_request'], timeout=1000)
        assert generated['status'] == 'ok'
        assert generated['response'].strip()
        assert generated['chunks'] == [chunk["chunk_id"]]
        assert generated['metrics']['generation_duration'] >= 0
        # The stored generation request can be replayed independently.
        assert generated['request'] == ranked['next_request']
    finally:
        request(vector_url, '/chunks', 'DELETE', {
            'document_id': variant, 'embedding_set_id': variant, 'from': 1,
        })
