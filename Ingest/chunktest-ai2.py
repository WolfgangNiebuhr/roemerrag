import os
import argparse
from chunking import split_text_into_chunks
from keywords import get_keywords_ollama

CHUNK_SIZE = 1000  # Größe der Chunks in Zeichen
OVERLAP = 150


def process_file(file_path):
    """Verarbeitet eine Datei: Zerlegen, Embeddings generieren, in DB speichern."""
    file_name = os.path.basename(file_path).split('.')[0]
    chunks = split_text_into_chunks(file_path, CHUNK_SIZE, OVERLAP)
    for i, chunk in enumerate(chunks):
        if i >= 100:
            break
        chunk_id = f"{file_name}-{i+1}"
        print(f"Verarbeite Chunk {chunk_id}...")
        try:
            keywords, metrics, question = get_keywords_ollama(chunk)
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