import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_common.http_errors import install, Problem
from rag_common.rag_results import validate_results, generation_metrics
from flask import Flask, request, jsonify, g, has_request_context
import os
import time
import random
import requests
import numpy as np
if __package__:
    from .ollama_endpoint import resolve_ollama_base_url
else:
    from ollama_endpoint import resolve_ollama_base_url

app = Flask(__name__)
install(app, "rag")

# Konfiguration

## Embedding
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.containers.internal:11434").rstrip("/")
OLLAMA_EMBEDDING_URL = OLLAMA_BASE_URL + "/api/embeddings"
if __package__:
    from .embedding_config import EMBEDDING_MODEL, EMBEDDING_SET_ID
else:
    from embedding_config import EMBEDDING_MODEL, EMBEDDING_SET_ID
EMBEDDING_MODEL_NAME = EMBEDDING_MODEL

## Retrieval
VECTOR_API_URL = os.environ.get("VECTOR_API_URL", "http://host.containers.internal:5500/search")
NUM_RESULTS = 5

## Generation
OLLAMA_ANSWER_URL = OLLAMA_BASE_URL + "/api/generate"
ANSWER_MODEL_NAME = os.getenv("ANSWER_MODEL", "phi3:mini")
RERANKER_URL = os.getenv("RERANKER_URL", "http://host.containers.internal:5000/rerank")
RERANKER_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")

QUERY = "Wer beherrschte die westliche Hälfte des Mittelmeeres?"

# All adapters share bounded transport settings; generation is never retried.
CONNECT_TIMEOUT = float(os.getenv("RAG_CONNECT_TIMEOUT", "5"))
TOTAL_TIMEOUT = float(os.getenv("RAG_TOTAL_TIMEOUT", "1800"))
READ_TIMEOUTS = {name: float(os.getenv("RAG_" + name.upper() + "_TIMEOUT", str(default)))
                 for name, default in (("embedding", 300), ("retrieval", 60),
                                       ("reranking", 600), ("generation", 600))}


def upstream_post(url, payload, stage):
    attempts = 1 if stage == "generation" else 2
    for attempt in range(attempts):
        remaining = TOTAL_TIMEOUT
        if has_request_context():
            remaining = g.get("deadline", time.monotonic() + TOTAL_TIMEOUT) - time.monotonic()
        if remaining <= 0:
            raise Problem("dependency-unavailable", "RAG time budget exhausted.")
        try:
            response = requests.post(url, json=payload,
                timeout=(min(CONNECT_TIMEOUT, remaining), min(READ_TIMEOUTS[stage], remaining)),
                headers={"X-Request-ID": g.request_id} if has_request_context() else {})
            if has_request_context() and time.monotonic() > g.deadline:
                raise Problem("dependency-unavailable", "RAG time budget exhausted.")
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt + 1 == attempts:
                raise Problem("dependency-unavailable", stage + " is unavailable.") from exc
            delay = 0.1 * (2 ** attempt) + random.uniform(0, 0.1)
            if has_request_context() and time.monotonic() + delay >= g.deadline:
                raise Problem("dependency-unavailable", "RAG time budget exhausted.") from exc
            app.logger.warning("upstream_retry stage=%s attempt=%s", stage, attempt + 1)
            time.sleep(delay)


def generate_embedding(query):
    """Erzeugt ein Embedding für die vordefinierte Frage über die Ollama-API."""
    payload = {
        "model": EMBEDDING_MODEL_NAME,
        "prompt": query
    }
    response = upstream_post(resolve_ollama_base_url() + "/api/embeddings", payload, "embedding")
    if response.status_code == 200:
        try:
            vector = response.json().get("embedding")
            if not isinstance(vector, list) or any(type(x) not in (int, float) for x in vector):
                raise ValueError()
            vec = np.array(vector, dtype=float)
            norm = np.linalg.norm(vec)
            if vec.ndim != 1 or not vec.size or not np.isfinite(vec).all() or not np.isfinite(norm) or norm <= 0:
                raise ValueError()
            return vec / norm
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise Problem("upstream-invalid-response", "Embedding returned an invalid vector.") from exc
    raise Problem("dependency-unavailable", "Embedding is unavailable.")


def search_vectors(embedding, embedding_set_id, metric, num_results):
    """Führt eine Suche über die Vektor-API aus und gibt die besten Treffer zurück."""
    payload = {
        "vector": embedding.tolist(),
        "embedding_set_id": embedding_set_id,
        "num_results": num_results,
        "metric": metric
    }
    response = upstream_post(VECTOR_API_URL, payload, "retrieval")
    if response.status_code == 200:
        try:
            results = response.json()
        except ValueError as error:
            raise Problem("upstream-invalid-response", "Retrieval returned invalid JSON.") from error
        return validate_results(results)
    else:
        raise Problem("dependency-unavailable", "Retrieval is unavailable.")


def generate_answer(context, question, model=None):
    system_prompt = (
        "Du bist ein Experte für römische Geschichte. Beantworte Fragen nur basierend auf den "
        "als Kontext übergebenen Dokumenten. Wenn die Frage nicht beantwortet werden kann, "
        "antworte mit 'Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.'"
    )
    payload = {
        "model": model or ANSWER_MODEL_NAME,
        "stream": False,
        "system": system_prompt,
        "prompt": f"Kontext:\n{context}\n\nFrage: {question}"
    }
    response = upstream_post(resolve_ollama_base_url() + "/api/generate", payload, "generation")
    if response.status_code != 200:
        raise Problem("dependency-unavailable", "Generation is unavailable.")

    try:
        data = response.json()
    except ValueError as exc:
        raise Problem("upstream-invalid-response", "Generation returned invalid JSON.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("response"), str):
        raise Problem("upstream-invalid-response", "Generation returned an invalid answer.")
    answer = data["response"]
    metrics = generation_metrics(data)
    return answer, metrics

def rerank_results(query, results, model, top_k):
    response = upstream_post(RERANKER_URL, {
        "model": model, "query": query,
        "documents": [row["chunktext"] for row in results]}, "reranking")
    if response.status_code != 200:
        raise Problem("dependency-unavailable", "Reranking is unavailable.")
    try:
        body = response.json()
        ranked = body["ranked_documents"]
        if not isinstance(ranked, list):
            raise ValueError()
        seen = set()
        for row in ranked:
            index = row["original_index"]
            if type(index) is not int or not 0 <= index < len(results) or index in seen:
                raise ValueError()
            seen.add(index)
        return [results[row["original_index"]] for row in ranked[:top_k]]
    except (ValueError, TypeError, KeyError) as exc:
        raise Problem("upstream-invalid-response", "Reranking returned an invalid document mapping.") from exc


@app.route('/process', methods=['POST'])
def process_request():
    g.deadline = time.monotonic() + TOTAL_TIMEOUT
    data = request.get_json()
    query = data["query"]
    embedding_set = data.get("embedding_set_id", data.get("filter", EMBEDDING_SET_ID))
    g.stage = "embedding"
    embedding = generate_embedding(query)
    g.stage = "retrieval"
    retrieved = validate_results(search_vectors(embedding, embedding_set,
                                data.get("metric", "euclidean"), data.get("num_results", 5)))
    retrieved = [{"chunk_id": row["chunk_id"], "chunktext": row["chunktext"]}
                 for row in retrieved if row["chunktext"].strip()]
    selected = retrieved
    reranking = None
    top_k = data.get("top_k", 0)
    if selected and top_k > 0:
        g.stage = "reranking"
        model = data.get("reranker", RERANKER_MODEL)
        started = time.monotonic()
        selected = rerank_results(query, retrieved, model, top_k)
        reranking = {"model": model, "duration": time.monotonic() - started}
    result = {"retrieved_results": retrieved, "selected_results": selected,
              "reranking": reranking, "chunks": [row["chunk_id"] for row in selected]}
    if not selected:
        return jsonify(**result, status="no_context", metrics=None,
                       response="Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.")
    g.stage = "generation"
    context = "\n".join(row["chunktext"] for row in selected)
    answer, metrics = generate_answer(context, query, data.get("answer_model", ANSWER_MODEL_NAME))
    return jsonify(**result, status="ok", response=answer, metrics=metrics)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5600)
