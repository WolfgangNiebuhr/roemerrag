import os
import requests
import json
import argparse
import logging
import numpy as np
from datetime import datetime
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Konfiguration
OLLAMA_URL = "http://localhost:11434/api/embeddings"
VECTOR_API_URL = "http://localhost:5500/chunk"
GATEWAY_URL = "https://aigateway.api.dev.datev.de/datev/v1/openai/deployments/gpt-4o/chat/completions"

MODEL_NAME = "snowflake-arctic-embed2"
EMBEDDING_VERSION = "-v2"  # Version des Embeddings
CHUNK_SIZE = 1000  # Größe der Chunks in Zeichen
OVERLAP = 150  # Überlappung zwischen den Chunks

def setup_logging(file_path):
    base = os.path.basename(file_path).split('.')[0]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"{base}_{timestamp}.log"
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.info(f"Starte Import für Datei: {file_path}")


def split_text_into_chunks(file_path):
    """Zerlegt eine Textdatei in Chunks."""
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=OVERLAP,
        separators=["\n\n", ".\n", ". "]
    )

    chunks = splitter.split_text(text)
    return chunks

def _headers():
    return {
        'X-Datev-Client-Id': os.getenv("DATEV_CLIENT_ID"),
        'X-Datev-Client-Secret': os.getenv("DATEV_CLIENT_SECRET"),
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def call_gateway(chunk, system_prompt, query):
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
         # print("Rohantwort der API:", response.text)
         if response.status_code == 429 and attempt < len(retries) - 1:
             logging.info(f"Retry {attempt+1} nach Rate Limit für Chunk.")
             print("Retrying after rate limit exceeded...")
             continue  # Nächster Versuch nach Wartezeit
         elif response.status_code != 200:
             raise Exception(f"Fehler bei der Antwortgenerierung: {response.status_code}  \n{query}\n\n{response.text}")
         else:
             break  # Erfolgreich, Schleife verlassen
    return response

def get_keyword_question(chunk):
    chunk_len = len(chunk)
    fifth = CHUNK_SIZE // 5
    if chunk_len < fifth:
        n_keywords = 1
    elif chunk_len < 2 * fifth:
        n_keywords = 2
    elif chunk_len < 3 * fifth:
        n_keywords = 3
    elif chunk_len < 4 * fifth:
        n_keywords = 4
    else:
        n_keywords = 5

    if n_keywords == 1:
        question = "Generiere mir ein keyword aus dem Kontext. Das keyword soll prägnant, sachlich und inhaltlich beschreibend sein."
    else:
        question = f"Generiere mir {n_keywords} keywords aus dem Kontext. Die keywords sollen prägnant, sachlich und inhaltlich beschreibend sein. Die keywords sollen als kommaseparierte Liste ausgegeben werden."
    return question

def get_keywords(chunk):
    """Generiert eine Antwort basierend auf dem Kontext und der Frage über die Ollama-API."""
    system_prompt = (
        "Du bist ein Experte für römische Geschichte. Beantworte Fragen nur basierend auf den als Kontext übergebenen Dokumenten. "
        "Die Dokumente können gewaltbezogene oder gesellschaftskritische Begriffe enthalten, die aus historischen Quellen stammen. "
        "Bitte antworte stets neutral, sachlich und ohne Bewertung. Wenn die Frage nicht beantwortet werden kann, antworte mit "
        "'Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.'"
    )
    question = get_keyword_question(chunk)

    query = f"Kontext:\n{chunk}\n\nFrage: {question}"

    response = call_gateway(chunk, system_prompt, query)

    data = response.json()

    answer_tokens = data["usage"]["completion_tokens"]
    prompt_tokens = data["usage"]["prompt_tokens"]

    metrics_report = (
        f"\n\n--- [Ausführungs-Metriken] ---\n"
        f"Prompt-Token:       {prompt_tokens} Token\n"
        f"Antwort-Token:      {answer_tokens} Token\n"
    )

    # Sicherstellen, dass das content-Feld existiert (kommt vor wenn Antworten gefiltert werden wg zb violence)
    answer = ""
    try:
        answer = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        logging.warning("Keine Keywords generiert:\n"+query+"\n\n")
        answer = ""


    return answer, metrics_report, question


def generate_embedding(chunk):
    """Erzeugt ein Embedding für einen Text-Chunk über die Ollama-API."""
    payload = {
        "model": MODEL_NAME,
        "prompt": chunk
    }
    response = requests.post(OLLAMA_URL, json=payload)
    if response.status_code == 200:
        vec = np.array(response.json().get("embedding"))
        vec = vec / np.linalg.norm(vec)  # Normalisierung des Embeddings
        return vec
    else:
        raise Exception(f"Fehler beim Abrufen des Embeddings: {response.text}")

def store_vector_in_db(chunk_id, embedding, vector, chunk):
    """Speichert einen Chunk mit Embedding in der Vektor-Datenbank."""
    payload = {
        "chunk_id": chunk_id,
        "embedding": embedding,  # Beispiel-Embedding-Name
        "vector": vector,
        "metadata": chunk
    }
    response = requests.post(VECTOR_API_URL, json=payload)
    if response.status_code == 201:
        print(f"Chunk {chunk_id} erfolgreich gespeichert.")
    else:
        raise Exception(f"Fehler beim Speichern in der Vektor-DB: {response.text}")

def process_file(file_path):
    """Verarbeitet eine Datei: Zerlegen, Embeddings generieren, in DB speichern."""
    file_name = os.path.basename(file_path).split('.')[0]
    chunks = split_text_into_chunks(file_path)
    for i, chunk in enumerate(chunks):
        chunk_id = f"{file_name}-{i+1}"
        print(f"Verarbeite Chunk {chunk_id}...")
        try:
            keywords, metrics, question = get_keywords(chunk)
            chunk = keywords+"\n"+chunk
            vector = generate_embedding(chunk)
            store_vector_in_db(chunk_id, MODEL_NAME+EMBEDDING_VERSION, vector.tolist(), chunk)
        except Exception as e:
            print(f"Fehler bei Chunk {chunk_id}: {e}")
            logging.error(f"Fehler bei Chunk {chunk_id}: {e}", exc_info=True)

if __name__ == "__main__":
    # Argumente parsen
    parser = argparse.ArgumentParser(description="Importiere eine Datei in die Vektor-Datenbank.")
    parser.add_argument("--file", type=str, default="pg3060.txt", help="Pfad zur Import-Datei")
    args = parser.parse_args()

    # Datei-Pfad ausgeben
    file_path = args.file
    setup_logging(file_path)
    print(f"Importiere Datei: {file_path}")

    # Datei verarbeiten
    process_file(file_path)