import requests
import json
import argparse

from scipy.spatial.distance import cosine
import numpy as np

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


# Use the same provider adapters, validation and prompt as the RAG API.
from rag.app import generate_embedding, generate_answer as _generate_answer, search_vectors as _search_vectors
from rag.embedding_config import EMBEDDING_SET_ID


def search_vectors(embedding, metric, num_results):
    return _search_vectors(embedding, EMBEDDING_SET_ID, metric, num_results)


def generate_answer(context, question):
    answer, metrics = _generate_answer(context, question)
    return answer + "\n" + json.dumps(metrics, ensure_ascii=False)


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
        context = "\n".join([result["chunktext"] for result in results])
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
