"""Pytest fixtures for isolated Podman integration tests."""

import os
import json
import shutil
import socket
import subprocess
import time
import uuid
import sys
import urllib.error
import urllib.request

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _run(*args, cwd=ROOT, capture=False):
    return subprocess.run(
        ["podman", *args], cwd=cwd, check=True,
        text=True, capture_output=capture,
    )


def _wait_tcp(port, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(2)
    raise RuntimeError(f"Timed out waiting for localhost:{port}")


def _wait_reranker_ready(timeout=600):
    url = "http://localhost:5000/health"
    deadline = time.monotonic() + timeout
    last_error = "no response yet"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                health = json.loads(response.read())
            if health.get("status") == "ok" and health.get("model_loaded") is True:
                return
            last_error = f"model not ready: {health}"
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(3)
    raise RuntimeError(f"Reranker did not become ready within {timeout}s: {last_error}")


@pytest.fixture(scope="session")
def podman_stack(request):
    if request.config.getoption("--no-podman"):
        pytest.skip("Podman setup disabled by --no-podman")

    for program in ("podman",):
        if shutil.which(program) is None:
            pytest.fail(f"Required executable not found: {program}")

    all_tests = request.config.getoption("--all")
    include_rag = all_tests or request.config.getoption("--include-rag")
    include_reranker = all_tests or request.config.getoption("--include-reranker")
    test_id = uuid.uuid4().hex[:12]
    pod = f"rag-test-{test_id}"
    volume = f"rag-test-data-{test_id}"
    db = f"rag-test-db-{test_id}"
    vector = f"rag-test-vector-{test_id}"
    containers = []
    images = []
    volume_created = False
    pod_created = False

    def build(tag, dockerfile, context):
        image = f"localhost/{tag}:test-{test_id}"
        _run("build", "-t", image, "-f", dockerfile, context)
        images.append(image)
        return image

    try:
        db_image = build("vectordb", "Vector/Dockerfile", "Vector")
        vector_image = build("vectorapi", "Vector/Dockerfile.api", "Vector")
        rag_image = build("rag-api", "rag/Dockerfile", "rag") if include_rag else None
        reranker_image = build("reranker", "reranker/Dockerfile", "reranker") if include_reranker else None

        _run("volume", "create", volume)
        volume_created = True
        _run("pod", "create", "--name", pod,
             "-p", "5432:5432", "-p", "5500:5500", "-p", "5600:5600", "-p", "5000:5000")
        pod_created = True
        _run("run", "-d", "--name", db, "--pod", pod,
             "-e", "POSTGRES_USER=admin", "-e", "POSTGRES_PASSWORD=admin",
             "-e", "POSTGRES_DB=vector_db", "-e", "PGDATA=/var/lib/postgresql/data/pgdata",
             "-v", f"{volume}:/var/lib/postgresql/data", db_image)
        containers.append(db)

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            result = subprocess.run(
                ["podman", "exec", db, "pg_isready", "-U", "admin", "-d", "vector_db"],
                cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                break
            time.sleep(2)
        else:
            logs = subprocess.run(["podman", "logs", db], text=True, capture_output=True).stdout
            raise RuntimeError(f"PostgreSQL did not become ready. Logs:\n{logs}")

        _run("run", "-d", "--name", vector, "--pod", pod,
             "-e", "DB_HOST=127.0.0.1", "-e", "DB_PORT=5432", "-e", "DB_USER=admin",
             "-e", "DB_PASSWORD=admin", "-e", "POSTGRES_DB=vector_db", vector_image)
        containers.append(vector)
        if include_rag:
            name = f"rag-test-app-{test_id}"
            _run("run", "-d", "--name", name, "--pod", pod, rag_image)
            containers.append(name)
        if include_reranker:
            name = f"rag-test-reranker-{test_id}"
            _run("run", "-d", "--name", name, "--pod", pod, reranker_image)
            containers.append(name)

        _wait_tcp(5500)
        if include_rag:
            _wait_tcp(5600)
        if include_reranker:
            _wait_reranker_ready()
        yield {
            "id": test_id,
            "vector_url": "http://localhost:5500",
            "rag_url": "http://localhost:5600",
            "reranker_url": "http://localhost:5000",
        }
    except Exception:
        if pod_created:
            subprocess.run(["podman", "pod", "ps", "--filter", f"name={pod}"])
            for name in containers:
                subprocess.run(["podman", "logs", name])
        raise
    finally:
        if not request.config.getoption("--keep-podman"):
            if containers:
                subprocess.run(["podman", "rm", "-f", *containers], cwd=ROOT, capture_output=True)
            if pod_created:
                subprocess.run(["podman", "pod", "rm", "-f", pod], cwd=ROOT, capture_output=True)
            if volume_created:
                subprocess.run(["podman", "volume", "rm", volume], cwd=ROOT, capture_output=True)
            if images:
                subprocess.run(["podman", "image", "rm", *images], cwd=ROOT, capture_output=True)


@pytest.fixture(scope="session")
def test_id(podman_stack):
    return podman_stack["id"]


@pytest.fixture(scope="session")
def vector_url(podman_stack):
    return podman_stack["vector_url"]


@pytest.fixture(scope="session")
def rag_url(podman_stack):
    return podman_stack["rag_url"]


@pytest.fixture(scope="session")
def reranker_url(podman_stack):
    return podman_stack["reranker_url"]


@pytest.fixture(scope="session")
def ollama_url():
    return os.environ.get("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings")


@pytest.fixture(scope="session")
def ollama_model():
    return os.environ.get("OLLAMA_EMBEDDING_MODEL", "snowflake-arctic-embed2")
