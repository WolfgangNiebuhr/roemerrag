from langchain.text_splitter import RecursiveCharacterTextSplitter


def split_recursive(text, size, overlap, *, separators=None):
    if separators is None:
        separators = ["\n\n", ".\n", ". "]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        separators=separators,
    )
    return splitter.split_text(text)


def split_text_into_chunks(file_path, size, overlap):
    """Zerlegt eine Textdatei in Chunks."""
    with open(file_path, 'r', encoding='utf-8') as file:
        text = file.read()

    return split_recursive(text, size, overlap)
