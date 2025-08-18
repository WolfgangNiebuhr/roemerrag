import os
import requests
import json
import argparse
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Konfiguration
GATEWAY_URL = "https://aigateway.api.dev.datev.de/datev/v1/openai/deployments/gpt-4o/chat/completions"

CHUNK_SIZE = 1000  # Größe der Chunks in Zeichen
OVERLAP = 150



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
         print("Rohantwort der API:", response.text)
         if response.status_code == 429 and attempt < len(retries) - 1:
             print("Retrying after rate limit exceeded...")
             continue  # Nächster Versuch nach Wartezeit
         elif response.status_code != 200:
             raise Exception(f"Fehler bei der Antwortgenerierung: {response.text}")
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
        "Du bist ein Experte für römische Geschichte. Beantworte Fragen nur basierend auf den "
        "als Kontext übergebenen Dokumenten. Wenn die Frage nicht beantwortet werden kann, "
        "antworte mit 'Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.'"
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

    answer = data["choices"][0]["message"]["content"]


    return answer, metrics_report, question

def process_file(file_path):
    """Verarbeitet eine Datei: Zerlegen, Embeddings generieren, in DB speichern."""
    file_name = os.path.basename(file_path).split('.')[0]
    chunks = split_text_into_chunks(file_path)
    for i, chunk in enumerate(chunks):
        if i >= 100:
            break
        chunk_id = f"{file_name}-{i+1}"
        print(f"Verarbeite Chunk {chunk_id}...")
        try:
            keywords, metrics, question = get_keywords(chunk)
            if keywords.strip() == "Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.":
                print(f"Chunk {chunk_id}:\n\n ******************** keine Antwort\n {question}\n{metrics}")
            else:
                print(f"Optimierter Chunk {chunk_id}:\n{keywords}\n{chunk}\n\n{metrics}")
        except Exception as e:
            print(f"Fehler bei Chunk {chunk_id}: {e}")


if __name__ == "__main__":
    # Argumente parsen
    parser = argparse.ArgumentParser(description="Importiere eine Datei in die Vektor-Datenbank.")
    parser.add_argument("--file", type=str, default="pg3060.txt", help="Pfad zur Import-Datei")
    args = parser.parse_args()

    # Datei-Pfad ausgeben
    file_path = args.file
    print(f"Importiere Datei: {file_path}")

    # Datei verarbeiten
    process_file(file_path)