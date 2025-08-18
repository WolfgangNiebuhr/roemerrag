import requests
import json
import argparse

from scipy.spatial.distance import cosine
import numpy as np

# Konfiguration

## Embedding
OLLAMA_EMBEDDING_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL_NAME = "snowflake-arctic-embed2"

## Retrieval
VECTOR_API_URL = "http://localhost:5500/search"
NUM_RESULTS = 5

## Generation
OLLAMA_ANSWER_URL = "http://localhost:11434/api/generate"
ANSWER_MODEL_NAME = "phi3:mini"

QUERY = "Wer war König Italus?"

GOLDCHUNK = "Vesta, Italus, Ackerbau, Stammsagen, Volk     "
" .                                                                      "
" Das Haus und der feste Herd, den der Ackerbauer sich gruendet anstatt  "
" der leichten Huette und der unsteten Feuerstelle des Hirten, werden im "
" geistigen Gebiete dargestellt und idealisiert in der Goettin Vesta oder "
" Εστία, fast der einzigen, die nicht indogermanisch und doch beiden     "
" Nationen von Haus aus gemein ist. Eine der aeltesten italischen        "
" Stammsagen legt dem Koenig Italus, oder, wie die Italiker gesprochen   "
" haben muessen, Vitalus oder Vitulus, die Ueberfuehrung des Volkes vom  "
" Hirtenleben zum Ackerbau bei und knuepft sinnig die urspruengliche     "
" italische Gesetzgebung daran; nur eine andere Wendung davon ist es,    "
" wenn die samnitische Stammsage zum Fuehrer der Urkolonien den          "
" Ackerstier macht oder wenn die aeltesten latinischen Volksnamen das    "
" Volk bezeichnen als Schnitter (Siculi, auch wohl Sicani) oder als "
" Feldarbeiter (Opsci)"


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

def search_vectors(embedding, metric, num_results):
    """Führt eine Suche über die Vektor-API aus und gibt die besten Treffer als Objekte zurück."""
    payload = {
        "vector": embedding.tolist(),  # Konvertierung in eine Liste für die JSON-Serialisierung
        "num_results": num_results,
        "metric": metric
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

def main():
    parser = argparse.ArgumentParser(description="Interaktives KI-Tool für Embedding, Suche und Antwortgenerierung.")
    parser.add_argument("--metric", type=str, default="cosine", help="Die zu verwendende Metrik (z.B. 'euclidean', 'cosine').")
    parser.add_argument("--num_results", type=int, default=5, help="Anzahl der zu suchenden Vektoren.")
    parser.add_argument("--query", type=str, required=True, help="Die Query, die verarbeitet werden soll.")
    args = parser.parse_args()

    metric = args.metric
    num_results = args.num_results
    query = args.query

    try:
        print("Frage:", query)
        print("Generiere Embedding für die Frage...")
        embedvec = generate_embedding(query)


        goldvec = generate_embedding(GOLDCHUNK)


        similarity = 1 - cosine(embedvec, goldvec)
        print(f"Cosine-Similarity Zwischen Gold-Chunk und Frage: {similarity}")
        dist = np.linalg.norm(embedvec -goldvec)
        print(f"Euklidischer Abstand Zwischen Gold-Chunk und Frage: {dist}")


        # -------------------------

        print(f"Führe {metric}-Suche über die Vektor-API aus...")
        results = search_vectors(embedvec, metric, num_results)
        # print(results)

        # Kontext aus den Textfeldern der Suchergebnisse erstellen
        context = "\n".join([result["metadata"] for result in results])
        # print(context)

        # Chunk-IDs für die Aufzählung extrahieren
        chunk_ids = [result["chunk_id"] for result in results]
        chunk_metric = [result["distance"] for result in results]
        # print(chunk_ids)
        chunk_dist = [1-cosine(embedvec, np.squeeze(np.array(json.loads(result["vector"])))) for result in results]
        # print(chunk_dist)

        # Antwortgenerierung
        print("\nGeneriere Antwort basierend auf den gefundenen Texten...")
        answer = generate_answer(context, query)
        print("\nAntwort:")
        print(answer)

        # Aufzählung der Chunks ausgeben
        print("\nbenutzte Chunks:")
        for i, chunk_id in enumerate(chunk_ids, start=1):
             print(f"{i}. {chunk_id} "+str(chunk_metric[i-1]))

        print("\nCosinus-Ähnlichkeiten:")
        for i, dist in enumerate(chunk_dist, start=1):
            print(f"{i}. {dist}")

        chunk_dist = [np.linalg.norm(embedvec - np.squeeze(np.array(json.loads(result["vector"])))) for result in results]
        print("\nEuklidischer Abstand:")
        for i, dist in enumerate(chunk_dist, start=1):
            print(f"{i}. {dist}")

    except Exception as e:
        print(f"Fehler: {e}")


if __name__ == "__main__":
    main()
