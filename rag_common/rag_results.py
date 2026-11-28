import math


class InvalidResults(ValueError):
    """The supplied results do not have the expected chunk structure."""


def validate_results(results):
    if not isinstance(results, list):
        raise InvalidResults("Erwartet wurde eine Liste.")
    for row in results:
        if (not isinstance(row, dict)
                or not isinstance(row.get("chunk_id"), str) or not row["chunk_id"].strip()
                or not isinstance(row.get("chunktext"), str)):
            raise InvalidResults("Retrieval contains invalid chunk fields.")
    return results


def usable_hits(results):
    return [row for row in results if row["chunktext"].strip()]


def generation_metrics(data):
    def number(key, count=False):
        value = data.get(key)
        if type(value) not in (int, float) or value < 0:
            return None
        try:
            if not math.isfinite(value) or (count and type(value) is not int):
                return None
        except OverflowError:
            return None
        return value
    metrics = {}
    for key in ("total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        value = number(key)
        metrics[key] = value / 1e9 if value is not None else None
    # Keep the previous wire field as a compatibility alias.
    metrics["generation_duration"] = metrics["total_duration"]
    metrics["prompt_tokens"] = number("prompt_eval_count", count=True)
    metrics["answer_tokens"] = number("eval_count", count=True)
    duration, tokens = metrics["eval_duration"], metrics["answer_tokens"]
    rate = tokens / duration if duration and tokens is not None else None
    metrics["answer_rate"] = rate if rate is not None and math.isfinite(rate) else None
    return metrics


