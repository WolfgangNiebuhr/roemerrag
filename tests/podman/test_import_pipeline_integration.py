import json
import math
import os
from pathlib import Path

import pytest

from Ingest import chunk, enrich, import3, pipeline
from Ingest.utils import gateway
from common import request


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
    assert request(vector_url, f"/chunks?embedding={embedding_set}")["chunks"] == 0
    try:
        assert pipeline.main(["--from", "enriched", "--input", str(enriched), "--config", str(config),
                              "--output-dir", str(output)]) == 0
        assert request(vector_url, f"/chunks?embedding={embedding_set}")["chunks"] == len(chunks)
        for row in pipeline.read_json(output / "embeddings.json")["chunks"]:
            stored = request(vector_url, f"/chunks/{row['chunk_id']}?embedding={embedding_set}")
            assert stored["chunktext"] == row["enrichment"] + "\n" + row["source_text"]
            hits = request(vector_url, "/search", "POST", {
                "vector": row["vector"], "embedding_set_id": embedding_set,
                "metric": "euclidean", "num_results": 1,
            })
            assert hits[0]["chunk_id"] == row["chunk_id"]
            assert hits[0]["distance"] == pytest.approx(0, abs=1e-5)
    finally:
        for row in chunks:
            request(vector_url, "/chunk", "DELETE", {
                "chunk_id": row["chunk_id"], "embedding_set_id": embedding_set,
            })


@pytest.mark.podman
@pytest.mark.ollama
def test_import3_compatible_matches_real_keywords_and_embeddings(
    tmp_path, monkeypatch, vector_url, test_id,
):
    host = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    monkeypatch.setenv("OLLAMA_HOST_URL", host)
    monkeypatch.setenv("IMPORT_VECTOR_URL", vector_url + "/vectors")
    monkeypatch.setattr(gateway, "OLLAMA_CHAT_URL", host + "/api/chat")
    monkeypatch.setattr(import3, "OLLAMA_URL", host + "/api/embeddings")
    monkeypatch.setattr(import3, "VECTOR_API_URL", vector_url + "/vectors")
    monkeypatch.setattr(import3, "MODEL_NAME", "snowflake-arctic-embed2")
    legacy_set = f"compatible-legacy-{test_id}"
    pipeline_set = f"compatible-pipeline-{test_id}"
    monkeypatch.setattr("Ingest.import3.EMBEDDING_SET_ID", legacy_set)

    sample = Path(pipeline.__file__).parent / "experiments" / "snowflake-arctic-embed-v2.json"
    settings = pipeline.read_json(sample)
    settings["embedding_set_id"] = pipeline_set
    config = tmp_path / sample.name
    pipeline.write_json(config, settings)
    source = Path(__file__).parent / "fixtures" / "early_rome.txt"
    legacy_chunks = import3.split_text_into_chunks(source, import3.CHUNK_SIZE, import3.OVERLAP)
    chunks = pipeline.make_chunks(source, pipeline.resolve_config(settings))["chunks"]
    assert [row["source_text"] for row in chunks] == legacy_chunks

    try:
        import3.process_file(source, start=1)
        output = tmp_path / "run"
        assert pipeline.main(["--file", str(source), "--config", str(config),
                              "--output-dir", str(output)]) == 0
        for embedding_set in (legacy_set, pipeline_set):
            assert request(vector_url, f"/chunks?embedding_set_id={embedding_set}")["chunks"] == len(chunks)

        for row in pipeline.read_json(output / "embeddings.json")["chunks"]:
            chunk_id = row["chunk_id"]
            old = request(vector_url, f"/chunks/{chunk_id}?embedding_set_id={legacy_set}")
            new = request(vector_url, f"/chunks/{chunk_id}?embedding_set_id={pipeline_set}")
            suffix = "\n" + row["source_text"]
            assert old["chunktext"].endswith(suffix)
            old_keywords = old["chunktext"][:-len(suffix)]
            assert new["chunktext"] == row["enrichment"] + suffix
            old_vector, new_vector = [json.loads(record["vector"]) for record in (old, new)]
            assert len(old_vector) == len(new_vector) == 1024
            assert math.hypot(*old_vector) == pytest.approx(1.0, abs=1e-6)
            assert math.hypot(*new_vector) == pytest.approx(1.0, abs=1e-6)
            max_delta = max(abs(a - b) for a, b in zip(old_vector, new_vector))
            print(f"{chunk_id}: keywords={row['enrichment']!r}, maximum vector difference={max_delta:.9g}")
            assert row["enrichment"] == old_keywords, f"{chunk_id}: max vector delta = {max_delta:.9g}"
            assert max_delta <= 1e-6, chunk_id
    finally:
        for embedding_set in (legacy_set, pipeline_set):
            for row in chunks:
                request(vector_url, "/chunk", "DELETE", {
                    "chunk_id": row["chunk_id"], "embedding_set_id": embedding_set,
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
