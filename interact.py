import sys
from rag_common.rag_results import validate_results
import requests
import argparse
import json
import os
CONNECT_TIMEOUT = float(os.getenv("RAG_CONNECT_TIMEOUT", "5"))
REQUEST_TIMEOUT = float(os.getenv("RAG_CLI_TIMEOUT", "1800"))


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


from rag.embedding_config import EMBEDDING_SET_ID, ANSWER_MODEL
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:5600/process")
ANSWER_MODEL_NAME = ANSWER_MODEL


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


def seconds(value):
    """API durations already use seconds; preserve missing measurements."""
    return "nicht verfuegbar" if value is None else f"{value:.2f} s"


def main():
    parser = GermanArgumentParser(allow_abbrev=False, description="Interaktives KI-Tool für Embedding, Suche und Antwortgenerierung.")
    parser.add_argument("--metric", type=metric_value, metavar="{cosine,euclidean}", default="cosine", help="Die zu verwendende Metrik (z.B. 'euclidean', 'cosine').")
    parser.add_argument("--embedding-set-id", "--embedding", dest="embedding", type=str, default=EMBEDDING_SET_ID, help="Die Kennung der zu verwendenden Embeddings.")
    parser.add_argument("--num_results", type=german_integer, default=5, help="Anzahl der zu suchenden Vektoren.")
    parser.add_argument("--query", type=str, required=True, help="Die Query, die verarbeitet werden soll.")
    parser.add_argument("--top_k", type=german_integer, default=6, help="Anzahl der Top-Rerank-Ergebnisse.")
    parser.add_argument("--reranker", type=str, default="cross-encoder/ms-marco-MiniLM-L6-v2", help="Zu verwendendes Reranker-Modell")
    parser.add_argument("--answer-model", default=ANSWER_MODEL_NAME, help="Antwortmodell")

    args = parser.parse_args()

    if not 1 <= args.num_results <= 100:
        parser.error(f"--num_results: {args.num_results!r} ist ungültig; erlaubt sind ganze Zahlen von 1 bis 100.")
    if args.top_k < 0:
        parser.error(f"--top_k: {args.top_k!r} ist ungültig; erwartet wird eine ganze Zahl >= 0 (0 deaktiviert Reranking).")
    for option, value in (("--answer-model", args.answer_model), ("--query", args.query), ("--embedding-set-id/--embedding", args.embedding), ("--reranker", args.reranker)):
        if not value.strip():
            parser.error(f"{option}: erwartet wird ein nichtleerer Text.")

    try:
        body = post_json(RAG_API_URL, {
            "query": args.query, "embedding_set_id": args.embedding,
            "metric": args.metric, "num_results": args.num_results,
            "top_k": args.top_k, "reranker": args.reranker,
            "answer_model": args.answer_model}, "RAG", REQUEST_TIMEOUT)
        if not isinstance(body, dict) or body.get("status") not in ("ok", "no_context") or not isinstance(body.get("response"), str):
            raise RuntimeError("RAG: Ungueltige Antwort.")
        retrieved = validate_results(body.get("retrieved_results"))
        selected = validate_results(body.get("selected_results"))
        print("Frage:", args.query)
        timings = body.get("timings") or {}
        print("\nRetrieval")
        print("Embedding-Laufzeit:", seconds(timings.get("embedding_duration")))
        print("Retrieval-Laufzeit:", seconds(timings.get("retrieval_duration")))
        print("Gefundene Chunks:")
        for index, row in enumerate(retrieved, 1):
            print(f"{index}. {row['chunk_id']}")
        if body["status"] == "ok":
            print()
            export_results(args.query, retrieved)

        print("\nReranking")
        reranking = body.get("reranking")
        if reranking:
            print("Modell:", reranking["model"])
            print("Laufzeit:", seconds(reranking.get("duration")))
            print("Ausgewaehlte Chunks:")
            for index, row in enumerate(selected, 1):
                print(f"{index}. {row['chunk_id']}")
        else:
            print("Deaktiviert." if args.top_k == 0 else "Nicht ausgefuehrt (kein Kontext).")

        print("\nAntwortgenerierung")
        print("Modell:", args.answer_model)
        print("\nAntwort:")
        print(body["response"])
        print("\nRAG-Pipeline-Gesamtdauer:", seconds(timings.get("pipeline_duration")))
        if body["status"] == "no_context":
            print("\nKeine Generierung (no_context).")
            return 0
        metrics = body.get("metrics") or {}
        print("\nLaufzeiten:")
        for key, label in (("generation_duration", "Generierungsdauer"), ("load_duration", "Modell-Ladezeit"),
                           ("prompt_eval_duration", "Prompt-Verarbeitung"), ("eval_duration", "Antwortgenerierung")):
            value = metrics.get(key, metrics.get("total_duration")) if key == "generation_duration" else metrics.get(key)
            print(f"{label}: {seconds(value)}")
        print("\nToken:")
        for key, label in (("prompt_tokens", "Prompt"), ("answer_tokens", "Antwort")):
            value = metrics.get(key)
            print(f"{label}: {value if value is not None else 'nicht verfuegbar'}")
        rate = metrics.get("answer_rate")
        print("Antwort-Rate:", f"{rate:.2f} Token/s" if rate is not None else "nicht verfuegbar")
        return 0
    except Exception as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
