"""Analyze retrieval and generation through the RAG evaluation API."""
import argparse
import json
import os
import sys

from rag_common.cli_http import REQUEST_TIMEOUT, post_json


GOLDCHUNK = (
    "Vesta, Italus, Ackerbau, Stammsagen, Volk     "
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
)


def print_distances(values):
    for field, label in (("cosine_similarity", "Cosinus-Ähnlichkeit"),
                         ("euclidean_distance", "Euklidischer Abstand")):
        value = values[field]
        print(f"  {label}: {'nicht verfügbar' if value is None else value}")


def main(argv=None):
    parser = argparse.ArgumentParser(allow_abbrev=False, description="RAG-Retrieval und Antwort analysieren.")
    parser.add_argument("--query", required=True, help="Zu untersuchende Frage.")
    parser.add_argument("--metric", choices=("cosine", "euclidean"), default="cosine")
    parser.add_argument("--num_results", type=int, default=5, help="Anzahl der Suchtreffer (1–100).")
    parser.add_argument("--embedding-set-id", help="Zu durchsuchendes Embedding-Set.")
    parser.add_argument("--answer-model", help="Modell für die Antwortgenerierung.")
    parser.add_argument("--compare-gold", action="store_true", help="Die Frage mit dem hinterlegten Gold-Chunk vergleichen.")
    args = parser.parse_args(argv)
    if not 1 <= args.num_results <= 100:
        parser.error("--num_results erwartet eine ganze Zahl zwischen 1 und 100.")
    for option in ("query", "embedding_set_id", "answer_model"):
        value = getattr(args, option)
        if value is not None and not value.strip():
            parser.error(f"--{option.replace('_', '-')} erwartet einen nichtleeren Text.")

    base_url = os.getenv("RAG_API_BASE_URL", "http://127.0.0.1:5600").rstrip("/")
    payload = {"query": args.query, "metric": args.metric, "num_results": args.num_results, "include_distances": True}
    if args.embedding_set_id is not None:
        payload["embedding_set_id"] = args.embedding_set_id
    if args.answer_model is not None:
        payload["answer_model"] = args.answer_model
    if args.compare_gold:
        payload["reference_text"] = GOLDCHUNK

    try:
        retrieved = post_json(f"{base_url}/evaluate/retrieve", payload, "Retrieval", REQUEST_TIMEOUT)
        diagnostics = retrieved["diagnostics"]
        next_request = retrieved["next_request"]
        if not isinstance(diagnostics["hits"], list) or not isinstance(next_request, dict):
            raise RuntimeError("Retrieval: Ungültige Antwort.")

        print("Frage:", args.query)
        if args.compare_gold:
            print("\nGold-Chunk:")
            print_distances(diagnostics["reference"])
        print(f"\nSuchtreffer nach {args.metric}:")
        for index, hit in enumerate(diagnostics["hits"], 1):
            print(f"{index}. {hit['chunk_id']} (Rankingdistanz: {hit['distance']})")
            print_distances(hit)

        generated = post_json(f"{base_url}/evaluate/generate", next_request, "Generierung", REQUEST_TIMEOUT)
        if generated["status"] not in ("ok", "no_context") or not isinstance(generated["response"], str):
            raise RuntimeError("Generierung: Ungültige Antwort.")
        print("\nAntwort:")
        print(generated["response"])
        if generated["metrics"] is not None:
            print(json.dumps(generated["metrics"], ensure_ascii=False))
        return 0
    except (KeyError, TypeError):
        print("Fehler: Unvollständige oder ungültige RAG-Antwort.", file=sys.stderr)
        return 1
    except RuntimeError as error:
        print(f"Fehler: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
