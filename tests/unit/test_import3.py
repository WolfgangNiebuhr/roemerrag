"""Exercise the real importer and keyword enrichment with HTTP responses faked."""

from unittest.mock import Mock

import pytest

from test_chunking import write_temp_text


@pytest.mark.parametrize("start", [1, 2])
def test_import_file_enriches_embeds_and_stores_chunks(monkeypatch, start):
    from Ingest import import3 as importer
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
            return Mock(status_code=200, json=lambda: {"embedding": [3.0, 4.0] + [0.0] * 1022})
        assert url == importer.VECTOR_API_URL
        return Mock(status_code=201)

    monkeypatch.setattr("requests.post", post)
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
        }, "timeout": (5, 300)})
        assert store[1]["timeout"] == (5, 60)
        payload = store[1]["json"]
        assert payload == {
            "chunk_id": f"{source.stem}-{index + start}",
            "embedding_set_id": importer.EMBEDDING_SET_ID,
            "vector": pytest.approx([0.6, 0.8] + [0.0] * 1022),
            "chunktext": enriched,
        }


@pytest.mark.parametrize("embedding", [[1.0], [0.0] * 1024, [float("inf")] + [0.0] * 1023])
def test_invalid_provider_embedding_is_not_stored(monkeypatch, tmp_path, embedding):
    from Ingest import import3 as importer

    source = tmp_path / "rome.txt"
    source.write_text("Roma", encoding="utf-8")
    monkeypatch.setattr(importer, "get_keywords_ollama", lambda text: ("Roma", {}, None))
    post = Mock(return_value=Mock(status_code=200, json=lambda: {"embedding": embedding}))
    monkeypatch.setattr(importer.requests, "post", post)
    importer.process_file(source, start=1)
    post.assert_called_once()
    assert post.call_args.args == (importer.OLLAMA_URL,)


def test_standard_import_is_selected_by_standard_retrieval(monkeypatch):
    from rag import app as rag_app
    from Ingest import import3 as importer
    source = write_temp_text("Roma")
    stored = []
    monkeypatch.setattr("Ingest.import3.get_keywords_ollama", lambda text: ("Rom", {}, None))
    monkeypatch.setattr(importer, "generate_embedding", lambda text: importer.np.array([1.0]))
    monkeypatch.setattr(importer, "store_vector_in_db", lambda *args: stored.append(args))
    try:
        importer.process_file(str(source), 1)
    finally:
        source.unlink()
    monkeypatch.setattr(rag_app, "generate_embedding", lambda query: [1.0])
    def search(vector, set_id, metric, count):
        return [{"chunk_id": row[0], "chunktext": row[3]} for row in stored if row[1] == set_id]
    monkeypatch.setattr(rag_app, "search_vectors", search)
    monkeypatch.setattr(rag_app, "generate_answer", lambda context, query, model=None: (context, {}))
    response = rag_app.app.test_client().post("/process", json={"query": "Roma?"})
    assert response.status_code == 200
    assert response.json["chunks"] == [stored[0][0]]
    assert importer.MODEL_NAME == rag_app.EMBEDDING_MODEL_NAME


@pytest.mark.parametrize('filename,stem', [
    ('rom.band1.txt', 'rom.band1'), ('rom.band2.txt', 'rom.band2'),
    ('rom', 'rom'), ('rom.txt', 'rom'),
])
def test_file_stem_used_for_chunks_and_log(monkeypatch, tmp_path, filename, stem):
    from Ingest import import3 as importer
    source = tmp_path / filename
    source.write_text('RomaAA\n\nCapuaB\n\nOstiaC\n\nGallia', encoding='utf-8')
    monkeypatch.setattr(importer, 'CHUNK_SIZE', 18)
    monkeypatch.setattr(importer, 'OVERLAP', 8)
    monkeypatch.setattr("Ingest.import3.get_keywords_ollama", lambda text: ('Rom', {}, None))
    monkeypatch.setattr(importer, 'generate_embedding', lambda text: importer.np.array([1.0]))
    store = Mock()
    monkeypatch.setattr(importer, 'store_vector_in_db', store)
    configure_log = Mock()
    monkeypatch.setattr(importer.logging, 'basicConfig', configure_log)
    importer.setup_logging(str(source))
    assert configure_log.call_args.kwargs['filename'].startswith(stem + '_')
    importer.process_file(str(source), 1)
    assert [call.args[0] for call in store.call_args_list] == [stem + '-1', stem + '-2', stem + '-3']
