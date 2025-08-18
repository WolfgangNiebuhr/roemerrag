from langchain.text_splitter import RecursiveCharacterTextSplitter

def split_text_into_chunks(file_path, size, overlap):
    """Zerlegt eine Textdatei in Chunks."""
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=["\n\n", ".\n", ". "]
    )

    chunks = splitter.split_text(text)
    return chunks
