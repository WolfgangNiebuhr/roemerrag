import requests
import argparse
import numpy as np
import time
import json
# Konfiguration

## Embedding
OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"
from rag.embedding_config import EMBEDDING_MODEL, EMBEDDING_SET_ID
EMBEDDING_MODEL_NAME = EMBEDDING_MODEL

## Retrieval
VECTOR_API_URL = "http://localhost:5500/search"
NUM_RESULTS = 5

## Generation
OLLAMA_ANSWER_URL = "http://localhost:11434/api/generate"
# ANSWER_MODEL_NAME = "gemma3:4b"
# ANSWER_MODEL_NAME = "phi3:mini"
ANSWER_MODEL_NAME = "gemma4:e4b"

QUERY = "Wer beherrschte die westliche Hälfte des Mittelmeeres?"

def generate_embedding(query):
    """Erzeugt ein Embedding für die vordefinierte Frage über die Ollama-API."""
    payload = {
        "model": EMBEDDING_MODEL_NAME,
        "prompt": query
    }
    response = requests.post(OLLAMA_EMBEDDING_URL, json=payload)
    if response.status_code == 200:
        # print(json.dumps(response.json(), indent=4))  # Ausgabe
        vec = np.array(response.json().get("embedding"))
        vec = vec / np.linalg.norm(vec)  # Normalisierung des Embeddings
        return vec
    else:
        raise Exception(f"Fehler beim Abrufen des Embeddings: {response.text}")

def search_vectors(embedding, metric, key, num_results):
    """Führt eine Suche über die Vektor-API aus und gibt die besten Treffer zurück."""
    payload = {
        "vector": embedding.tolist(),
        "num_results": num_results,
        "metric": metric,
        "embedding_set_id": key
    }
    response = requests.post(VECTOR_API_URL, json=payload)
    if response.status_code == 200:
        # print(json.dumps(response.json(), indent=4))  # Ausgabe der vollständigen JSON-Antwort
        results = response.json()
        # Überprüfen, ob die Antwort eine Liste ist
        if isinstance(results, list):
            return results
        else:
            raise Exception("Unerwartetes Antwortformat: Erwartet wurde eine Liste.")
    else:
        raise Exception(f"Fehler bei der Suche in der Vektor-API: {response.text}")


def generate_answer(context, question):
    """Generiert eine Antwort basierend auf dem Kontext und der Frage über die Ollama-API."""
    system_prompt = (
        "Du bist ein Experte für römische Geschichte. Beantworte Fragen nur basierend auf den "
        "als Kontext übergebenen Dokumenten. Wenn die Frage nicht beantwortet werden kann, "
        "antworte mit 'Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.'"
    )
    payload = {
        # "model": "llama3.1",
        "model": ANSWER_MODEL_NAME,
        "stream": False,
        "system": system_prompt,
        "prompt": f"Kontext:\n{context}\n\nFrage: {question}"
    }
    response = requests.post(OLLAMA_ANSWER_URL, json=payload)
    # print("Rohantwort der API:", response.text)  # Debugging-Ausgabe

    if response.status_code != 200:
        raise Exception(f"Fehler bei der Antwortgenerierung: {response.text}")

    data = response.json()
    answer = data.get("response", "Keine Antwort erhalten.")

    # Performance-Metriken extrahieren (in ns → s oder ms umrechnen)
    total_duration = data.get("total_duration", 0) / 1e9  # Sekunden
    load_duration = data.get("load_duration", 0) / 1e6    # Millisekunden
    prompt_eval_duration = data.get("prompt_eval_duration", 0) / 1e9
    eval_duration = data.get("eval_duration", 0) / 1e9

    prompt_tokens = data.get("prompt_eval_count", 0)
    answer_tokens = data.get("eval_count", 0)

    # Ausgabe formatieren
    metrics_report = (
        f"\n\n--- [Ausführungs-Metriken] ---\n"
        f"Gesamtdauer:        {total_duration:.2f} s\n"
        f"Modell-Ladezeit:    {load_duration:.2f} ms\n"
        f"Prompt-Token:       {prompt_tokens} Token, Dauer: {prompt_eval_duration:.2f} s\n"
        f"Antwort-Token:      {answer_tokens} Token, Dauer: {eval_duration:.2f} s\n"
        f"Antwort-Rate:       {answer_tokens / eval_duration:.2f} Token/s"
    )

    return answer + metrics_report

def rerank_results(query, results, reranker, top_k):
    """Rerankt die Suchergebnisse """
    payload = {
        "model": reranker,
        "query": query,
        "documents": [result["chunktext"] for result in results]
    }
    response = requests.post("http://localhost:5000/rerank", json=payload, timeout=600)

    # print("Rohantwort der Rerank-API:", response.text)  # Debugging-Ausgabe

    if response.status_code == 200:
        body = response.json()
        print(f"Reranker-Modell: {body['model']}")
        reranked = body["ranked_documents"]

        sorted_results = []
        for item in reranked[:top_k]:
            original = results[item["original_index"]]
            sorted_results.append({
                "chunktext": item["text"],
                "chunk_id": original["chunk_id"]
            })
        return sorted_results
    else:
        raise Exception(f"Fehler beim Reranking: {response.text}")


def export_results(query, results, filename="search_results.json"):
    """Exportiert Query und Suchergebnisse in eine JSON-Datei."""
    try:
        # Erstelle das Export-Datenformat
        export_data = {
            "query": query,
            "passages": [result["chunktext"] for result in results]
        }

        # Schreibe JSON-Datei mit UTF-8 Encoding und ensure_ascii=False für Sonderzeichen
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"Ergebnisse erfolgreich nach '{filename}' exportiert.")

    except Exception as e:
        print(f"Fehler beim Exportieren: {e}")

def main():
    parser = argparse.ArgumentParser(description="Interaktives KI-Tool für Embedding, Suche und Antwortgenerierung.")
    parser.add_argument("--metric", type=str, default="cosine", help="Die zu verwendende Metrik (z.B. 'euclidean', 'cosine').")
    parser.add_argument("--embedding-set-id", "--embedding", dest="embedding", type=str, default=EMBEDDING_SET_ID, help="Die Kennung der zu verwendenden Embeddings.")
    parser.add_argument("--num_results", type=int, default=5, help="Anzahl der zu suchenden Vektoren.")
    parser.add_argument("--query", type=str, required=True, help="Die Query, die verarbeitet werden soll.")
    parser.add_argument("--top_k", type=int, default=6, help="Anzahl der Top-Rerank-Ergebnisse.")
    parser.add_argument("--reranker", type=str, default="cross-encoder/ms-marco-MiniLM-L6-v2", help="Zu verwendendes Reranker-Modell")

    args = parser.parse_args()

    metric = args.metric
    num_results = args.num_results
    top_k = args.top_k
    query = args.query
    embedding_key = args.embedding
    reranker = args.reranker

    try:
        print("Frage:", query)
        print("Generiere Embedding für die Frage...")
        embedding = generate_embedding(query)

        # -------------------------

        print(f"Führe {metric}-Suche über die Vektor-API aus...")
        results = search_vectors(embedding, metric, embedding_key, num_results)

        export_results(query, results)

        # IDs für die Aufzählung extrahieren
        retrieved_ids = [result["chunk_id"] for result in results]

        if top_k > 0:
            start = time.time()
            results = rerank_results(query, results, reranker, top_k)
            duration = time.time() - start
            print(f"Laufzeit von rerank_results: {duration:.3f} Sekunden")

            reranked_ids = [result["chunk_id"] for result in results]
            context = "\n".join([result["chunktext"] for result in results])
        else:
            context = "\n".join([result["chunktext"] for result in results])


        # Antwortgenerierung
        print("\nGeneriere Antwort basierend auf den gefundenen Texten...")
        answer = generate_answer(context, query)
        print("\nAntwort:")
        print(answer)

        # Aufzählung der Chunks ausgeben
        print("\nfound Chunks:")
        for i, element in enumerate(retrieved_ids   , start=1):
             print(f"{i}. {element}")

        if top_k > 0:
            print("\nreranked Chunks:")
            for i, element in enumerate(reranked_ids   , start=1):
                print(f"{i}. {element}")

    except Exception as e:
        print(f"Fehler: {e}")


if __name__ == "__main__":
    main()
