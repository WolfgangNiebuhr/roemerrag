import math

import numpy as np

from rag_common.rag_results import generation_metrics
from rag_common.vector_contract import embedding_norm

from .embedding_config import EMBEDDING_MODEL as EMBEDDING_MODEL_NAME
from .ollama_endpoint import resolve_ollama_base_url
from .transport import InvalidProviderResponse, ProviderUnavailable, upstream_post


def generate_embedding(query, with_metrics=False, *, post=upstream_post):
    """Erzeugt ein Embedding für die vordefinierte Frage über die Ollama-API."""
    payload = {
        "model": EMBEDDING_MODEL_NAME,
        "prompt": query
    }
    response = post(resolve_ollama_base_url() + "/api/embeddings", payload, "embedding")
    if response.status_code == 200:
        try:
            body = response.json()
            vector = body.get("embedding") if isinstance(body, dict) else None
            norm = embedding_norm(vector)
            normalized = np.array(vector, dtype=float) / norm
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


def embed_query(query, *, supplied_vector=None, with_metrics=False, post=upstream_post):
    if supplied_vector is not None:
        return np.array(supplied_vector, dtype=float), None
    if with_metrics:
        return generate_embedding(query, with_metrics=True, post=post)
    return generate_embedding(query, post=post), None


def compare_embeddings(query_vector, other_vector):
    if len(query_vector) != len(other_vector):
        raise InvalidProviderResponse("Cannot compare embeddings with different dimensions.")
    query_norm = math.hypot(*query_vector)
    other_norm = math.hypot(*other_vector)
    cosine = None
    if 0 < query_norm < math.inf and 0 < other_norm < math.inf:
        cosine = math.fsum((a / query_norm) * (b / other_norm) for a, b in zip(query_vector, other_vector))
        cosine = max(-1.0, min(1.0, cosine))
    euclidean = math.dist(query_vector, other_vector)
    return {"cosine_similarity": cosine, "euclidean_distance": euclidean if math.isfinite(euclidean) else None}
