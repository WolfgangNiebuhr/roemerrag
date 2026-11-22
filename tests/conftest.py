"""Shared pytest options and marker selection for unit and integration suites."""

import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

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


def external_temp_path(path):
    """Reject private temporary directories anywhere inside the checkout."""
    resolved = Path(path).resolve()
    if resolved.is_relative_to(Path(ROOT).resolve()):
        raise pytest.UsageError("Test temporary directories must be outside the project: " + str(resolved))
    return resolved


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config):
    temporary_root = external_temp_path(tempfile.gettempdir())
    # Also protect calls that override addopts or explicitly enable cacheprovider.
    # Run before its configure hook creates config.cache.
    config._inicache["cache_dir"] = str(temporary_root / "rag-pytest-cache")
    # Set an explicit base so PYTEST_DEBUG_TEMPROOT cannot redirect fixtures
    # into the checkout. Do not create it: pytest owns its lifecycle.
    requested = config.option.basetemp
    config.option.basetemp = str(external_temp_path(requested) if requested
        else temporary_root / ("rag-pytest-" + uuid4().hex))
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
