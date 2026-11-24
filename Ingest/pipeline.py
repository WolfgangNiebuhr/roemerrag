"""Run a configured import through the existing Ollama and Vector APIs."""

import argparse
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import monotonic
from uuid import uuid4

import requests

from .utils.chunking import split_recursive
from .utils.keywords import keyword_messages


DEFAULT_SEPARATORS = ("\n\n", ".\n", ". ", "")


def recursive(text, *, size=1000, overlap=150, separators=DEFAULT_SEPARATORS):
    return split_recursive(text, size, overlap, separators=list(separators))


def post(url, payload, timeout, status):
    response = requests.post(url, json=payload, timeout=timeout, allow_redirects=False)
    if response.status_code != status:
        raise ValueError(f"HTTP {response.status_code}")
    return response.json()


def keywords(text, *, model, prompt, ollama, timeout):
    require(prompt == "keywords-v1", "Unknown keyword prompt")
    system, query, _ = keyword_messages(text)
    data = post(ollama + "/api/chat", {
        "model": model, "stream": False, "options": {"temperature": 0.0},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": query}],
    }, timeout, 200)
    message = data.get("message") if isinstance(data, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Missing keywords in Ollama response")
    return content


def no_enrichment(text, *, ollama, timeout):
    return ""


CHUNKERS = {"recursive": recursive}
ENRICHERS = {"none": no_enrichment, "keywords": keywords}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, allowed):
    require(isinstance(value, dict) and value.keys() <= set(allowed.split()),
            f"Expected an object with fields from: {allowed}")
    return value


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def resolve_config(config, *, chunk_only=False):
    fields(config, "format_version name embedding_set_id chunking enrichment embedding")
    require(type(config.get("format_version")) is int and config["format_version"] == 1,
            "Expected format_version 1")
    chunking = fields(config.get("chunking"), "strategy parameters")
    require(chunking.get("strategy") == "recursive", "Unknown chunking strategy")
    params = fields(chunking.get("parameters", {}), "size overlap separators")
    size, overlap = params.get("size", 1000), params.get("overlap", 150)
    require(type(size) is int and type(overlap) is int and 0 <= overlap < size,
            "Expected integer size > 0 and 0 <= overlap < size")
    separators = params.get("separators", list(DEFAULT_SEPARATORS))
    require(isinstance(separators, list) and bool(separators)
            and all(isinstance(separator, str) for separator in separators)
            and "" not in separators[:-1],
            "Expected a nonempty list of literal separators with an optional final empty string")
    result = {"format_version": 1, "chunking": {
        "strategy": "recursive",
        "parameters": {"size": size, "overlap": overlap, "separators": separators},
    }}
    if chunk_only:
        return result
    require(nonempty(config.get("name")) and nonempty(config.get("embedding_set_id")),
            "Expected a name and embedding_set_id")
    enrichment = fields(config.get("enrichment", {"strategy": "none"}), "strategy parameters")
    strategy = enrichment.get("strategy")
    require(isinstance(strategy, str) and strategy in ENRICHERS, "Unknown enrichment strategy")
    params = enrichment.get("parameters", {})
    if strategy == "keywords":
        fields(params, "model prompt")
        params = {"model": "gemma3:4b", "prompt": "keywords-v1", **params}
        require(nonempty(params["model"]) and params["prompt"] == "keywords-v1",
                "Expected a keyword model and prompt keywords-v1")
    else:
        fields(params, "")
    embedding = fields(config.get("embedding"), "model normalize dimensions")
    embedding = {"normalize": True, "dimensions": 1024, **embedding}
    require(nonempty(embedding.get("model")) and type(embedding["normalize"]) is bool
            and type(embedding["dimensions"]) is int and embedding["dimensions"] == 1024,
            "Expected an embedding model, boolean normalize and 1024 dimensions")
    return {**result, "name": config["name"], "embedding_set_id": config["embedding_set_id"],
            "enrichment": {"strategy": strategy, "parameters": params}, "embedding": embedding}


def make_chunks(path, config):
    raw = path.read_bytes()
    source = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    strategy = config["chunking"]
    chunks = CHUNKERS[strategy["strategy"]](source, **strategy["parameters"])
    require(nonempty(path.stem) and bool(chunks), "Source has no document ID or text chunks")
    return {
        "format_version": 1, "stage": "chunks", "document_id": path.stem,
        "source": str(path.resolve()), "source_version": hashlib.sha256(raw).hexdigest(),
        "chunking": strategy,
        "chunks": [{"chunk_id": f"{path.stem}-{index}", "source_text": chunk}
                   for index, chunk in enumerate(chunks, 1)],
    }


def chunktext(row):
    return row["enrichment"] + "\n" + row["source_text"] if row["enrichment"] else row["source_text"]


def validate_artifact(data, stage, config):
    require(isinstance(data, dict) and type(data.get("format_version")) is int
            and data["format_version"] == 1 and data.get("stage") == stage,
            "Incompatible chunk artifact")
    artifact_config = resolve_config(
        {"format_version": 1, "chunking": data.get("chunking")}, chunk_only=True)
    require(artifact_config["chunking"] == config["chunking"], "Incompatible artifact chunking")
    data["chunking"] = artifact_config["chunking"]
    digest = data.get("source_version")
    require(nonempty(data.get("document_id")) and nonempty(data.get("source"))
            and isinstance(digest, str) and len(digest) == 64
            and all(c in "0123456789abcdef" for c in digest), "Invalid artifact source")
    chunks = data.get("chunks")
    require(isinstance(chunks, list) and bool(chunks), "Artifact has no chunks")
    if stage == "enriched":
        require(data.get("enrichment") == config["enrichment"], "Incompatible enrichment")
    for index, row in enumerate(chunks, 1):
        require(isinstance(row, dict) and row.get("chunk_id") == f"{data['document_id']}-{index}"
                and nonempty(row.get("source_text")), "Invalid artifact chunk")
        if stage == "enriched":
            enrichment = row.get("enrichment")
            require(isinstance(enrichment, str)
                    and (nonempty(enrichment) if config["enrichment"]["strategy"] == "keywords"
                         else enrichment == "")
                    and row.get("chunktext") == chunktext(row), "Invalid artifact enrichment")


def embed(text, config, ollama, timeout):
    data = post(ollama + "/api/embeddings",
                {"model": config["model"], "prompt": text}, timeout, 200)
    vector = data.get("embedding") if isinstance(data, dict) else None
    require(isinstance(vector, list) and len(vector) == config["dimensions"]
            and all(type(x) in (int, float) and math.isfinite(x) for x in vector),
            "Invalid embedding values or dimensions")
    norm = math.hypot(*vector)
    require(math.isfinite(norm) and norm > 0, "Invalid embedding norm")
    return [x / norm for x in vector] if config["normalize"] else vector


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temp:
        temporary = Path(temp.name)
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n",
                             encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run(args, config, artifact):
    ollama = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    vector_url = os.getenv("IMPORT_VECTOR_URL", "http://127.0.0.1:5500/vectors")
    connect = float(os.getenv("IMPORT_CONNECT_TIMEOUT", "5"))
    timeouts = {
        "enrichment": (connect, float(os.getenv("IMPORT_KEYWORD_TIMEOUT", "120"))),
        "embedding": (connect, float(os.getenv("IMPORT_EMBED_TIMEOUT", "300"))),
        "storage": (connect, float(os.getenv("IMPORT_STORE_TIMEOUT", "60"))),
    }
    require(all(math.isfinite(value) and value > 0 for pair in timeouts.values() for value in pair),
            "HTTP timeouts must be positive and finite")
    output = args.output_dir
    output.mkdir(parents=True, exist_ok=False)
    started = stage_started = monotonic()
    phase, chunk_id = "chunks", None
    report = {
        "format_version": 1, "run_id": uuid4().hex, "config": config,
        "input": str((args.file or args.input).resolve()), "input_stage": args.from_stage,
        "expected": None, "stored": 0, "stage_seconds": {}, "artifacts": [], "error": None,
    }
    try:
        if artifact is None:
            artifact = make_chunks(args.file, config)
        report["expected"] = len(artifact["chunks"])
        if artifact["stage"] == "chunks":
            write_json(output / "chunks.json", artifact)
            report["artifacts"].append("chunks.json")
            report["stage_seconds"][phase] = monotonic() - stage_started
            phase, stage_started = "enrichment", monotonic()
            strategy = config["enrichment"]
            rows = []
            for source in artifact["chunks"]:
                chunk_id = source["chunk_id"]
                enrichment = ENRICHERS[strategy["strategy"]](
                    source["source_text"], **strategy["parameters"],
                    ollama=ollama, timeout=timeouts[phase],
                )
                row = {**source, "enrichment": enrichment}
                rows.append({**row, "chunktext": chunktext(row)})
            artifact = {**artifact, "stage": "enriched", "enrichment": strategy, "chunks": rows}
            write_json(output / "enriched.json", artifact)
            report["artifacts"].append("enriched.json")
            report["stage_seconds"][phase] = monotonic() - stage_started
        phase, stage_started = "embedding", monotonic()
        rows = []
        for row in artifact["chunks"]:
            chunk_id = row["chunk_id"]
            vector = embed(row["chunktext"], config["embedding"], ollama, timeouts[phase])
            rows.append({**row, "vector": vector})
        write_json(output / "embeddings.json",
                   {**artifact, "stage": "embeddings", "embedding": config["embedding"], "chunks": rows})
        report["artifacts"].append("embeddings.json")
        report["stage_seconds"][phase] = monotonic() - stage_started
        phase, stage_started = "storage", monotonic()
        for row in rows:
            chunk_id = row["chunk_id"]
            data = post(vector_url, {
                "chunk_id": chunk_id, "embedding_set_id": config["embedding_set_id"],
                "chunktext": row["chunktext"], "vector": row["vector"],
            }, timeouts[phase], 201)
            require(isinstance(data, dict) and data.get("message") == "Vector stored",
                    "Invalid Vector API acknowledgement")
            report["stored"] += 1
        report["stage_seconds"][phase] = monotonic() - stage_started
    except (OSError, ValueError, OverflowError) as error:
        report["stage_seconds"][phase] = monotonic() - stage_started
        report["error"] = {"stage": phase, "chunk_id": chunk_id, "type": type(error).__name__}
        print(f"Import failed in {phase} ({type(error).__name__})", file=sys.stderr)
    report["total_seconds"] = monotonic() - started
    write_json(output / "run.json", report)
    return 1 if report["error"] else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--from", dest="from_stage", choices=("chunks", "enriched"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if bool(args.from_stage) != bool(args.input):
        parser.error("--input is required with --from and only allowed with --from")
    try:
        config = resolve_config(read_json(args.config))
        artifact = read_json(args.input) if args.input else None
        if args.input:
            validate_artifact(artifact, args.from_stage, config)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    try:
        return run(args, config, artifact)
    except (OSError, ValueError) as error:
        print(f"Import could not complete ({type(error).__name__}): {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
