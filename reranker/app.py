import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_common.http_errors import Problem, install, invalid_request, json_object, text_field, validating_request
from rag_common.health import DOWN, OUT_OF_SERVICE, UP, install_actuator
from flask import Flask, jsonify
import os
import logging
import math
from threading import Lock, Thread

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
install(app, default_stage="reranking")

MODEL_NAME = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")
MODEL = None
ACTIVE_MODEL_NAME = None
MODEL_LOCK = Lock()
MODEL_STATUS = OUT_OF_SERVICE


class ModelUnavailable(RuntimeError):
    """The requested reranking model could not be loaded."""


def load_model(model_name):
    """Caller holds MODEL_LOCK across selection and inference."""
    global MODEL, ACTIVE_MODEL_NAME, MODEL_STATUS
    if MODEL is None or ACTIVE_MODEL_NAME != model_name:
        if MODEL is None:
            MODEL_STATUS = OUT_OF_SERVICE
        logging.info("Lade Rerank-Modell: %s", model_name)
        try:
            from sentence_transformers import CrossEncoder
            candidate = CrossEncoder(model_name, trust_remote_code=False)
        except Exception as error:
            if MODEL is None:
                MODEL_STATUS = DOWN
            logging.exception("Modell konnte nicht geladen werden: %s", model_name)
            raise ModelUnavailable("Rerank model is not available") from error
        MODEL, ACTIVE_MODEL_NAME = candidate, model_name
        MODEL_STATUS = UP
    return MODEL


@app.route('/rerank', methods=['POST'])
def rerank():
    with validating_request():
        data = json_object()
        query = text_field(data, "query")
        model_name = (text_field(data, "model", required=False) or MODEL_NAME).strip()
        documents = data.get("documents")
        if not isinstance(documents, list) or any(not isinstance(doc, str) or not doc.strip() for doc in documents):
            invalid_request("documents muss eine Liste nichtleerer Strings sein.", "documents")

    if not documents:
        return jsonify({"ranked_documents": [], "model": model_name})

    sentences = [[query, doc] for doc in documents]
    with MODEL_LOCK:
        try:
            model = load_model(model_name)
        except ModelUnavailable as error:
            raise Problem("model-unavailable", "Rerank-Modell ist nicht verf?gbar.", model=model_name) from error
        scores = model.predict(sentences)

    try:
        scores = [float(score) for score in scores]
    except (TypeError, ValueError, OverflowError) as error:
        raise Problem("upstream-invalid-response", "Reranking returned an invalid score.") from error
    if not all(math.isfinite(score) for score in scores):
        raise Problem("upstream-invalid-response", "Reranking returned an invalid score.")

    results = [
        {"original_index": index, "score": score, "text": doc}
        for index, (doc, score) in enumerate(zip(documents, scores))
    ]

    ranked_results = sorted(results, key=lambda x: x['score'], reverse=True)
    logging.info("Rerank request processed: documents=%s", len(documents))
    return jsonify({"ranked_documents": ranked_results, "model": model_name})


def initialize_default_model():
    with MODEL_LOCK:
        if MODEL is None:
            try:
                load_model(MODEL_NAME)
            except ModelUnavailable:
                pass  # A later rerank request can retry.


install_actuator(app, status=lambda: MODEL_STATUS,
                 info=lambda: {"models": {"active": ACTIVE_MODEL_NAME, "default": MODEL_NAME}})


if __name__ == '__main__':
    Thread(target=initialize_default_model, name="reranker-startup", daemon=True).start()
    app.run(host='0.0.0.0', port=5000)
