# Kapselt die Ollama-Chat-Anfragen des Keywordpfads.

import requests
import logging
import time

# Konfiguration
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_HOST}/api/chat"
OLLAMA_MODEL = "gemma3:4b"

# Sendet die Chat-Anfrage und wiederholt sie bei einer Ratenbegrenzung.
def call_ollama_gateway(chunk, system_prompt, query):
    """
    Sendet messages an Ollama /api/chat mit dem konfigurierten lokalen Modell.
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
