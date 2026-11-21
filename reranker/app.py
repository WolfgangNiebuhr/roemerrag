import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag_common.http_errors import install, Problem
from flask import Flask, request, jsonify
import os
import logging
from threading import Lock

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
install(app, "reranker")

MODEL_NAME = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")
MODEL = None
ACTIVE_MODEL_NAME = None
MODEL_LOCK = Lock()


def load_model(model_name):
    """Caller holds MODEL_LOCK across selection and inference."""
    global MODEL, ACTIVE_MODEL_NAME
    if MODEL is None or ACTIVE_MODEL_NAME != model_name:
        logging.info("Lade Rerank-Modell: %s", model_name)
        try:
            from sentence_transformers import CrossEncoder
            candidate = CrossEncoder(model_name, trust_remote_code=False)
        except Exception as error:
            logging.exception("Modell konnte nicht geladen werden: %s", model_name)
            raise RuntimeError("Rerank model is not available") from error
        MODEL, ACTIVE_MODEL_NAME = candidate, model_name
    return MODEL


@app.route('/rerank', methods=['POST'])
def rerank():
    data = request.get_json(silent=True)
    model_name = data.get("model", MODEL_NAME).strip()
    query = data['query']
    documents = data['documents']

    if not documents:
        return jsonify({"ranked_documents": [], "model": model_name})

    try:
        sentences = [[query, doc] for doc in documents]
        with MODEL_LOCK:
            try:
                model = load_model(model_name)
            except RuntimeError:
                raise Problem("model-unavailable", "Rerank-Modell ist nicht verf?gbar.", model=model_name)
            scores = model.predict(sentences)

        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            results.append({
                "original_index": i,
                "score": float(score),
                "text": doc
            })

        ranked_results = sorted(results, key=lambda x: x['score'], reverse=True)
        logging.info("Rerank request processed: documents=%s", len(documents))
        return jsonify({"ranked_documents": ranked_results, "model": model_name})

    except Exception as e:
        raise

@app.route('/health', methods=['GET'])
def health_check():
    with MODEL_LOCK:
        try:
            if MODEL is None:
                load_model(MODEL_NAME)
        except RuntimeError:
            raise Problem("model-unavailable", "Rerank-Modell ist nicht verf?gbar.")
        return jsonify({"status": "ok", "model_loaded": True, "model_name": ACTIVE_MODEL_NAME}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
