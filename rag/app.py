import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_common.http_errors import (
    aliased_text, install, invalid_request, json_object, problem_response, text_field, validating_request,
)
from rag_common.rag_results import InvalidResults, generation_metrics, validate_results
from rag_common.vector_contract import VectorInputError, parse_search_options, parse_vector
from flask import Flask, jsonify, g, has_request_context
import os
import time
import random
from string import Formatter
import requests
import numpy as np
if __package__:
    from .ollama_endpoint import resolve_ollama_base_url
else:
    from ollama_endpoint import resolve_ollama_base_url

app = Flask(__name__)
install(app, default_stage="processing")

# Konfiguration

## Embedding
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://host.containers.internal:11434").rstrip("/")
OLLAMA_EMBEDDING_URL = OLLAMA_BASE_URL + "/api/embeddings"
if __package__:
    from .embedding_config import EMBEDDING_MODEL, EMBEDDING_SET_ID, ANSWER_MODEL
else:
    from embedding_config import EMBEDDING_MODEL, EMBEDDING_SET_ID, ANSWER_MODEL
EMBEDDING_MODEL_NAME = EMBEDDING_MODEL

## Retrieval
VECTOR_API_URL = os.environ.get("VECTOR_API_URL", "http://host.containers.internal:5500/search")
NUM_RESULTS = 5

## Generation
OLLAMA_ANSWER_URL = OLLAMA_BASE_URL + "/api/generate"
ANSWER_MODEL_NAME = ANSWER_MODEL
RERANKER_URL = os.getenv("RERANKER_URL", "http://host.containers.internal:5000/rerank")
RERANKER_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")

QUERY = "Wer beherrschte die westliche Hälfte des Mittelmeeres?"

# All adapters share bounded transport settings; generation is never retried.
CONNECT_TIMEOUT = float(os.getenv("RAG_CONNECT_TIMEOUT", "5"))
TOTAL_TIMEOUT = float(os.getenv("RAG_TOTAL_TIMEOUT", "1800"))
READ_TIMEOUTS = {name: float(os.getenv("RAG_" + name.upper() + "_TIMEOUT", str(default)))
                 for name, default in (("embedding", 300), ("retrieval", 60),
                                       ("reranking", 600), ("generation", 600))}


class ProviderUnavailable(RuntimeError):
    """A provider call could not complete successfully."""


class InvalidProviderResponse(ValueError):
    """A provider returned data that does not meet its response contract."""


@app.errorhandler(ProviderUnavailable)
def provider_unavailable(error):
    return problem_response("dependency-unavailable", str(error))


@app.errorhandler(InvalidResults)
@app.errorhandler(InvalidProviderResponse)
def invalid_upstream_response(error):
    return problem_response("upstream-invalid-response", str(error))


def upstream_post(url, payload, stage):
    attempts = 1 if stage == "generation" else 2
    for attempt in range(attempts):
        remaining = TOTAL_TIMEOUT
        if has_request_context():
            remaining = g.get("deadline", time.monotonic() + TOTAL_TIMEOUT) - time.monotonic()
        if remaining <= 0:
            raise ProviderUnavailable("RAG time budget exhausted.")
        try:
            response = requests.post(url, json=payload,
                timeout=(min(CONNECT_TIMEOUT, remaining), min(READ_TIMEOUTS[stage], remaining)),
                headers={"X-Request-ID": g.request_id} if has_request_context() else {})
            if has_request_context() and time.monotonic() > g.deadline:
                raise ProviderUnavailable("RAG time budget exhausted.")
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt + 1 == attempts:
                raise ProviderUnavailable(stage + " is unavailable.") from exc
            delay = 0.1 * (2 ** attempt) + random.uniform(0, 0.1)
            if has_request_context() and time.monotonic() + delay >= g.deadline:
                raise ProviderUnavailable("RAG time budget exhausted.") from exc
            app.logger.warning("upstream_retry stage=%s attempt=%s", stage, attempt + 1)
            time.sleep(delay)


def generate_embedding(query, with_metrics=False):
    """Erzeugt ein Embedding für die vordefinierte Frage über die Ollama-API."""
    payload = {
        "model": EMBEDDING_MODEL_NAME,
        "prompt": query
    }
    response = upstream_post(resolve_ollama_base_url() + "/api/embeddings", payload, "embedding")
    if response.status_code == 200:
        try:
            body = response.json()
            vector = body.get("embedding")
            if not isinstance(vector, list) or any(type(x) not in (int, float) for x in vector):
                raise ValueError()
            vec = np.array(vector, dtype=float)
            norm = np.linalg.norm(vec)
            if vec.ndim != 1 or not vec.size or not np.isfinite(vec).all() or not np.isfinite(norm) or norm <= 0:
                raise ValueError()
            normalized = vec / norm
            if with_metrics:
                available = generation_metrics(body)
                return normalized, {"total_duration": available["generation_duration"],
                                    "load_duration": available["load_duration"],
                                    "prompt_eval_duration": available["prompt_eval_duration"],
                                    "prompt_tokens": available["prompt_tokens"]}
            return normalized
        except (ValueError, TypeError, AttributeError, OverflowError) as exc:
            raise InvalidProviderResponse("Embedding returned an invalid vector.") from exc
    raise ProviderUnavailable("Embedding is unavailable.")


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
            raise InvalidProviderResponse("Retrieval returned invalid JSON.") from error
        return validate_results(results)
    else:
        raise ProviderUnavailable("Retrieval is unavailable.")


def generate_answer(context, question, model=None, system_prompt=None, user_prompt=None):
    system_prompt = system_prompt or (
        "Du bist ein Experte für römische Geschichte. Beantworte Fragen nur basierend auf den "
        "als Kontext übergebenen Dokumenten. Wenn die Frage nicht beantwortet werden kann, "
        "antworte mit 'Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.'"
    )
    payload = {
        "model": model or ANSWER_MODEL_NAME,
        "stream": False,
        "system": system_prompt,
        "prompt": (user_prompt or "Kontext:\n{context}\n\nFrage: {question}").format(context=context, question=question)
    }
    response = upstream_post(resolve_ollama_base_url() + "/api/generate", payload, "generation")
    if response.status_code != 200:
        raise ProviderUnavailable("Generation is unavailable.")

    try:
        data = response.json()
    except ValueError as exc:
        raise InvalidProviderResponse("Generation returned invalid JSON.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("response"), str):
        raise InvalidProviderResponse("Generation returned an invalid answer.")
    answer = data["response"]
    metrics = generation_metrics(data)
    return answer, metrics

def rerank_results(query, results, model, top_k, with_scores=False):
    response = upstream_post(RERANKER_URL, {
        "model": model, "query": query,
        "documents": [row["chunktext"] for row in results]}, "reranking")
    if response.status_code != 200:
        raise ProviderUnavailable("Reranking is unavailable.")
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
        selected = []
        for row in ranked[:top_k]:
            result = dict(results[row["original_index"]])
            if with_scores:
                score = row.get("score")
                if type(score) not in (int, float) or not np.isfinite(score):
                    raise ValueError()
                result.update(rerank_score=score, original_index=row["original_index"])
            selected.append(result)
        return selected
    except (ValueError, TypeError, KeyError) as exc:
        raise InvalidProviderResponse("Reranking returned an invalid document mapping.") from exc


def read_rag_request():
    data = json_object()
    text_field(data, "query")
    return data


def parse_rag_options(data, *, default_top_k):
    embedding_set = aliased_text(
        data, "embedding_set_id", "filter", conflict_detail="Widersprüchliche Set-Kennungen.",
        default=EMBEDDING_SET_ID,
    )
    try:
        metric, count = parse_search_options(data, default_count=NUM_RESULTS)
    except VectorInputError as error:
        invalid_request(str(error), error.field)
    text_field(data, "reranker", required=False)
    text_field(data, "answer_model", required=False)
    top_k = data.get("top_k", default_top_k)
    if type(top_k) is not int or top_k < 0:
        invalid_request("top_k muss eine ganze Zahl >= 0 sein.", "top_k")
    return dict(data, embedding_set_id=embedding_set, metric=metric, num_results=count, top_k=top_k)


def validate_evaluation_results(data):
    try:
        validate_results(data.get("results"))
    except InvalidResults:
        invalid_request("results muss Chunkobjekte mit chunk_id und chunktext enthalten.", "results")


def validate_evaluation_prompts(data):
    text_field(data, "system_prompt", required=False)
    template = text_field(data, "user_prompt", required=False)
    if template is None:
        return
    try:
        allowed = all(
            field is None or (field in ("context", "question") and not spec and not conversion)
            for _, field, spec, conversion in Formatter().parse(template)
        )
    except ValueError:
        allowed = False
    if not allowed:
        invalid_request("user_prompt erlaubt nur {context} und {question}.", "user_prompt")


def evaluation_start():
    started = time.monotonic()
    g.deadline = started + TOTAL_TIMEOUT
    return started


def generation_input(data, results):
    payload = {"query": data["query"], "results": results,
               "answer_model": data.get("answer_model", ANSWER_MODEL_NAME)}
    for key in ("system_prompt", "user_prompt"):
        if key in data:
            payload[key] = data[key]
    return payload


@app.post("/evaluate/retrieve")
def evaluate_retrieve():
    with validating_request():
        data = read_rag_request()
        supplied_vector = None
        if "vector" in data:
            try:
                supplied_vector = parse_vector(data["vector"], data.get("metric"))
            except VectorInputError as error:
                invalid_request(str(error), error.field)
        validate_evaluation_prompts(data)
        data = parse_rag_options(data, default_top_k=5)
    started = evaluation_start()
    g.stage = "embedding"
    embedding_started = time.monotonic()
    embedding_metrics = None
    if supplied_vector is not None:
        embedding = np.array(supplied_vector, dtype=float)
    else:
        embedding, embedding_metrics = generate_embedding(data["query"], with_metrics=True)
    embedding_duration = time.monotonic() - embedding_started if supplied_vector is None else None
    g.stage = "retrieval"
    retrieval_started = time.monotonic()
    embedding_set = data["embedding_set_id"]
    metric = data["metric"]
    results = search_vectors(embedding, embedding_set, metric, data["num_results"])
    retrieval_duration = time.monotonic() - retrieval_started
    next_request = generation_input(data, results)
    next_request.update(top_k=data["top_k"], reranker=data.get("reranker", RERANKER_MODEL))
    return jsonify(query=data["query"], results=results, vector=embedding.tolist(),
                   embedding_model=EMBEDDING_MODEL_NAME if supplied_vector is None else None,
                   embedding_set_id=embedding_set, metric=metric,
                   metrics={"retrieved_count": len(results), "embedding": embedding_metrics},
                   timings={"embedding_duration": embedding_duration,
                            "retrieval_duration": retrieval_duration,
                            "evaluation_duration": time.monotonic() - started},
                   next_request=next_request)


@app.post("/evaluate/rerank")
def evaluate_rerank():
    with validating_request():
        data = read_rag_request()
        validate_evaluation_results(data)
        validate_evaluation_prompts(data)
        data = parse_rag_options(data, default_top_k=5)
    started = evaluation_start()
    g.stage = "reranking"
    # Match /process: whitespace-only passages are never sent to the reranker.
    results = [row for row in data["results"] if row["chunktext"].strip()]
    model = data.get("reranker", RERANKER_MODEL)
    top_k = data["top_k"]
    selected = rerank_results(data["query"], results, model, top_k, with_scores=True) if results and top_k else results
    return jsonify(query=data["query"], results=selected, reranker=model, top_k=top_k,
                   status="ok" if selected else "no_context",
                   metrics={"input_count": len(data["results"]), "selected_count": len(selected)},
                   timings={"reranking_duration": time.monotonic() - started},
                   next_request=generation_input(data, selected))


@app.post("/evaluate/generate")
def evaluate_generate():
    with validating_request():
        data = read_rag_request()
        validate_evaluation_results(data)
        validate_evaluation_prompts(data)
        data = parse_rag_options(data, default_top_k=5)
    started = evaluation_start()
    g.stage = "generation"
    selected = [row for row in data["results"] if row["chunktext"].strip()]
    context = "\n".join(row["chunktext"] for row in selected)
    model = data.get("answer_model", ANSWER_MODEL_NAME)
    metrics = None
    if selected:
        answer, metrics = generate_answer(context, data["query"], model,
            system_prompt=data.get("system_prompt"), user_prompt=data.get("user_prompt"))
    else:
        answer = "Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden."
    return jsonify(query=data["query"], results=selected, context=context, answer_model=model,
                   status="ok" if selected else "no_context", response=answer,
                   chunks=[row["chunk_id"] for row in selected], metrics=metrics,
                   timings={"generation_request_duration": time.monotonic() - started},
                   request=generation_input(data, data["results"]))


@app.route('/process', methods=['POST'])
def process_request():
    with validating_request():
        data = parse_rag_options(read_rag_request(), default_top_k=0)
    pipeline_started = time.monotonic()
    g.deadline = pipeline_started + TOTAL_TIMEOUT
    timings = {}
    query = data["query"]
    embedding_set = data["embedding_set_id"]
    g.stage = "embedding"
    started = time.monotonic()
    embedding = generate_embedding(query)
    timings["embedding_duration"] = time.monotonic() - started
    g.stage = "retrieval"
    started = time.monotonic()
    retrieved = validate_results(search_vectors(embedding, embedding_set, data["metric"], data["num_results"]))
    retrieved = [{"chunk_id": row["chunk_id"], "chunktext": row["chunktext"]}
                 for row in retrieved if row["chunktext"].strip()]
    timings["retrieval_duration"] = time.monotonic() - started
    selected = retrieved
    reranking = None
    top_k = data["top_k"]
    if selected and top_k > 0:
        g.stage = "reranking"
        model = data.get("reranker", RERANKER_MODEL)
        started = time.monotonic()
        selected = rerank_results(query, retrieved, model, top_k)
        reranking = {"model": model, "duration": time.monotonic() - started}
    result = {"retrieved_results": retrieved, "selected_results": selected,
              "reranking": reranking, "timings": timings, "chunks": [row["chunk_id"] for row in selected]}
    if not selected:
        timings["pipeline_duration"] = time.monotonic() - pipeline_started
        return jsonify(**result, status="no_context", metrics=None,
                       response="Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.")
    g.stage = "generation"
    context = "\n".join(row["chunktext"] for row in selected)
    answer, metrics = generate_answer(context, query, data.get("answer_model", ANSWER_MODEL_NAME))
    timings["pipeline_duration"] = time.monotonic() - pipeline_started
    return jsonify(**result, status="ok", response=answer, metrics=metrics)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5600)
