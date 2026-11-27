import json
import os
from pathlib import Path

import pytest

from Ingest import chunk, enrich, pipeline
from common import request


@pytest.mark.podman
def test_pipeline_keeps_committed_chunks_and_trims_after_suffix_import(
    vector_url, test_id, monkeypatch, tmp_path,
):
    set_id = f"suffix-{test_id}"
    monkeypatch.setenv("IMPORT_VECTOR_URL", vector_url + "/vectors")
    document = "rom_%"
    source = tmp_path / f"{document}.txt"
    source.write_text("abcdefghijklmnop", encoding="utf-8")
    config = tmp_path / "config.json"
    pipeline.write_json(config, {
        "format_version": 1, "name": "suffix", "embedding_set_id": set_id,
        "chunking": {"strategy": "recursive", "parameters": {"size": 4, "overlap": 0}},
        "embedding": {"model": "mock"},
    })
    real_request = pipeline.request_json
    vector = [1] + [0] * 1023
    interrupt_at = None

    def post(send, url, payload, timeout, status):
        if url.endswith("/api/embeddings"):
            if payload["prompt"] == interrupt_at:
                raise pipeline.requests.Timeout()
            return {"embedding": vector}
        return real_request(send, url, payload, timeout, status)

    def stored(chunk_id, target_set=set_id, expected=200):
        return request(vector_url, f"/chunks/{chunk_id.replace('%', '%25')}?embedding_set_id={target_set}",
                       expected=expected)

    def run(name, *args):
        return pipeline.main(["--config", str(config), "--output-dir", str(tmp_path / name), *args])

    monkeypatch.setattr(pipeline, "request_json", post)
    assert run("initial", "--file", str(source)) == 0
    for chunk_id, target_set in ((f"{document}-part-9", set_id), (f"{document}-4", set_id + "-other"),
                                 (f"{document}-100000000000000000000", set_id)):
        request(vector_url, "/vectors", "POST", {
            "chunk_id": chunk_id, "embedding_set_id": target_set, "chunktext": "separate", "vector": vector,
        }, expected=201)
    source.write_text("AAAABBBBCCCC", encoding="utf-8")
    interrupt_at = "CCCC"
    assert run("failed", "--file", str(source), "--start", "2") == 1
    assert stored(f"{document}-1")["chunktext"] == "abcd"
    assert stored(f"{document}-2")["chunktext"] == "BBBB"
    assert stored(f"{document}-3")["chunktext"] == "ijkl"
    assert stored(f"{document}-4")["chunktext"] == "mnop"

    interrupt_at = None
    assert run("resumed", "--file", str(source), "--start", "3") == 0
    assert stored(f"{document}-1")["chunktext"] == "abcd"
    assert stored(f"{document}-2")["chunktext"] == "BBBB"
    assert stored(f"{document}-3")["chunktext"] == "CCCC"
    stored(f"{document}-4", expected=404)
    stored(f"{document}-100000000000000000000", expected=404)
    assert stored(f"{document}-part-9")["chunktext"] == "separate"
    assert stored(f"{document}-4", set_id + "-other")["chunktext"] == "separate"


@pytest.mark.podman
@pytest.mark.ollama
def test_pipeline_with_real_keywords_and_embeddings(tmp_path, monkeypatch, vector_url, test_id):
    host = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434")
    monkeypatch.setenv("OLLAMA_HOST_URL", host)
    monkeypatch.setenv("IMPORT_VECTOR_URL", vector_url + "/vectors")
    embedding_set = f"pipeline-{test_id}"
    source = Path(__file__).parent / "fixtures" / "early_rome.txt"
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "format_version": 1, "name": "integration", "embedding_set_id": embedding_set,
        "chunking": {"strategy": "recursive"},
        "enrichment": {"strategy": "keywords"},
        "embedding": {"model": "snowflake-arctic-embed2"},
    }), encoding="utf-8")
    output = tmp_path / "run"
    chunks = pipeline.make_chunks(source, pipeline.resolve_config(pipeline.read_json(config)))["chunks"]
    chunk_artifact = tmp_path / "chunks.json"
    enriched = tmp_path / "enriched.json"
    chunk.main(["--file", str(source), "--config", str(config), "--output", str(chunk_artifact)])
    assert enrich.main(["--input", str(chunk_artifact), "--config", str(config),
                        "--output", str(enriched)]) == 0
    for row in pipeline.read_json(enriched)["chunks"]:
        assert row["enrichment_metrics"]["total_duration"] > 0
    assert request(vector_url, f"/chunks?embedding_set_id={embedding_set}")["chunks"] == 0
    try:
        assert pipeline.main(["--from", "enriched", "--input", str(enriched), "--config", str(config),
                              "--output-dir", str(output)]) == 0
        assert request(vector_url, f"/chunks?embedding_set_id={embedding_set}")["chunks"] == len(chunks)
        for row in pipeline.read_json(output / "embeddings.json")["chunks"]:
            stored = request(vector_url, f"/chunks/{row['chunk_id']}?embedding_set_id={embedding_set}")
            assert stored["chunktext"] == row["enrichment"] + "\n" + row["source_text"]
            hits = request(vector_url, "/search", "POST", {
                "vector": row["vector"], "embedding_set_id": embedding_set,
                "metric": "euclidean", "num_results": 1,
            })
            assert hits[0]["chunk_id"] == row["chunk_id"]
            assert hits[0]["distance"] == pytest.approx(0, abs=1e-5)
    finally:
        request(vector_url, "/chunks", "DELETE", {
            "document_id": source.stem, "embedding_set_id": embedding_set, "from": 1,
        })


@pytest.mark.podman
@pytest.mark.ollama
def test_experiments_store_and_retrieve_under_configured_set_ids(
    tmp_path, monkeypatch, vector_url,
):
    monkeypatch.setenv("IMPORT_VECTOR_URL", vector_url + "/vectors")
    experiments = Path(pipeline.__file__).parent / "experiments"
    source = Path(__file__).parent / "fixtures" / "early_rome.txt"
    expected_sets = ("test-recursive-1000", "snowflake-arctic-embed-v1", "snowflake-arctic-embed-v2")
    imported = {}
    # The session-scoped fixture owns the database and removes its volume afterward.
    for set_id in expected_sets:
        config = experiments / f"{set_id}.json"
        output = tmp_path / set_id
        assert pipeline.main(["--file", str(source), "--config", str(config),
                              "--output-dir", str(output)]) == 0
        imported[set_id] = pipeline.read_json(output / "embeddings.json")["chunks"]

    for set_id, chunks in imported.items():
        assert request(vector_url, f"/chunks?embedding_set_id={set_id}")["chunks"] == len(chunks)
        for row in chunks:
            chunk_id = row["chunk_id"]
            stored = request(vector_url, f"/chunks/{chunk_id}?embedding_set_id={set_id}")
            assert stored["embedding_set_id"] == set_id
            assert stored["chunktext"] == row["chunktext"]
            hits = request(vector_url, "/search", "POST", {
                "vector": row["vector"], "embedding_set_id": set_id,
                "metric": "euclidean", "num_results": 1,
            })
            assert hits[0]["chunk_id"] == chunk_id
            assert hits[0]["embedding_set_id"] == set_id
            assert hits[0]["distance"] == pytest.approx(0, abs=1e-5)

    for old_id in ("recursive-1000-v1", "import-py-compatible-v1", "import3-compatible-v1"):
        assert request(vector_url, f"/chunks?embedding_set_id={old_id}")["chunks"] == 0
