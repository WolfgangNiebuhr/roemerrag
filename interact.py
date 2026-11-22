import sys
from rag_common.rag_results import validate_results, generation_metrics
import requests
import argparse
import numpy as np
import time
import json
CONNECT_TIMEOUT = 5
EMBED_TIMEOUT = 300
SEARCH_TIMEOUT = 60
GENERATE_TIMEOUT = 600
RERANK_TIMEOUT = 600


def post_json(url, payload, operation, timeout):
    try:
        response = requests.post(url, json=payload, timeout=(CONNECT_TIMEOUT, timeout))
    except requests.Timeout as error:
        raise RuntimeError(operation + ": Zeitlimit ueberschritten.") from error
    except requests.ConnectionError as error:
        raise RuntimeError(operation + ": Dienst nicht erreichbar.") from error
    if response.status_code != 200:
        message = operation + f": HTTP {response.status_code}"
        try:
            problem = response.json()
        except ValueError:
            problem = None
        if isinstance(problem, dict):
            for key in ("title", "detail"):
                if isinstance(problem.get(key), str):
                    message += " - " + problem[key]
            # Ollama uses {"error": "..."} rather than RFC 9457.
            if not any(isinstance(problem.get(key), str) for key in ("title", "detail")):
                if isinstance(problem.get("error"), str):
                    message += " - " + problem["error"]
            for key in ("type", "request_id"):
                if isinstance(problem.get(key), str):
                    message += f" [{key}: {problem[key]}]"
        raise RuntimeError(message)
    try:
        return response.json()
    except ValueError as error:
        raise RuntimeError(operation + ": Ungueltige JSON-Antwort.") from error


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
    data = post_json(OLLAMA_EMBEDDING_URL, payload, "Embedding", EMBED_TIMEOUT)
    if not isinstance(data, dict) or not isinstance(data.get("embedding"), list):
        raise RuntimeError("Embedding: Ungueltige Antwort.")
    try:
        raw = data["embedding"]
        if any(type(value) not in (int, float) for value in raw):
            raise ValueError()
        vec = np.array(raw, dtype=float)
        norm = np.linalg.norm(vec)
        if vec.ndim != 1 or not vec.size or not np.isfinite(vec).all() or not np.isfinite(norm) or norm <= 0:
            raise ValueError()
        return vec / norm
    except (ValueError, TypeError, OverflowError) as error:
        raise RuntimeError("Embedding: Ungueltiger Vektor.") from error


def search_vectors(embedding, metric, key, num_results):
    """Führt eine Suche über die Vektor-API aus und gibt die besten Treffer zurück."""
    payload = {
        "vector": embedding.tolist(),
        "num_results": num_results,
        "metric": metric,
        "embedding_set_id": key
    }
    return validate_results(post_json(VECTOR_API_URL, payload, "Retrieval", SEARCH_TIMEOUT))


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
    data = post_json(OLLAMA_ANSWER_URL, payload, "Generierung", GENERATE_TIMEOUT)
    if not isinstance(data, dict) or not isinstance(data.get("response"), str):
        raise RuntimeError("Generierung: Ungueltige Antwort.")
    metrics = generation_metrics(data)
    def display(key, scale=1):
        value = metrics[key]
        return "nicht verfuegbar" if value is None else f"{value * scale:.2f}"
    return data["response"] + (
        "\n\n--- [Ausfuehrungs-Metriken] ---\n"
        f"Gesamtdauer: {display('total_duration')} s\n"
        f"Modell-Ladezeit: {display('load_duration', 1000)} ms\n"
        f"Prompt-Token: {display('prompt_tokens')}, Dauer: {display('prompt_eval_duration')} s\n"
        f"Antwort-Token: {display('answer_tokens')}, Dauer: {display('eval_duration')} s\n"
        f"Antwort-Rate: {display('answer_rate')} Token/s"
    )


def rerank_results(query, results, reranker, top_k):
    """Rerankt die Suchergebnisse """
    payload = {
        "model": reranker,
        "query": query,
        "documents": [result["chunktext"] for result in results]
    }
    body = post_json("http://localhost:5000/rerank", payload, "Reranking", RERANK_TIMEOUT)
    if not isinstance(body, dict) or not isinstance(body.get("ranked_documents"), list):
        raise RuntimeError("Reranking: Ungueltige Antwort.")
    ranked = body["ranked_documents"]
    seen = set()
    for row in ranked:
        index = row.get("original_index") if isinstance(row, dict) else None
        if type(index) is not int or not 0 <= index < len(results) or index in seen:
            raise RuntimeError("Reranking: Ungueltige Dokumentzuordnung.")
        seen.add(index)
    print(f"Reranker-Modell: {body.get('model', reranker)}")
    return [results[row["original_index"]] for row in ranked[:top_k]]


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
        raise RuntimeError("Export fehlgeschlagen: " + str(e)) from e

class GermanArgumentParser(argparse.ArgumentParser):
    """Keep argparse diagnostics local to this CLI, without global translations."""
    def error(self, message):
        translations = (
            ("the following arguments are required: ", "Folgende Pflichtparameter fehlen: "),
            ("unrecognized arguments: ", "Unbekannte Argumente: "),
            ("expected one argument", "ein Wert muss angegeben werden"),
            ("ignored explicit argument", "diese Option akzeptiert keinen Wert"),
            ("argument ", "Parameter "),
        )
        for original, translated in translations:
            message = message.replace(original, translated)
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}: Fehler: {message}\n")

    def format_usage(self):
        return super().format_usage().replace("usage: ", "Aufruf: ", 1)


def german_integer(value):
    try:
        return int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"{value!r} ist keine ganze Zahl.") from error


def metric_value(value):
    if value not in ("cosine", "euclidean"):
        raise argparse.ArgumentTypeError(f"{value!r} ist ungültig; erlaubt sind cosine und euclidean (L2-Distanz).")
    return value


def main():
    parser = GermanArgumentParser(allow_abbrev=False, description="Interaktives KI-Tool für Embedding, Suche und Antwortgenerierung.")
    parser.add_argument("--metric", type=metric_value, metavar="{cosine,euclidean}", default="cosine", help="Die zu verwendende Metrik (z.B. 'euclidean', 'cosine').")
    parser.add_argument("--embedding-set-id", "--embedding", dest="embedding", type=str, default=EMBEDDING_SET_ID, help="Die Kennung der zu verwendenden Embeddings.")
    parser.add_argument("--num_results", type=german_integer, default=5, help="Anzahl der zu suchenden Vektoren.")
    parser.add_argument("--query", type=str, required=True, help="Die Query, die verarbeitet werden soll.")
    parser.add_argument("--top_k", type=german_integer, default=6, help="Anzahl der Top-Rerank-Ergebnisse.")
    parser.add_argument("--reranker", type=str, default="cross-encoder/ms-marco-MiniLM-L6-v2", help="Zu verwendendes Reranker-Modell")

    args = parser.parse_args()

    if not 1 <= args.num_results <= 100:
        parser.error(f"--num_results: {args.num_results!r} ist ungültig; erlaubt sind ganze Zahlen von 1 bis 100.")
    if args.top_k < 0:
        parser.error(f"--top_k: {args.top_k!r} ist ungültig; erwartet wird eine ganze Zahl >= 0 (0 deaktiviert Reranking).")
    for option, value in (("--query", args.query), ("--embedding-set-id/--embedding", args.embedding), ("--reranker", args.reranker)):
        if not value.strip():
            parser.error(f"{option}: erwartet wird ein nichtleerer Text.")

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
        results = validate_results(search_vectors(embedding, metric, embedding_key, num_results))
        results = [row for row in results if row["chunktext"].strip()]
        if not results:
            print("Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden. (no_context)")
            return 0

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


        if not context.strip():
            print("Keine verwertbaren Dokumente nach Reranking. (no_context)")
            return 0

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

        return 0
    except Exception as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
