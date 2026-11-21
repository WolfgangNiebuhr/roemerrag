"""Exercise the real importer and keyword enrichment with HTTP responses faked."""

import importlib
from pathlib import Path
from unittest.mock import Mock

import pytest

from test_chunking import write_temp_text


@pytest.mark.parametrize("start", [1, 2])
def test_import_file_enriches_embeds_and_stores_chunks(monkeypatch, start):
    # Match import3's script-style imports without changing production imports.
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "Ingest"))
    importer = importlib.import_module("import3")
    monkeypatch.setattr(importer, "CHUNK_SIZE", 18)
    monkeypatch.setattr(importer, "OVERLAP", 8)
    source = write_temp_text("RomaAA\n\nCapuaB\n\nOstiaC\n\nGallia")
    chunks = ["RomaAA\n\nCapuaB", "CapuaB\n\nOstiaC", "OstiaC\n\nGallia"][start - 1:]
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/api/chat"):
            return Mock(status_code=200, json=lambda: {"message": {"content": "Roma, Capua"}})
        if url == importer.OLLAMA_URL:
            return Mock(status_code=200, json=lambda: {"embedding": [3.0, 4.0]})
        assert url == importer.VECTOR_API_URL
        return Mock(status_code=201)

    monkeypatch.setattr(importer.requests, "post", post)
    try:
        importer.process_file(str(source), start)
    finally:
        source.unlink()

    assert len(calls) == 3 * len(chunks)
    for index, chunk in enumerate(chunks):
        chat, embedding, store = calls[index * 3:index * 3 + 3]
        assert chat[0].endswith("/api/chat")
        assert any(chunk in message["content"] for message in chat[1]["json"]["messages"])
        enriched = "Roma, Capua\n" + chunk
        assert embedding == (importer.OLLAMA_URL, {"json": {
            "model": importer.MODEL_NAME, "prompt": enriched,
        }})
        payload = store[1]["json"]
        assert payload == {
            "chunk_id": f"{source.stem}-{index + start}",
            "embedding": importer.MODEL_NAME + importer.EMBEDDING_VERSION,
            "vector": pytest.approx([0.6, 0.8]),
            "metadata": enriched,
        }
