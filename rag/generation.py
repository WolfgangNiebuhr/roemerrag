from string import Formatter

from rag_common.rag_results import generation_metrics, usable_hits

from .embedding_config import ANSWER_MODEL as ANSWER_MODEL_NAME
from .ollama_endpoint import resolve_ollama_base_url
from .transport import InvalidProviderResponse, ProviderUnavailable, upstream_post


def generate_answer(context, question, model=None, system_prompt=None, user_prompt=None, *, post=upstream_post):
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
    response = post(resolve_ollama_base_url() + "/api/generate", payload, "generation")
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


def generate_from_hits(query, results, model, *, post=upstream_post, **prompts):
    selected = usable_hits(results)
    context = "\n".join(row["chunktext"] for row in selected)
    if selected:
        answer, metrics = generate_answer(context, query, model, post=post, **prompts)
    else:
        answer = "Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden."
        metrics = None
    return {
        "results": selected, "context": context, "status": "ok" if selected else "no_context",
        "response": answer, "metrics": metrics, "chunks": [row["chunk_id"] for row in selected],
    }


def valid_user_prompt(template):
    try:
        return all(
            field is None or (field in ("context", "question") and not spec and not conversion)
            for _, field, spec, conversion in Formatter().parse(template)
        )
    except ValueError:
        return False
