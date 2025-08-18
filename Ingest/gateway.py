
import requests
import logging
import time
import json
import os

# Konfiguration
GATEWAY_URL = "https://aigateway.api.dev.datev.de/datev/v1/openai/deployments/gpt-4o/chat/completions"

OLLAMA_HOST = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_MODEL = "phi3:mini"

def _headers():
    return {
        'X-Datev-Client-Id': os.getenv("DATEV_CLIENT_ID"),
        'X-Datev-Client-Secret': os.getenv("DATEV_CLIENT_SECRET"),
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def call_ai_gateway(chunk, system_prompt, query):
    retries = [0, 0.2, 0.4]  # Sekunden: sofort, 200ms, 400ms

    for attempt, wait in enumerate(retries):
        if wait > 0:
            time.sleep(wait)
        response = requests.post(
            GATEWAY_URL,
            headers=_headers(),
            data=json.dumps({"messages": [{"role": "system", "content": system_prompt},
                                          {"role": "user", "content": query}]})
        )
        print("Rohantwort der API:", response.text)
        if response.status_code == 429 and attempt < len(retries) - 1:
            print("Retrying after rate limit exceeded...")
            continue  # Nächster Versuch nach Wartezeit
        elif response.status_code != 200:
            raise Exception(f"Fehler bei der Antwortgenerierung: {response.text}")
        else:
            break  # Erfolgreich, Schleife verlassen
    return response

def call_ollama_gateway(chunk, system_prompt, query):
    """
    Sendet messages an Ollama /api/chat mit dem Modell 'llama2'.
    Behält Retries (429) und Fehlerbehandlung aus der bisherigen Funktion bei.
    Gibt ein requests.Response zurück (wie zuvor).
    """
    retries = [0, 0.2, 0.4]  # Sekunden: sofort, 200ms, 400ms

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        # Bei Bedarf kannst du hier Streaming aktivieren:
        "stream": False,
        # Optionale Generierungsoptionen:
        "options": {
            "temperature": 0.0
        }
    }

    for attempt, wait in enumerate(retries):
        if wait > 0:
            time.sleep(wait)

        # Ollama benötigt keinen API-Key; json= setzt automatisch Content-Type
        response = requests.post(
            OLLAMA_CHAT_URL,
            json=payload,
            timeout=120
        )

        print("Rohantwort der API:", response.text)

        if response.status_code == 429 and attempt < len(retries) - 1:
            logging.info(f"Retry {attempt+1} nach Rate Limit für Chunk.")
            print("Retrying after rate limit exceeded...")
            continue
        elif response.status_code != 200:
            raise Exception(
                f"Fehler bei der Antwortgenerierung: {response.status_code}\n{query}\n\n{response.text}"
            )
        else:
            break  # Erfolgreich, Schleife verlassen

    return response
