import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain.text_splitter import RecursiveCharacterTextSplitter

from Ingest import chunk, import3, pipeline


@pytest.fixture
def experiment(tmp_path):
    source = tmp_path / "rom.band1.txt"
    source.write_bytes(b"abcdefghijklmnopqrstuvwxyz")
    config = tmp_path / "config.json"
    config.write_text(json.dumps({
        "format_version": 1, "name": "test", "embedding_set_id": "test-v1",
        "chunking": {"strategy": "recursive", "parameters": {"size": 10, "overlap": 2}},
        "embedding": {"model": "embedding-model"},
    }), encoding="utf-8")
    return source, config


def test_chunk_only_and_reuse_with_no_keywords(experiment, tmp_path, monkeypatch):
    source, config = experiment
    monkeypatch.delenv("IMPORT_VECTOR_URL", raising=False)
    artifact = tmp_path / "chunks.json"
    calls = []

    def post(url, payload, timeout, status):
        calls.append((url, payload))
        if status == 200:
            return {"embedding": [3, 4] + [0] * 1022}
        return {"message": "Vector stored"}

    monkeypatch.setattr(pipeline, "post", post)
    chunk.main(["--file", str(source), "--config", str(config), "--output", str(artifact)])
    assert calls == []
    data = pipeline.read_json(artifact)
    assert data["chunking"]["parameters"]["separators"] == list(pipeline.DEFAULT_SEPARATORS)
    assert data["source_version"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert [row["source_text"] for row in data["chunks"]] == [
        "abcdefghij", "ijklmnopqr", "qrstuvwxyz",
    ]
    source.unlink()
    # Version 1 artifacts written before separators were configurable remain usable.
    del data["chunking"]["parameters"]["separators"]
    pipeline.write_json(artifact, data)
    output = tmp_path / "run"
    assert pipeline.main(["--from", "chunks", "--input", str(artifact),
                          "--config", str(config), "--output-dir", str(output)]) == 0
    assert [payload["prompt"] for _, payload in calls[:3]] == [
        row["source_text"] for row in data["chunks"]
    ]
    for index, (url, payload) in enumerate(calls[3:], 1):
        assert url == "http://127.0.0.1:5500/vectors"
        assert payload["chunk_id"] == f"rom.band1-{index}"
        assert payload["chunktext"] == calls[index - 1][1]["prompt"]
        assert payload["embedding_set_id"] == "test-v1"
        assert payload["vector"][:2] == [0.6, 0.8]
    assert pipeline.read_json(output / "run.json")["stored"] == 3


def test_keywords_and_reuse_after_failed_embedding(experiment, tmp_path, monkeypatch):
    source, config = experiment
    data = pipeline.read_json(config)
    data["enrichment"] = {"strategy": "keywords", "parameters": {"model": "keyword-model"}}
    config.write_text(json.dumps(data), encoding="utf-8")
    calls = []

    def post(url, payload, timeout, status):
        calls.append((url, payload))
        if url.endswith("/api/chat"):
            assert payload["model"] == "keyword-model"
            return {"message": {"content": "Rom"}}
        return {"embedding": [float("inf")] + [0] * 1023}

    monkeypatch.setattr(pipeline, "post", post)
    failed = tmp_path / "failed"
    assert pipeline.main(["--file", str(source), "--config", str(config),
                          "--output-dir", str(failed)]) == 1
    assert len(calls) == 4
    assert calls[-1][1]["prompt"] == "Rom\nabcdefghij"
    report = pipeline.read_json(failed / "run.json")
    assert report["stored"] == 0
    assert report["error"]["stage"] == "embedding"
    assert report["error"]["chunk_id"] == "rom.band1-1"
    assert not (failed / "embeddings.json").exists()

    def retry(url, payload, timeout, status):
        assert not url.endswith("/api/chat")
        if status == 200:
            assert payload["prompt"].startswith("Rom\n")
            return {"embedding": [1] + [0] * 1023}
        assert payload["chunktext"].startswith("Rom\n")
        return {"message": "Vector stored"}

    monkeypatch.setattr(pipeline, "post", retry)
    assert pipeline.main(["--from", "enriched", "--input", str(failed / "enriched.json"),
                          "--config", str(config), "--output-dir", str(tmp_path / "retry")]) == 0


@pytest.mark.parametrize("override", [
    {"chunking": {"strategy": "recursive", "parameters": {"size": 10, "overlap": 10}}},
    {"chunking": {"strategy": "recursive", "parameters": {"separators": ["", " "]}}},
    {"chunking": {"strategy": "recursive", "parameters": {"separators": []}}},
    {"chunking": {"strategy": "recursive", "parameters": {"separators": [42, ""]}}},
    {"enrichment": {"strategy": "keywords", "parameters": {"prompt": "unknown"}}},
    {"embedding": {"model": "x", "dimensions": 768}},
])
def test_invalid_configuration_stops_before_import(experiment, tmp_path, override):
    source, config = experiment
    config.write_text(json.dumps({**pipeline.read_json(config), **override}), encoding="utf-8")
    output = tmp_path / "run"
    with pytest.raises(SystemExit) as error:
        pipeline.main(["--file", str(source), "--config", str(config), "--output-dir", str(output)])
    assert error.value.code == 2
    assert not output.exists()


def test_snowflake_arctic_embed_v1_matches_langchain_chunk_boundaries(tmp_path):
    ingest = Path(pipeline.__file__).parent
    config = pipeline.resolve_config(
        pipeline.read_json(ingest / "experiments" / "snowflake-arctic-embed-v1.json"))
    source = tmp_path / "roman.txt"
    source.write_bytes((
        ("Rom. Karthago und die italischen Gemeinschaften. " * 15 + "\r\n") * 4
        + "\r\n" + "Mittelmeer " * 250 + "x" * 1200
    ).encode("utf-8"))
    actual = [row["source_text"] for row in pipeline.make_chunks(source, config)["chunks"]]
    assert len(actual) > 1
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    assert actual == splitter.split_text(source.read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="Incompatible artifact chunking"):
        pipeline.validate_artifact(
            pipeline.make_chunks(source, config), "chunks",
            pipeline.resolve_config(pipeline.read_json(ingest / "experiments" / "test-recursive-1000.json")),
        )


def test_storage_failure_reports_only_confirmed_writes(experiment, tmp_path, monkeypatch):
    source, config = experiment
    writes = []

    def post(url, payload, timeout, status):
        if status == 200:
            return {"embedding": [1] + [0] * 1023}
        writes.append(payload["chunk_id"])
        if len(writes) == 2:
            raise pipeline.requests.Timeout("private provider details")
        return {"message": "Vector stored"}

    monkeypatch.setattr(pipeline, "post", post)
    output = tmp_path / "run"
    assert pipeline.main(["--file", str(source), "--config", str(config),
                          "--output-dir", str(output)]) == 1
    assert writes == ["rom.band1-1", "rom.band1-2"]
    report = pipeline.read_json(output / "run.json")
    assert report["expected"] == 3
    assert report["stored"] == 1
    assert report["error"] == {"stage": "storage", "chunk_id": "rom.band1-2", "type": "Timeout"}
    assert "embeddings.json" in report["artifacts"]
    assert "private provider details" not in (output / "run.json").read_text(encoding="utf-8")


def test_import3_experiment_matches_legacy_pipeline(tmp_path, monkeypatch):
    config_path = Path(pipeline.__file__).parent / "experiments" / "snowflake-arctic-embed-v2.json"
    config = pipeline.resolve_config(pipeline.read_json(config_path))
    source = tmp_path / "rom.band1.txt"
    source.write_text("x" * 1200 + "\n\nKarthago. Rom.", encoding="utf-8")
    legacy_chunks = import3.split_text_into_chunks(source, import3.CHUNK_SIZE, import3.OVERLAP)
    assert len(legacy_chunks) == 2
    assert len(legacy_chunks[0]) == 1200
    calls = []

    def post(url, *, json, timeout, **kwargs):
        endpoint = url.rsplit("/", 1)[-1]
        calls.append((endpoint, json))
        status, body = {
            "chat": (200, {"message": {"content": "Rom, Karthago"}}),
            "embeddings": (200, {"embedding": [1.0, 2.0, 3.0] + [0.0] * 1021}),
            "vectors": (201, {"message": "Vector stored"}),
        }[endpoint]
        return SimpleNamespace(status_code=status, text="", json=lambda: body)

    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr(import3, "MODEL_NAME", "snowflake-arctic-embed2")
    import3.process_file(source, start=1)
    legacy_calls = calls.copy()
    calls.clear()
    output = tmp_path / "run"
    assert pipeline.main(["--file", str(source), "--config", str(config_path),
                          "--output-dir", str(output)]) == 0

    assert [row["source_text"] for row in pipeline.read_json(output / "chunks.json")["chunks"]] == legacy_chunks
    for endpoint in ("chat", "embeddings", "vectors"):
        legacy = [body for name, body in legacy_calls if name == endpoint]
        current = [body for name, body in calls if name == endpoint]
        assert len(legacy) == len(current) == len(legacy_chunks)
        for old, new in zip(legacy, current):
            if endpoint == "vectors":
                assert new["embedding_set_id"] == config["embedding_set_id"]
                assert new.pop("vector") == pytest.approx(old.pop("vector"), abs=1e-15, rel=1e-14)
                old["embedding_set_id"] = config["embedding_set_id"]
            assert new == old
