"""Endpoint selection, explicit overrides and retry after an unavailable server."""

import io
from unittest.mock import Mock

import pytest

from rag import ollama_endpoint as endpoint


@pytest.fixture(autouse=True)
def reset_endpoint(monkeypatch):
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    endpoint.resolve_ollama_base_url.cache_clear()
    yield
    endpoint.resolve_ollama_base_url.cache_clear()


def test_explicit_address_has_priority(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://configured:1234/")
    monkeypatch.setattr(endpoint, "wsl_gateways", Mock(side_effect=AssertionError))
    assert endpoint.resolve_ollama_base_url() == "http://configured:1234"


def test_gateway_fallback_is_cached(monkeypatch):
    monkeypatch.setattr(endpoint, "wsl_gateways", lambda: ["172.24.64.1"])
    opener = Mock()
    opener.open.side_effect = [OSError("refused"), io.BytesIO(b'{"models": []}')]
    monkeypatch.setattr(endpoint.urllib.request, "build_opener", lambda *args: opener)
    assert endpoint.resolve_ollama_base_url() == "http://172.24.64.1:11434"
    assert endpoint.resolve_ollama_base_url() == "http://172.24.64.1:11434"
    assert opener.open.call_count == 2


def test_failure_is_retried(monkeypatch):
    monkeypatch.setattr(endpoint, "wsl_gateways", lambda: [])
    opener = Mock()
    opener.open.side_effect = [OSError("refused"), io.BytesIO(b'{"models": []}')]
    monkeypatch.setattr(endpoint.urllib.request, "build_opener", lambda *args: opener)
    with pytest.raises(RuntimeError, match="Ollama is unreachable"):
        endpoint.resolve_ollama_base_url()
    assert endpoint.resolve_ollama_base_url() == endpoint.DEFAULT_URL


def test_route_table_decodes_little_endian_gateway(monkeypatch):
    def read_text(path):
        if str(path).endswith("osrelease"):
            return "6.6.87-microsoft-standard-WSL2"
        return "Iface Destination Gateway Flags RefCnt Use Metric Mask\neth0 00000000 014018AC 0003 0 0 0 00000000\neth0 004018AC 00000000 0001 0 0 0 00F0FFFF\n"
    monkeypatch.setattr(endpoint.Path, "read_text", read_text)
    assert endpoint.wsl_gateways() == ["172.24.64.1"]
