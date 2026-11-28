import time

if not __package__:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, g, jsonify

from rag import embedding, generation, reranking, retrieval, transport
from rag.embedding_config import EMBEDDING_SET_ID
from rag.ollama_endpoint import OllamaResolutionError
from rag_common.health import install_actuator
from rag_common.http_errors import (
    boolean_field, install, invalid_request, json_object, problem_response, text_field, validating_request,
)
from rag_common.rag_results import InvalidResults, validate_results
from rag_common.vector_contract import VectorInputError, parse_search_options, parse_vector

app = Flask(__name__)
install(app, default_stage="processing")

install_actuator(app, info=lambda: {"configuredModels": {
    "embedding": embedding.EMBEDDING_MODEL_NAME,
    "answer": generation.ANSWER_MODEL_NAME,
    "reranker": reranking.RERANKER_MODEL,
}})


@app.errorhandler(transport.ProviderUnavailable)
def provider_unavailable(error):
    return problem_response("dependency-unavailable", str(error))


@app.errorhandler(OllamaResolutionError)
def ollama_resolution_failed(error):
    app.logger.warning("ollama_resolution_failed request_id=%s stage=%s: %s", g.request_id, g.stage, error)
    return problem_response("dependency-unavailable", "Ollama ist nicht erreichbar.")


@app.errorhandler(InvalidResults)
@app.errorhandler(transport.InvalidProviderResponse)
def invalid_upstream_response(error):
    return problem_response("upstream-invalid-response", str(error))


def upstream_post(url, payload, stage):
    return transport.upstream_post(url, payload, stage, request_id=g.request_id)


def read_rag_request():
    data = json_object()
    text_field(data, "query")
    return data


def parse_rag_options(data, *, default_top_k):
    if "filter" in data:
        invalid_request("Verwende embedding_set_id als Set-Kennung.", "filter")
    embedding_set = text_field(data, "embedding_set_id", required=False) or EMBEDDING_SET_ID
    try:
        metric, count = parse_search_options(data, default_count=retrieval.NUM_RESULTS)
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
    if template is not None and not generation.valid_user_prompt(template):
        invalid_request("user_prompt erlaubt nur {context} und {question}.", "user_prompt")


def generation_input(data, results):
    payload = {"query": data["query"], "results": results,
               "answer_model": data.get("answer_model", generation.ANSWER_MODEL_NAME)}
    for key in ("system_prompt", "user_prompt"):
        if key in data:
            payload[key] = data[key]
    return payload


def process_hit_fields(results):
    return [{"chunk_id": row["chunk_id"], "chunktext": row["chunktext"]} for row in results]


@app.post("/evaluate/retrieve")
def evaluate_retrieve():
    with validating_request():
        data = read_rag_request()
        include_distances = boolean_field(data, "include_distances")
        include_query_vector = boolean_field(data, "include_query_vector")
        reference_text = text_field(data, "reference_text", required=False)
        supplied_vector = None
        if "vector" in data:
            if reference_text is not None:
                invalid_request("reference_text erfordert ein vom Dienst erzeugtes Frageembedding.", "reference_text")
            try:
                supplied_vector = parse_vector(data["vector"], data.get("metric"))
            except VectorInputError as error:
                invalid_request(str(error), error.field)
        validate_evaluation_prompts(data)
        data = parse_rag_options(data, default_top_k=5)
    started = time.monotonic()
    g.stage = "embedding"
    embedding_started = time.monotonic()
    query_vector, embedding_metrics = embedding.embed_query(
        data["query"], supplied_vector=supplied_vector, with_metrics=True, post=upstream_post,
    )
    embedding_duration = time.monotonic() - embedding_started if supplied_vector is None else None
    g.stage = "retrieval"
    retrieval_started = time.monotonic()
    embedding_set = data["embedding_set_id"]
    metric = data["metric"]
    results = retrieval.retrieve_hits(
        query_vector, embedding_set, metric, data["num_results"], include_vector=include_distances, post=upstream_post,
    )
    retrieval_duration = time.monotonic() - retrieval_started
    diagnostics = {}
    if include_distances:
        diagnostics["hits"] = retrieval.retrieval_distances(query_vector, results)
        results = [{key: value for key, value in row.items() if key != "vector"} for row in results]
    if reference_text is not None:
        g.stage = "embedding"
        reference_vector, _ = embedding.embed_query(reference_text, post=upstream_post)
        diagnostics["reference"] = embedding.compare_embeddings(query_vector, reference_vector)
    next_request = generation_input(data, results)
    next_request.update(top_k=data["top_k"], reranker=data.get("reranker", reranking.RERANKER_MODEL))
    return jsonify(query=data["query"], results=results,
                   embedding_model=embedding.EMBEDDING_MODEL_NAME if supplied_vector is None else None,
                   embedding_set_id=embedding_set, metric=metric,
                   metrics={"retrieved_count": len(results), "embedding": embedding_metrics},
                   timings={"embedding_duration": embedding_duration,
                            "retrieval_duration": retrieval_duration,
                            "evaluation_duration": time.monotonic() - started},
                   next_request=next_request,
                   **({"vector": query_vector.tolist()} if include_query_vector else {}),
                   **({"diagnostics": diagnostics} if diagnostics else {}))


@app.post("/evaluate/rerank")
def evaluate_rerank():
    with validating_request():
        data = read_rag_request()
        validate_evaluation_results(data)
        validate_evaluation_prompts(data)
        data = parse_rag_options(data, default_top_k=5)
    started = time.monotonic()
    g.stage = "reranking"
    model = data.get("reranker", reranking.RERANKER_MODEL)
    top_k = data["top_k"]
    _, selected, _ = reranking.select_hits(data["query"], data["results"], model, top_k, post=upstream_post)
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
    started = time.monotonic()
    g.stage = "generation"
    model = data.get("answer_model", generation.ANSWER_MODEL_NAME)
    generated = generation.generate_from_hits(
        data["query"], data["results"], model,
        system_prompt=data.get("system_prompt"), user_prompt=data.get("user_prompt"), post=upstream_post,
    )
    return jsonify(**generated, query=data["query"], answer_model=model,
                   timings={"generation_request_duration": time.monotonic() - started},
                   request=generation_input(data, data["results"]))


@app.route('/process', methods=['POST'])
def process_request():
    with validating_request():
        data = parse_rag_options(read_rag_request(), default_top_k=0)
    pipeline_started = time.monotonic()
    timings = {}
    query = data["query"]
    embedding_set = data["embedding_set_id"]
    g.stage = "embedding"
    started = time.monotonic()
    query_vector, _ = embedding.embed_query(query, post=upstream_post)
    timings["embedding_duration"] = time.monotonic() - started
    g.stage = "retrieval"
    started = time.monotonic()
    results = retrieval.retrieve_hits(
        query_vector, embedding_set, data["metric"], data["num_results"], post=upstream_post,
    )
    timings["retrieval_duration"] = time.monotonic() - started
    g.stage = "reranking"
    retrieved, selected, reranking_info = reranking.select_hits(
        query, results, data.get("reranker", reranking.RERANKER_MODEL), data["top_k"], post=upstream_post,
    )
    g.stage = "generation"
    generated = generation.generate_from_hits(
        query, selected, data.get("answer_model", generation.ANSWER_MODEL_NAME), post=upstream_post,
    )
    timings["pipeline_duration"] = time.monotonic() - pipeline_started
    return jsonify(retrieved_results=process_hit_fields(retrieved),
                   selected_results=process_hit_fields(generated["results"]),
                   reranking=reranking_info, timings=timings, chunks=generated["chunks"],
                   status=generated["status"], response=generated["response"], metrics=generated["metrics"])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5600)
