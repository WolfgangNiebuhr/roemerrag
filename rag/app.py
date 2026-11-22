import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_common.http_errors import install, Problem
from flask import Flask, request, jsonify, g
import os
import math
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
ANSWER_MODEL_NAME = "phi3:mini"

QUERY = "Wer beherrschte die westliche Hälfte des Mittelmeeres?"

def generate_embedding(query):
    """Erzeugt ein Embedding für die vordefinierte Frage über die Ollama-API."""
    payload = {
        "model": EMBEDDING_MODEL_NAME,
        "prompt": query
    }
    response = requests.post(resolve_ollama_base_url() + "/api/embeddings", json=payload, timeout=300)
    if response.status_code == 200:
        vector = response.json().get("embedding")
        if not vector:
            raise ValueError("Ollama-Antwort enth?lt kein Embedding")
        vec = np.array(vector, dtype=float)
        norm = np.linalg.norm(vec)
        if not norm:
            raise ValueError("Ollama lieferte ein Embedding mit Norm 0")
        vec = vec / norm  # Normalisierung des Embeddings
        return vec
    else:
        raise Exception(f"Fehler beim Abrufen des Embeddings: {response.text}")

def search_vectors(embedding, embedding_set_id, metric, num_results):
    """Führt eine Suche über die Vektor-API aus und gibt die besten Treffer zurück."""
    payload = {
        "vector": embedding.tolist(),
        "embedding_set_id": embedding_set_id,
        "num_results": num_results,
        "metric": metric
    }
    response = requests.post(VECTOR_API_URL, json=payload, timeout=60)
    if response.status_code == 200:
        try:
            results = response.json()
        except ValueError as error:
            raise Problem("upstream-invalid-response", "Retrieval returned invalid JSON.") from error
        return validate_results(results)
    else:
        raise Problem("dependency-unavailable", "Retrieval is unavailable.")


def validate_results(results):
    if not isinstance(results, list):
        raise Problem("upstream-invalid-response", "Erwartet wurde eine Liste.")
    for row in results:
        if (not isinstance(row, dict)
                or not isinstance(row.get("chunk_id"), str) or not row["chunk_id"].strip()
                or not isinstance(row.get("chunktext"), str)):
            raise Problem("upstream-invalid-response", "Retrieval contains invalid chunk fields.")
    return results


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
    metrics["prompt_tokens"] = number("prompt_eval_count", count=True)
    metrics["answer_tokens"] = number("eval_count", count=True)
    duration, tokens = metrics["eval_duration"], metrics["answer_tokens"]
    rate = tokens / duration if duration and tokens is not None else None
    metrics["answer_rate"] = rate if rate is not None and math.isfinite(rate) else None
    return metrics


def generate_answer(context, question):
    system_prompt = (
        "Du bist ein Experte für römische Geschichte. Beantworte Fragen nur basierend auf den "
        "als Kontext übergebenen Dokumenten. Wenn die Frage nicht beantwortet werden kann, "
        "antworte mit 'Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.'"
    )
    payload = {
        "model": ANSWER_MODEL_NAME,
        "stream": False,
        "system": system_prompt,
        "prompt": f"Kontext:\n{context}\n\nFrage: {question}"
    }
    response = requests.post(resolve_ollama_base_url() + "/api/generate", json=payload, timeout=600)
    if response.status_code != 200:
        raise Exception(f"Fehler bei der Antwortgenerierung: {response.text}")

    data = response.json()
    answer = data.get("response", "Keine Antwort erhalten.")
    metrics = generation_metrics(data)
    return answer, metrics

@app.route('/process', methods=['POST'])
def process_request():
    try:
        data = request.get_json(silent=True)
        query = data.get("query")
        filter = data.get("embedding_set_id", data.get("filter", EMBEDDING_SET_ID))
        metric = data.get("metric", "euclidean")
        num_results = data.get("num_results", 5)


        g.stage = "embedding"
        embedding = generate_embedding(query)
        g.stage = "retrieval"
        results = validate_results(search_vectors(embedding, filter, metric, num_results))
        results = [row for row in results if row["chunktext"].strip()]
        if not results:
            return jsonify(status="no_context", response="Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.", chunks=[], metrics=None), 200

        context = "\n".join([result["chunktext"] for result in results])
        second_elements = [result["chunk_id"] for result in results]

        g.stage = "generation"
        answer, metrics = generate_answer(context, query)

        response = {
            "response": answer,
            "metrics": metrics,
            "chunks": second_elements
        }
        return jsonify(response), 200

    except Exception as e:
        raise

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5600)
