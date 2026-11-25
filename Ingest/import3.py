# Importiert Textdateien mit Keyword-Anreicherung und normalisierten Embeddings.

import os
import requests
import argparse
import logging
import numpy as np
from datetime import datetime
if __package__:
    from .utils.keywords import get_keywords_ollama
    from .utils.chunking import split_text_into_chunks
else:
    from utils.keywords import get_keywords_ollama
    from utils.chunking import split_text_into_chunks

# Konfiguration
OLLAMA_URL = "http://localhost:11434/api/embeddings"
VECTOR_API_URL = "http://localhost:5500/vectors"


# Support direct execution from the project root and IDE script launches.
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rag.embedding_config import EMBEDDING_MODEL, EMBEDDING_SET_ID
MODEL_NAME = EMBEDDING_MODEL
CHUNK_SIZE = 1000  # Größe der Chunks in Zeichen
OVERLAP = 150  # Überlappung zwischen den Chunks

# Konfiguriert eine datierte Logdatei pro Quelldatei.
def setup_logging(file_path):
    base = Path(file_path).stem
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_filename = f"{base}_{timestamp}.log"
    logging.basicConfig(
        filename=log_filename,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    logging.info(f"Starte Import für Datei: {file_path}")




# Ruft Ollama fuer einen Chunk auf und normalisiert den Vektor.
def generate_embedding(chunk):
    """Erzeugt ein Embedding für einen Text-Chunk über die Ollama-API."""
    payload = {
        "model": MODEL_NAME,
        "prompt": chunk
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=(float(os.getenv("IMPORT_CONNECT_TIMEOUT", "5")), float(os.getenv("IMPORT_EMBED_TIMEOUT", "300"))))
    if response.status_code == 200:
        vec = np.array(response.json().get("embedding"))
        vec = vec / np.linalg.norm(vec)  # Normalisierung des Embeddings
        return vec
    else:
        raise Exception(f"Fehler beim Abrufen des Embeddings: {response.text}")

# Uebergibt Chunktext und Vektor mit ihren Kennungen an die Vector-API.
def store_vector_in_db(chunk_id, embedding_set_id, vector, chunk):
    """Speichert einen Chunk mit Embedding in der Vektor-Datenbank."""
    payload = {
        "chunk_id": chunk_id,
        "embedding_set_id": embedding_set_id,
        "vector": vector,
        "chunktext": chunk
    }
    response = requests.post(VECTOR_API_URL, json=payload, timeout=(float(os.getenv("IMPORT_CONNECT_TIMEOUT", "5")), float(os.getenv("IMPORT_STORE_TIMEOUT", "60"))))
    if response.status_code == 201:
        print(f"Chunk {chunk_id} erfolgreich gespeichert.")
    else:
        raise Exception(f"Fehler beim Speichern in der Vektor-DB: {response.text}")

# Importiert die Chunks einer Datei ab der gewaehlten Startnummer.
def process_file(file_path, start):
    """Verarbeitet eine Datei: Zerlegen, Embeddings generieren, in DB speichern."""
    file_name = Path(file_path).stem
    chunks = split_text_into_chunks(file_path, CHUNK_SIZE, OVERLAP)
    for i, chunk in enumerate(chunks):
        if i+1 >= start:
            chunk_id = f"{file_name}-{i+1}"
            print(f"Verarbeite Chunk {chunk_id}...")
            try:
                keywords, metrics, question = get_keywords_ollama(chunk)
                chunk = keywords+"\n"+chunk
                vector = generate_embedding(chunk)
                store_vector_in_db(chunk_id, EMBEDDING_SET_ID, vector.tolist(), chunk)
            except Exception as e:
                print(f"Fehler bei Chunk {chunk_id}: {e}")
                logging.error(f"Fehler bei Chunk {chunk_id}: {e}", exc_info=True)

if __name__ == "__main__":
    # Argumente parsen
    parser = argparse.ArgumentParser(description="Importiere eine Datei in die Vektor-Datenbank.")
    parser.add_argument("--file", type=str, default="pg3060.txt", help="Pfad zur Import-Datei")
    parser.add_argument("--start", type=int, default=1, help="Erster chunk der embedded werden soll")
    args = parser.parse_args()

    # Datei-Pfad ausgeben
    file_path = args.file
    start = args.start
    setup_logging(file_path)
    print(f"Importiere Datei: {file_path}")

    # Datei verarbeiten
    process_file(file_path,start)