import os
import requests
import json
import argparse
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Konfiguration
OLLAMA_URL = "http://localhost:11434/api/embeddings"
VECTOR_API_URL = "http://localhost:5500/vectors"
MODEL_NAME = "snowflake-arctic-embed2"
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

def store_vector_in_db(chunk_id, vector, chunk):
    """Speichert einen Chunk mit Embedding in der Vektor-Datenbank."""
    payload = {
        "chunk_id": chunk_id,
        "embedding": MODEL_NAME,  # Beispiel-Embedding-Name
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
            embedding = generate_embedding(chunk)
            store_vector_in_db(chunk_id, embedding.tolist(), chunk, metadata=f"Chunk {i+1} von Datei {file_name}")
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