import os
import requests
import json
import argparse
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Konfiguration
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "phi3:mini"
CHUNK_SIZE = 1000  # Größe der Chunks in Zeichen

def split_text_into_chunks(file_path):
    """Zerlegt eine Textdatei in Chunks."""
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100
    )

    chunks = splitter.split_text(text)
    return chunks

def optimize_chunk(chunk):
    """Generiert eine Antwort basierend auf dem Kontext und der Frage über die Ollama-API."""
    system_prompt = (
        "Du bist ein Experte für römische Geschichte. Beantworte Fragen nur basierend auf den "
        "als Kontext übergebenen Dokumenten. Wenn die Frage nicht beantwortet werden kann, "
        "antworte mit 'Die Frage kann basierend auf dem gegebenen Kontext nicht beantwortet werden.'"
    )
    question = "Generiere mir bis zu fünf keywords aus dem Kontext"
    payload = {
        # "model": "llama3.1",
        "model": MODEL_NAME,
        "stream": False,
        "system": system_prompt,
        "prompt": f"Kontext:\n{chunk}\n\nFrage: {question}"
    }
    response = requests.post(OLLAMA_URL, json=payload)
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

def process_file(file_path):
    """Verarbeitet eine Datei: Zerlegen, Embeddings generieren, in DB speichern."""
    file_name = os.path.basename(file_path).split('.')[0]
    chunks = split_text_into_chunks(file_path)
    for i, chunk in enumerate(chunks):
        chunk_id = f"{file_name}-{i+1}"
        print(f"Verarbeite Chunk {chunk_id}...")
        try:
            optimized_chunk = optimize_chunk(chunk)
            print(f"Optimierter Chunk {chunk_id}:\n{optimized_chunk}\n")
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