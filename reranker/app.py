from flask import Flask, request, jsonify
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

MODEL_NAME = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")
MODEL = None

def load_model():
    global MODEL
    if MODEL is None:
        logging.info(f"Lade Rerank-Modell: {MODEL_NAME}...")
        try:
            from sentence_transformers import CrossEncoder
            MODEL = CrossEncoder(MODEL_NAME, trust_remote_code=True)
            logging.info("Modell erfolgreich geladen.")
        except Exception as e:
            logging.error(f"Fehler beim Laden des Modells {MODEL_NAME}: {e}")
            raise RuntimeError(f"Modell konnte nicht geladen werden: {MODEL_NAME}") from e

@app.before_request
def check_model_loaded():
    if MODEL is None:
        try:
            load_model()
        except RuntimeError:
            return jsonify({"error": "Rerank model is not available. Check server logs for details."}), 503

@app.route('/rerank', methods=['POST'])
def rerank():
    data = request.get_json()
    if not data or 'query' not in data or 'documents' not in data:
        return jsonify({"error": "Ungültiges Request-Format. Erwartet 'query' und 'documents'."}), 400

    query = data['query']
    documents = data['documents']

    if not isinstance(query, str) or not isinstance(documents, list):
        return jsonify({"error": "'query' muss ein String und 'documents' eine Liste sein."}), 400

    if not documents:
        return jsonify({"ranked_documents": []})

    try:
        sentences = [[query, doc] for doc in documents]
        scores = MODEL.predict(sentences)

        results = []
        for i, (doc, score) in enumerate(zip(documents, scores)):
            results.append({
                "original_index": i,
                "score": float(score),
                "text": doc
            })

        ranked_results = sorted(results, key=lambda x: x['score'], reverse=True)
        logging.info(f"Rerank-Anfrage verarbeitet. Query: '{query}', Dokumente: {len(documents)}")
        return jsonify({"ranked_documents": ranked_results})

    except Exception as e:
        logging.error(f"Fehler beim Reranking: {e}", exc_info=True)
        return jsonify({"error": f"Interner Serverfehler beim Reranking: {e}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    if MODEL is not None:
        return jsonify({"status": "ok", "model_loaded": True, "model_name": MODEL_NAME}), 200
    else:
        return jsonify({"status": "initializing", "model_loaded": False, "model_name": MODEL_NAME}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
