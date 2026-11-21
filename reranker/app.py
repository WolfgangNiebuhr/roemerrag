from flask import Flask, request, jsonify
import os
import logging
from threading import Lock

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

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
    if not isinstance(data, dict) or 'query' not in data or 'documents' not in data:
        return jsonify({"error": "Ungültiges Request-Format. Erwartet 'query' und 'documents'."}), 400

    model_name = data.get("model", MODEL_NAME)
    if not isinstance(model_name, str) or not model_name.strip():
        return jsonify({"error": "model muss ein nichtleerer String sein"}), 400
    model_name = model_name.strip()
    query = data['query']
    documents = data['documents']

    if not isinstance(query, str) or not isinstance(documents, list) or not all(isinstance(doc, str) for doc in documents):
        return jsonify({"error": "'query' muss ein String und 'documents' eine Liste sein."}), 400

    if not documents:
        return jsonify({"ranked_documents": [], "model": model_name})

    try:
        sentences = [[query, doc] for doc in documents]
        with MODEL_LOCK:
            try:
                model = load_model(model_name)
            except RuntimeError:
                return jsonify({"error": "Rerank model is not available. Check server logs for details.", "model": model_name}), 503
            scores = model.predict(sentences)

        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            results.append({
                "original_index": i,
                "score": float(score),
                "text": doc
            })

        ranked_results = sorted(results, key=lambda x: x['score'], reverse=True)
        logging.info(f"Rerank-Anfrage verarbeitet. Query: '{query}', Dokumente: {len(documents)}")
        return jsonify({"ranked_documents": ranked_results, "model": model_name})

    except Exception as e:
        logging.error(f"Fehler beim Reranking: {e}", exc_info=True)
        return jsonify({"error": f"Interner Serverfehler beim Reranking: {e}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    with MODEL_LOCK:
        try:
            if MODEL is None:
                load_model(MODEL_NAME)
        except RuntimeError:
            return jsonify({"status": "unavailable", "model_loaded": False, "model_name": MODEL_NAME}), 503
        return jsonify({"status": "ok", "model_loaded": True, "model_name": ACTIVE_MODEL_NAME}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
