"""Shared pytest options and marker selection for unit and integration suites."""

import os
import sys

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def pytest_addoption(parser):
    parser.addoption("--all", action="store_true", help="run all optional RAG, reranker, and Ollama tests")
    parser.addoption("--include-rag", action="store_true", help="build and test the RAG API")
    parser.addoption("--include-reranker", action="store_true", help="build and test the reranker")
    parser.addoption("--include-ollama", action="store_true", help="test host Ollama embeddings")
    parser.addoption("--keep-podman", action="store_true", help="retain created Podman resources")
    parser.addoption("--no-podman", action="store_true", help="skip Podman tests")


def pytest_configure(config):
    config.addinivalue_line("markers", "podman: requires Podman containers")
    config.addinivalue_line("markers", "rag: requires --include-rag or --all")
    config.addinivalue_line("markers", "reranker: requires --include-reranker or --all")
    config.addinivalue_line("markers", "ollama: requires --include-ollama or --all")


def pytest_collection_modifyitems(config, items):
    all_groups = config.getoption("--all")
    enabled = {
        "rag": all_groups or config.getoption("--include-rag"),
        "reranker": all_groups or config.getoption("--include-reranker"),
        "ollama": all_groups or config.getoption("--include-ollama"),
    }
    no_podman = config.getoption("--no-podman")
    for item in items:
        for marker, is_enabled in enabled.items():
            if item.get_closest_marker(marker) and not is_enabled:
                item.add_marker(pytest.mark.skip(reason=f"use --include-{marker} or --all"))
        if item.get_closest_marker("podman") and no_podman:
            item.add_marker(pytest.mark.skip(reason="Podman tests disabled by --no-podman"))
