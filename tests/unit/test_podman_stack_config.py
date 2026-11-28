"""Check test-stack isolation without starting containers."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("reranker", [False, True])
def test_stack_uses_allocated_ports_and_internal_retrieval(monkeypatch, reranker):
    path = Path(__file__).parents[1] / "podman" / "conftest.py"
    spec = importlib.util.spec_from_file_location("stack_fixtures", path)
    stack = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stack)
    calls = []
    ports = {"5500/tcp": 45100, "5600/tcp": 45101, "5000/tcp": 45102}

    def run(*args, **kwargs):
        calls.append(args)
        output = ""
        if args[:2] == ("pod", "inspect"):
            output = "test-infra\n"
        elif args[0] == "port":
            assert args[1] == "test-infra"
            output = f"127.0.0.1:{ports[args[2]]}\n"
        return SimpleNamespace(stdout=output)

    monkeypatch.setitem(vars(stack), "_run", run)
    monkeypatch.setattr("shutil.which", lambda name: name)
    monkeypatch.setattr("subprocess.run", lambda *a, **kw: SimpleNamespace(returncode=0))
    ready = []
    monkeypatch.setattr(stack, "_wait_health_ready", lambda url, timeout=120: ready.append((url, timeout)))
    options = {"--include-rag": True, "--include-reranker": reranker}
    request = SimpleNamespace(config=SimpleNamespace(getoption=lambda key: options.get(key, False)))
    fixture = stack.podman_stack.__wrapped__(request)
    try:
        urls = next(fixture)
        assert urls["vector_url"] == "http://127.0.0.1:45100"
        assert urls["rag_url"] == "http://127.0.0.1:45101"
        assert urls["reranker_url"] == ("http://127.0.0.1:45102" if reranker else None)
        create = next(call for call in calls if call[:2] == ("pod", "create"))
        expected_publish = ("-p", "127.0.0.1::5500", "-p", "127.0.0.1::5600")
        if reranker:
            expected_publish += ("-p", "127.0.0.1::5000")
        assert create[4:] == expected_publish
        rag_run = next(call for call in calls if "VECTOR_API_URL=http://127.0.0.1:5500/search" in call)
        assert rag_run[0] == "run"
        expected_ready = [("http://127.0.0.1:45100", 120), ("http://127.0.0.1:45101", 120)]
        if reranker:
            expected_ready.append(("http://127.0.0.1:45102", 600))
        assert ready == expected_ready
    finally:
        fixture.close()
