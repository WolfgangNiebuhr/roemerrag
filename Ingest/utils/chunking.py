# Stellt die gemeinsame rekursive Textzerlegung fuer den Dokumentimport bereit.

from langchain.text_splitter import RecursiveCharacterTextSplitter


# Zerlegt Text anhand der angegebenen Trennzeichen, Groesse und Ueberlappung.
def split_recursive(text, size, overlap, *, separators=None):
    if separators is None:
        separators = ["\n\n", ".\n", ". "]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=separators,
    )
    return splitter.split_text(text)


# Liest eine UTF-8-Datei und zerlegt ihren Inhalt mit den Standardtrennzeichen.
def split_text_into_chunks(file_path, size, overlap):
    """Zerlegt eine Textdatei in Chunks."""
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    return split_recursive(text, size, overlap)
