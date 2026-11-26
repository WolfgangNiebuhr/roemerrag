"""HTTP transport shared by the command-line clients."""
import os

import requests

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
