from sentence_transformers import CrossEncoder
import os
import logging
import json
import argparse
import time

# Konfiguriere das Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Umgebungsvariable für das Modell. Standardmäßig ein kleines, effizientes Modell.
# MODEL_NAME = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L6-v2")
# MODEL_NAME = os.getenv("RERANK_MODEL", "jinaai/jina-reranker-v2-base-multilingual")
MODEL_NAME = os.getenv("RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

def load_model():
    """Lädt das Reranker-Modell."""
    logging.info(f"Lade Rerank-Modell: {MODEL_NAME}...")
    try:
        model = CrossEncoder(MODEL_NAME, trust_remote_code=True)
        logging.info("Modell erfolgreich geladen.")
        return model
    except Exception as e:
        logging.error(f"Fehler beim Laden des Modells {MODEL_NAME}: {e}")
        raise RuntimeError(f"Modell konnte nicht geladen werden: {MODEL_NAME}") from e

def rerank(query, documents, model):
    """Rerankt Dokumente basierend auf einer Query."""
    if not isinstance(query, str) or not isinstance(documents, list):
        raise ValueError("'query' muss ein String und 'documents' eine Liste sein.")
    if not documents:
        return []
    # Paare aus Query und Dokumenten erstellen
    sentences = [[query, doc] for doc in documents]
    # Scores berechnen
    scores = model.predict(sentences)
    # Dokumente zusammen mit ihren ursprünglichen Indizes und Scores speichern
    results = []
    for i, (doc, score) in enumerate(zip(documents, scores)):
        results.append({
            "original_index": i,
            "score": float(score),
            "text": doc
        })
    # Ergebnisse nach Score absteigend sortieren
    ranked_results = sorted(results, key=lambda x: x['score'], reverse=True)
    return ranked_results

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Reranker Demo")
    parser.add_argument('--input', type=str, help='Pfad zu einer JSON-Datei mit query und passages')
    args = parser.parse_args()

    if args.input:
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)
        query = data.get("query")
        passages = data.get("passages")
        if not isinstance(query, str) or not isinstance(passages, list):
            raise ValueError("Die Eingabedatei muss ein Feld 'query' (String) und 'passages' (Liste) enthalten.")
    else:
        # Beispiel-Daten wie in der curl-Anfrage
        query = "Wie funktioniert maschinelles Lernen?"
        passages = [
            "Maschinelles Lernen ist ein Teilbereich der künstlichen Intelligenz, der Computern das Lernen aus Daten ermöglicht.",
            "Deep Learning ist eine spezialisierte Form des maschinellen Lernens, die neuronale Netze mit vielen Schichten verwendet.",
            "Das Training eines Modells beinhaltet die Anpassung von Parametern, um Vorhersagen zu verbessern.",
            "Quantencomputing nutzt Prinzipien der Quantenmechanik für die Datenverarbeitung."
        ]
    model = load_model()
    start = time.time()
    ranked_documents = rerank(query, passages, model)
    duration = time.time() - start
    print(f"Laufzeit von rerank_results: {duration:.3f} Sekunden")
    print(json.dumps({"ranked_documents": ranked_documents}, ensure_ascii=False, indent=2))
