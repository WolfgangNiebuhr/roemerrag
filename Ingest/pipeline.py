# Steuert Chunking, optionale Anreicherung, Embedding und Speicherung eines Importlaufs.

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

import requests

from .utils.chunking import split_recursive
from .utils.keywords import keyword_messages


DEFAULT_SEPARATORS = ("\n\n", ".\n", ". ", "")


# Erstellt die Nachrichten fuer die kurze Keyword-Promptversion.
def concise_keyword_messages(text):
    return (
        "Extrahiere bis zu fuenf aussagekraeftige Stichwoerter aus dem Quelltext. "
        "Uebernimm ihre Schreibweise und gib ausschliesslich eine kommaseparierte Liste aus.",
        text,
        None,
    )


KEYWORD_PROMPTS = {"keywords-v1": keyword_messages, "keywords-v2": concise_keyword_messages}


def recursive(text, *, size=1000, overlap=150, separators=DEFAULT_SEPARATORS):
    return split_recursive(text, size, overlap, separators=list(separators))


def request_json(send, url, payload, timeout, status):
    response = send(url, json=payload, timeout=timeout, allow_redirects=False)
    if response.status_code != status:
        raise ValueError(f"HTTP {response.status_code}")
    return response.json()


# Ermittelt Keywords mit Ollama und erfasst die Anfrage- und Providermetriken.
def keywords(text, *, model, prompt, ollama, timeout, system_prompt=None):
    if system_prompt is None:
        system, query, _ = KEYWORD_PROMPTS[prompt](text)
    else:
        system, query = system_prompt, text
    started = monotonic()
    data = request_json(requests.post, ollama + "/api/chat", {
        "model": model, "stream": False, "options": {"temperature": 0.0},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": query}],
    }, timeout, 200)
    message = data.get("message") if isinstance(data, dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Missing keywords in Ollama response")
    metrics = {"request_seconds": monotonic() - started}
    for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration",
                "prompt_eval_count", "eval_count"):
        value = data.get(key)
        metrics[key] = value if type(value) is int and value >= 0 else None
    return content, metrics


def no_enrichment(text, *, ollama, timeout):
    return "", None


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


# Validiert die Konfiguration und ergaenzt die Standardwerte der angeforderten Stufen.
def resolve_config(config, *, chunk_only=False, enrichment_only=False):
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
    enrichment = fields(config.get("enrichment", {"strategy": "none"}), "strategy parameters")
    strategy = enrichment.get("strategy")
    require(isinstance(strategy, str) and strategy in ENRICHERS, "Unknown enrichment strategy")
    params = enrichment.get("parameters", {})
    if strategy == "keywords":
        fields(params, "model prompt system_prompt")
        params = {"model": "gemma3:4b", "prompt": "keywords-v1", **params}
        require(nonempty(params["model"]) and nonempty(params["prompt"]),
                "Expected a keyword model and a prompt version")
        if "system_prompt" in params:
            require(nonempty(params["system_prompt"]) and params["prompt"] not in KEYWORD_PROMPTS,
                    "A custom system prompt requires its own prompt version")
        else:
            require(params["prompt"] in KEYWORD_PROMPTS, "Unknown keyword prompt version")
    else:
        fields(params, "")
    result["enrichment"] = {"strategy": strategy, "parameters": params}
    if enrichment_only:
        return result
    require(nonempty(config.get("name")) and nonempty(config.get("embedding_set_id")),
            "Expected a name and embedding_set_id")
    embedding = fields(config.get("embedding"), "model normalize dimensions")
    embedding = {"normalize": True, "dimensions": 1024, **embedding}
    require(nonempty(embedding.get("model")) and type(embedding["normalize"]) is bool
            and type(embedding["dimensions"]) is int and embedding["dimensions"] == 1024,
            "Expected an embedding model, boolean normalize and 1024 dimensions")
    return {**result, "name": config["name"], "embedding_set_id": config["embedding_set_id"],
            "embedding": embedding}


def has_chunk_text(value):
    return isinstance(value, str) and bool(value.strip(" \n\r"))


# Zerlegt eine UTF-8-Quelle in Chunks und versieht sie mit stabilen IDs.
def make_chunks(path, config):
    raw = path.read_bytes()
    source = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    strategy = config["chunking"]
    chunks = CHUNKERS[strategy["strategy"]](source, **strategy["parameters"])
    chunks = [chunk for chunk in chunks if has_chunk_text(chunk)]
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


# Wendet die Anreicherungsstrategie an und setzt den gemeinsamen Chunktext zusammen.
def enrich_chunk(source, strategy, ollama, timeout):
    enrichment, metrics = ENRICHERS[strategy["strategy"]](
        source["source_text"], **strategy["parameters"], ollama=ollama, timeout=timeout,
    )
    row = {**source, "enrichment": enrichment, "enrichment_metrics": metrics}
    return {**row, "chunktext": chunktext(row)}


# Liest die Ollama-Adresse und validiert die Zeitlimits fuer Keyword-Anfragen.
def enrichment_connection():
    ollama = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    timeout = (float(os.getenv("IMPORT_CONNECT_TIMEOUT", "5")),
               float(os.getenv("IMPORT_KEYWORD_TIMEOUT", "120")))
    require(all(math.isfinite(value) and value > 0 for value in timeout),
            "HTTP timeouts must be positive and finite")
    return ollama, timeout


# Prueft Format, Konfiguration und Chunks eines vorhandenen Zwischenartefakts.
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
                and has_chunk_text(row.get("source_text")), "Invalid artifact chunk")
        if stage == "enriched":
            enrichment = row.get("enrichment")
            require(isinstance(enrichment, str)
                    and (nonempty(enrichment) if config["enrichment"]["strategy"] == "keywords"
                         else enrichment == "")
                    and row.get("chunktext") == chunktext(row), "Invalid artifact enrichment")


# Ruft das Embedding ab, prueft den Vektor und normalisiert ihn bei Bedarf.
def embed(text, config, ollama, timeout):
    data = request_json(requests.post, ollama + "/api/embeddings",
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


# Schreibt ein JSON-Artefakt atomar ueber eine Datei im Zielverzeichnis.
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


def run(args, config, artifact, start, vector_url):
    total = len(artifact["chunks"])
    next_chunk = start
    phase = "setup"
    enriched, embeddings = [], []
    try:
        ollama, keyword_timeout = enrichment_connection()
        connect = keyword_timeout[0]
        embedding_timeout = (connect, float(os.getenv("IMPORT_EMBED_TIMEOUT", "300")))
        storage_timeout = (connect, float(os.getenv("IMPORT_STORE_TIMEOUT", "60")))
        require(all(math.isfinite(value) and value > 0 for value in (*embedding_timeout, *storage_timeout)),
                "HTTP timeouts must be positive and finite")

        output = args.output_dir
        output.mkdir(parents=True, exist_ok=False)
        write_json(output / f"{artifact['stage']}.json", artifact)
        for number, source in enumerate(artifact["chunks"][start - 1:], start):
            chunk_id = source["chunk_id"]
            phase = "enrichment"
            row = source if artifact["stage"] == "enriched" else enrich_chunk(
                source, config["enrichment"], ollama, keyword_timeout,
            )
            phase = "embedding"
            vector = embed(row["chunktext"], config["embedding"], ollama, embedding_timeout)
            phase = "storage"
            data = request_json(requests.post, vector_url, {
                "chunk_id": chunk_id, "embedding_set_id": config["embedding_set_id"],
                "chunktext": row["chunktext"], "vector": vector,
            }, storage_timeout, 201)
            require(isinstance(data, dict) and data.get("message") == "Vector stored",
                    "Invalid Vector API acknowledgement")
            next_chunk = number + 1
            if start == 1:
                enriched.append(row)
                embeddings.append({**row, "vector": vector})

        phase = "artifacts"
        if start == 1:
            enriched_artifact = {**artifact, "stage": "enriched", "enrichment": config["enrichment"],
                                 "chunks": enriched}
            if artifact["stage"] == "chunks":
                write_json(output / "enriched.json", enriched_artifact)
            write_json(output / "embeddings.json",
                       {**enriched_artifact, "stage": "embeddings", "embedding": config["embedding"],
                        "chunks": embeddings})
        phase = "cleanup"
        delete_url = vector_url.rsplit("/", 1)[0] + "/chunks"
        data = request_json(requests.delete, delete_url, {
            "embedding_set_id": config["embedding_set_id"], "document_id": artifact["document_id"],
            "from": total + 1,
        }, storage_timeout, 200)
        require(isinstance(data, dict) and type(data.get("deleted")) is int and data["deleted"] >= 0,
                "Invalid Vector API cleanup acknowledgement")
    except (OSError, ValueError, OverflowError, KeyboardInterrupt) as error:
        print(f"Import failed in {phase} at chunk {next_chunk} ({type(error).__name__}). "
              f"Continue with --start {next_chunk}.", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--file", type=Path)
    source.add_argument("--from", dest="from_stage", choices=("chunks", "enriched"))
    parser.add_argument("--start", type=int, default=1, metavar="CHUNK")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    if bool(args.from_stage) != bool(args.input):
        parser.error("--input is required with --from and only allowed with --from")
    vector_url = os.getenv("IMPORT_VECTOR_URL", "http://127.0.0.1:5500/vectors").rstrip("/")
    try:
        config = resolve_config(read_json(args.config))
        if args.input:
            artifact = read_json(args.input)
            validate_artifact(artifact, args.from_stage, config)
        else:
            artifact = make_chunks(args.file, config)
        require(1 <= args.start <= len(artifact["chunks"]) + 1, "--start is outside the document")
    except (OSError, ValueError, OverflowError) as error:
        parser.error(str(error))
    return run(args, config, artifact, args.start, vector_url)


if __name__ == "__main__":
    sys.exit(main())
