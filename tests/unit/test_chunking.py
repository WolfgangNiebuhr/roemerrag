"""Unit tests for the ingestion text chunker."""

import tempfile
from unittest.mock import Mock
from pathlib import Path

import Ingest.chunking as chunking
import pytest


def write_temp_text(text):
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".txt", prefix="chunking-test-",
        dir=Path(__file__).parent, delete=False,
    ) as file:
        file.write(text)
        return Path(file.name)


@pytest.mark.parametrize("overlap, expected", [
    (0, ["RomaAA\n\nCapuaB", "OstiaC\n\nGallia"]),
    (8, ["RomaAA\n\nCapuaB", "CapuaB\n\nOstiaC", "OstiaC\n\nGallia"]),
])
def test_paragraph_boundaries_order_and_overlap(overlap, expected):
    source = write_temp_text("RomaAA\n\nCapuaB\n\nOstiaC\n\nGallia")
    try:
        chunks = chunking.split_text_into_chunks(str(source), size=18, overlap=overlap)
    finally:
        source.unlink()
    assert chunks == expected
    assert all(len(chunk) <= 18 for chunk in chunks)


def test_chunking_reads_utf8_and_passes_size_overlap_and_separators(monkeypatch):
    text = "Römischer Satz.\n\nKarthagischer Satz."
    source = write_temp_text(text)
    splitter_instance = Mock()
    splitter_instance.split_text.return_value = ["Römischer Satz.", "Karthagischer Satz."]
    splitter_class = Mock(return_value=splitter_instance)
    monkeypatch.setattr("Ingest.chunking.RecursiveCharacterTextSplitter", splitter_class)

    try:
        chunks = chunking.split_text_into_chunks(str(source), size=18, overlap=5)
    finally:
        source.unlink()

    assert chunks == ["Römischer Satz.", "Karthagischer Satz."]
    splitter_class.assert_called_once_with(
        chunk_size=18,
        chunk_overlap=5,
        separators=["\n\n", ".\n", ". "],
    )
    splitter_instance.split_text.assert_called_once_with(text)


def test_chunking_preserves_unicode_and_paragraph_content():
    text = "Römische Geschichte ist spannend.\n\nKarthago lag in Nordafrika."
    source = write_temp_text(text)

    try:
        chunks = chunking.split_text_into_chunks(str(source), size=100, overlap=10)
    finally:
        source.unlink()

    assert len(chunks) == 1
    assert "Römische Geschichte" in chunks[0]
    assert "Karthago lag in Nordafrika." in chunks[0]
