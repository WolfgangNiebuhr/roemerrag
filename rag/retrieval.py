import os

from rag_common.rag_results import validate_results
from rag_common.vector_contract import VectorInputError, parse_vector

from .embedding import compare_embeddings
from .transport import InvalidProviderResponse, ProviderUnavailable, upstream_post

VECTOR_API_URL = os.environ.get("VECTOR_API_URL", "http://host.containers.internal:5500/search")
NUM_RESULTS = 5


def retrieve_hits(embedding, embedding_set_id, metric, num_results, *, include_vector=False, post=upstream_post):
    """Führt eine Suche über die Vektor-API aus und gibt die besten Treffer zurück."""
    payload = {
        "vector": embedding.tolist(),
        "embedding_set_id": embedding_set_id,
        "num_results": num_results,
        "metric": metric
    }
    if include_vector:
        payload["include_vector"] = True
    response = post(VECTOR_API_URL, payload, "retrieval")
    if response.status_code != 200:
        raise ProviderUnavailable("Retrieval is unavailable.")
    try:
        results = response.json()
    except ValueError as error:
        raise InvalidProviderResponse("Retrieval returned invalid JSON.") from error
    results = validate_results(results)
    if not include_vector:
        for row in results:
            row.pop("vector", None)
    return results


def retrieval_distances(embedding, results):
    distances = []
    for row in results:
        try:
            vector = parse_vector(row.get("vector"), None)
        except VectorInputError as error:
            raise InvalidProviderResponse("Retrieval returned an invalid stored vector.") from error
        distances.append({
            "chunk_id": row["chunk_id"],
            "distance": row.get("distance"),
            **compare_embeddings(embedding, vector),
        })
    return distances
