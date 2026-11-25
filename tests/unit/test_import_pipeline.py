import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain.text_splitter import RecursiveCharacterTextSplitter

from Ingest import chunk, enrich, import3, pipeline


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

    def post(send, url, payload, timeout, status):
        calls.append((url, payload))
        if send is pipeline.requests.delete and url.endswith("/chunks"):
            return {"deleted": 0}
        if status == 200:
            return {"embedding": [3, 4] + [0] * 1022}
        return {"message": "Vector stored"}

    monkeypatch.setattr(pipeline, "request_json", post)
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
    embedding_calls = [payload for url, payload in calls if url.endswith("/api/embeddings")]
    writes = [payload for url, payload in calls if url.endswith("/vectors")]
    assert [payload["prompt"] for payload in embedding_calls] == [
        row["source_text"] for row in data["chunks"]
    ]
    for index, payload in enumerate(writes, 1):
        assert payload["chunk_id"] == f"rom.band1-{index}"
        assert payload["chunktext"] == embedding_calls[index - 1]["prompt"]
        assert payload["embedding_set_id"] == "test-v1"
        assert payload["vector"][:2] == [0.6, 0.8]
    assert len(writes) == 3
    assert not (output / "run.json").exists()


def test_keywords_are_recomputed_for_unstored_chunk(experiment, tmp_path, monkeypatch, capsys):
    source, config = experiment
    data = pipeline.read_json(config)
    data["enrichment"] = {"strategy": "keywords", "parameters": {"model": "keyword-model"}}
    config.write_text(json.dumps(data), encoding="utf-8")
    calls = []

    def post(send, url, payload, timeout, status):
        calls.append((url, payload))
        if url.endswith("/api/chat"):
            assert payload["model"] == "keyword-model"
            return {"message": {"content": "Rom"}}
        return {"embedding": [float("inf")] + [0] * 1023}

    monkeypatch.setattr(pipeline, "request_json", post)
    failed = tmp_path / "failed"
    assert pipeline.main(["--file", str(source), "--config", str(config),
                          "--output-dir", str(failed)]) == 1
    assert len(calls) == 2
    assert calls[-1][1]["prompt"] == "Rom\nabcdefghij"
    assert "embedding at chunk 1 (ValueError). Continue with --start 1." in capsys.readouterr().err
    assert not (failed / "embeddings.json").exists()

    def retry(send, url, payload, timeout, status):
        if url.endswith("/api/chat"):
            return {"message": {"content": "Rom"}}
        if send is pipeline.requests.delete and url.endswith("/chunks"):
            return {"deleted": 0}
        if status == 200:
            assert payload["prompt"].startswith("Rom\n")
            return {"embedding": [1] + [0] * 1023}
        assert payload["chunktext"].startswith("Rom\n")
        return {"message": "Vector stored"}

    monkeypatch.setattr(pipeline, "request_json", retry)
    assert pipeline.main(["--file", str(source), "--start", "1",
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


@pytest.mark.parametrize("failure", ["embedding", "storage", "cleanup"])
def test_start_hint_retries_first_unconfirmed_chunk(experiment, tmp_path, monkeypatch, failure, capsys):
    source, config = experiment
    embedded = []
    writes = []
    trims = []
    interrupted = True

    def post(send, url, payload, timeout, status):
        if send is pipeline.requests.delete and url.endswith("/chunks"):
            trims.append(payload)
            if interrupted and failure == "cleanup":
                raise pipeline.requests.Timeout()
            return {"deleted": 2}
        if url.endswith("/api/embeddings"):
            embedded.append(payload["prompt"])
            if interrupted and failure == "embedding" and len(embedded) == 2:
                raise pipeline.requests.Timeout()
            return {"embedding": [1] + [0] * 1023}
        writes.append(payload["chunk_id"])
        if interrupted and failure == "storage" and len(writes) == 2:
            raise pipeline.requests.Timeout("private provider details")
        return {"message": "Vector stored"}

    monkeypatch.setattr(pipeline, "request_json", post)
    output = tmp_path / "first"
    assert pipeline.main(["--file", str(source), "--config", str(config),
                          "--output-dir", str(output)]) == 1
    start = 4 if failure == "cleanup" else 2
    stderr = capsys.readouterr().err
    assert f"{failure} at chunk {start} (Timeout). Continue with --start {start}." in stderr
    assert bool(trims) == (failure == "cleanup")
    assert "private provider details" not in stderr
    assert not (output / "run.json").exists()

    embedded.clear()
    writes.clear()
    interrupted = False
    retry = tmp_path / "retry"
    assert pipeline.main(["--file", str(source), "--start", str(start), "--config", str(config),
                          "--output-dir", str(retry)]) == 0
    assert writes == ([] if failure == "cleanup" else ["rom.band1-2", "rom.band1-3"])
    assert embedded == ([] if failure == "cleanup" else ["ijklmnopqr", "qrstuvwxyz"])
    assert trims[-1] == {"embedding_set_id": "test-v1", "document_id": "rom.band1", "from": 4}


@pytest.mark.parametrize("start", ["0", "5"])
def test_invalid_start(experiment, tmp_path, start):
    source, config = experiment
    with pytest.raises(SystemExit) as error:
        pipeline.main(["--file", str(source), "--start", start, "--config", str(config),
                       "--output-dir", str(tmp_path / "invalid")])
    assert error.value.code == 2


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
            "chunks": (200, {"deleted": 0}),
        }[endpoint]
        return SimpleNamespace(status_code=status, text="", json=lambda: body)

    monkeypatch.setattr("requests.post", post)
    monkeypatch.setattr("requests.delete", post)
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


def test_enrichment_variants_share_chunks_and_can_be_imported(experiment, tmp_path, monkeypatch):
    source, config = experiment
    original = pipeline.read_json(config)
    chunks = tmp_path / "chunks.json"
    chunk.main(["--file", str(source), "--config", str(config), "--output", str(chunks)])
    calls = []

    def chat_only(send, url, payload, timeout, status):
        assert url.endswith("/api/chat")
        calls.append(payload)
        return {"message": {"content": "Rom, Karthago"}, "total_duration": 200_000_000,
                "prompt_eval_count": 12, "eval_count": 5}

    monkeypatch.setattr(pipeline, "request_json", chat_only)
    artifacts = []
    for model, prompt in (("model-a", "keywords-v1"), ("model-b", "keywords-v1"),
                          ("model-b", "keywords-v2")):
        strategy = {"strategy": "keywords", "parameters": {"model": model, "prompt": prompt}}
        pipeline.write_json(config, {**original, "enrichment": strategy, "embedding": None})
        output = tmp_path / f"{model}-{prompt}" / "enriched.json"
        assert enrich.main(["--input", str(chunks), "--config", str(config),
                            "--output", str(output)]) == 0
        artifact = pipeline.read_json(output)
        artifacts.append(artifact)
        assert artifact["enrichment"] == strategy
        for row in artifact["chunks"]:
            assert row["chunktext"] == "Rom, Karthago\n" + row["source_text"]
            metrics = row["enrichment_metrics"]
            assert metrics["request_seconds"] >= 0
            assert metrics["total_duration"] == 200_000_000
            assert metrics["prompt_eval_count"] == 12
            assert metrics["eval_count"] == 5
            assert metrics["load_duration"] is None
    chunks_count = len(pipeline.read_json(chunks)["chunks"])
    assert len(calls) == 3 * chunks_count
    assert calls[0]["model"] != calls[chunks_count]["model"]
    assert calls[0]["messages"] == calls[chunks_count]["messages"]
    assert calls[chunks_count]["messages"] != calls[2 * chunks_count]["messages"]
    assert [a["source_version"] for a in artifacts] == [pipeline.read_json(chunks)["source_version"]] * 3

    pipeline.write_json(config, {**original, "enrichment": artifacts[-1]["enrichment"]})

    def embed_and_store(send, url, payload, timeout, status):
        if send is pipeline.requests.delete and url.endswith("/chunks"):
            return {"deleted": 0}
        if status == 200:
            assert payload["prompt"].startswith("Rom, Karthago\n")
            return {"embedding": [1.0] + [0.0] * 1023}
        assert payload["chunktext"].startswith("Rom, Karthago\n")
        return {"message": "Vector stored"}

    monkeypatch.setattr(pipeline, "request_json", embed_and_store)
    assert pipeline.main(["--from", "enriched", "--input", str(output), "--config", str(config),
                          "--output-dir", str(tmp_path / "import")]) == 0


def test_custom_prompt_and_failed_enrichment_leave_no_artifact(experiment, tmp_path, monkeypatch):
    source, config = experiment
    settings = pipeline.read_json(config)
    settings["enrichment"] = {"strategy": "keywords", "parameters": {
        "prompt": "trial-1", "system_prompt": "Extrahiere nur Ortsnamen.",
    }}
    pipeline.write_json(config, settings)
    chunks = tmp_path / "chunks.json"
    chunk.main(["--file", str(source), "--config", str(config), "--output", str(chunks)])
    output = tmp_path / "enriched.json"

    def empty_chat(send, url, payload, timeout, status):
        assert url.endswith("/api/chat")
        assert payload["messages"] == [
            {"role": "system", "content": "Extrahiere nur Ortsnamen."},
            {"role": "user", "content": "abcdefghij"},
        ]
        return {"message": {"content": ""}}

    monkeypatch.setattr(pipeline, "request_json", empty_chat)
    assert enrich.main(["--input", str(chunks), "--config", str(config),
                        "--output", str(output)]) == 1
    assert not output.exists()
