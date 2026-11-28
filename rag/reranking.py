import math
import os
import time

from rag_common.rag_results import usable_hits

from .transport import InvalidProviderResponse, ProviderUnavailable, upstream_post

RERANKER_URL = os.getenv("RERANKER_URL", "http://host.containers.internal:5000/rerank")
RERANKER_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")


def rerank_results(query, results, model, top_k, with_scores=False, *, post=upstream_post):
    response = post(RERANKER_URL, {
        "model": model, "query": query,
        "documents": [row["chunktext"] for row in results]}, "reranking")
    if response.status_code == 502:
        raise InvalidProviderResponse("Reranker rejected an invalid upstream response.")
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
            score = row["score"]
            if type(score) not in (int, float) or not math.isfinite(score):
                raise InvalidProviderResponse("Reranking returned an invalid score.")
        selected = []
        for row in ranked[:top_k]:
            result = dict(results[row["original_index"]])
            if with_scores:
                result.update(rerank_score=row["score"], original_index=row["original_index"])
            selected.append(result)
        return selected
    except InvalidProviderResponse:
        raise
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise InvalidProviderResponse("Reranking returned an invalid document mapping.") from exc


def select_hits(query, results, model, top_k, *, post=upstream_post):
    candidates = usable_hits(results)
    if not candidates or top_k == 0:
        return candidates, candidates, None
    started = time.monotonic()
    selected = rerank_results(query, candidates, model, top_k, with_scores=True, post=post)
    return candidates, selected, {"model": model, "duration": time.monotonic() - started}
