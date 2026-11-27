"""Pytest fixtures for isolated Podman integration tests."""

import os
import json
import shutil
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


def _wait_health_ready(base_url, timeout=120):
    url = base_url + "/actuator/health"
    deadline = time.monotonic() + timeout
    last_error = "no response yet"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                health = json.loads(response.read())
            if health.get("status") == "UP" and health["build"]["time"]:
                return
            last_error = f"service not ready: {health}"
        except urllib.error.HTTPError as exc:
            with exc:
                last_error = f"{exc.code}: {exc.read().decode(errors='replace')}"
        except (OSError, json.JSONDecodeError) as exc:
            last_error = str(exc)
        time.sleep(1)
    raise RuntimeError(f"{url} did not become ready within {timeout}s: {last_error}")


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
        if context == ".":
            from scripts.build_image import build_image
            build_image(tag, image)
        else:
            _run("build", "-t", image, "-f", dockerfile, context)
        images.append(image)
        return image

    try:
        db_image = build("vectordb", "Vector/Dockerfile", "Vector")
        vector_image = build("vectorapi", "Vector/Dockerfile.api", ".")
        rag_image = build("rag-api", "rag/Dockerfile", ".") if include_rag else None
        reranker_image = build("reranker", "reranker/Dockerfile", ".") if include_reranker else None

        _run("volume", "create", volume)
        volume_created = True
        # Let Podman allocate host ports; a manually used stack may be running.
        publish = ["-p", "5500"]
        if include_rag:
            publish.extend(["-p", "5600"])
        if include_reranker:
            publish.extend(["-p", "5000"])
        _run("pod", "create", "--name", pod, *publish)
        pod_created = True
        containers.append(db)
        _run("run", "-d", "--name", db, "--pod", pod,
             "-e", "POSTGRES_USER=admin", "-e", "POSTGRES_PASSWORD=admin",
             "-e", "POSTGRES_DB=vector_db", "-e", "PGDATA=/var/lib/postgresql/data/pgdata",
             "-v", f"{volume}:/var/lib/postgresql/data", db_image)

        infra = _run("pod", "inspect", "--format", "{{.InfraContainerID}}", pod, capture=True).stdout.strip()

        def host_port(container_port):
            binding = _run("port", infra, f"{container_port}/tcp", capture=True).stdout
            return int(binding.splitlines()[0].rsplit(":", 1)[1])

        vector_port = host_port(5500)
        rag_port = host_port(5600) if include_rag else None
        reranker_port = host_port(5000) if include_reranker else None

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
            _run("run", "-d", "--name", name, "--pod", pod,
                 "-e", "VECTOR_API_URL=http://127.0.0.1:5500/search",
                 "-e", "RERANKER_URL=http://127.0.0.1:5000/rerank",
                 "-e", "OLLAMA_BASE_URL=" + os.environ.get("OLLAMA_CONTAINER_URL", ""), rag_image)
            containers.append(name)
        if include_reranker:
            name = f"rag-test-reranker-{test_id}"
            _run("run", "-d", "--name", name, "--pod", pod, reranker_image)
            containers.append(name)

        _wait_health_ready(f"http://127.0.0.1:{vector_port}")
        if include_rag:
            _wait_health_ready(f"http://127.0.0.1:{rag_port}")
        if include_reranker:
            _wait_health_ready(f"http://127.0.0.1:{reranker_port}", timeout=600)
        yield {
            "id": test_id,
            "db_container": db,
            "rag_container": f"rag-test-app-{test_id}" if include_rag else None,
            "vector_url": f"http://127.0.0.1:{vector_port}",
            "rag_url": f"http://127.0.0.1:{rag_port}" if include_rag else None,
            "reranker_container": f"rag-test-reranker-{test_id}" if include_reranker else None,
            "reranker_url": f"http://127.0.0.1:{reranker_port}" if include_reranker else None,
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
def e2e_ollama_url(podman_stack):
    """Fail before ingestion if either side cannot reach the real models."""
    host_url = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
    container_url = os.environ.get("OLLAMA_CONTAINER_URL") or "automatic host/WSL gateway detection"
    required = {"snowflake-arctic-embed2:latest", "phi3:mini"}
    try:
        with urllib.request.urlopen(host_url + "/api/tags", timeout=10) as response:
            models = json.load(response)
        missing = required - {model["name"] for model in models["models"]}
        if missing:
            pytest.fail(f"Host Ollama is missing models: {sorted(missing)}; run ollama pull for each model")
    except (OSError, ValueError, KeyError) as exc:
        pytest.fail(f"Host Ollama is not available at {host_url}: {exc}")

    script = (
        "import json, urllib.request; "
        "from ollama_endpoint import resolve_ollama_base_url; "
        "url = resolve_ollama_base_url(); print('Ollama endpoint:', url, flush=True); "
        "r = urllib.request.urlopen(url + '/api/tags', timeout=10); "
        "models = {m['name'] for m in json.load(r)['models']}; "
        f"missing = {required!r} - models; "
        "assert not missing, f'Missing Ollama models: {missing}'"
    )
    result = subprocess.run(
        ["podman", "exec", podman_stack["rag_container"], "python", "-c", script],
        cwd=ROOT, text=True, capture_output=True, timeout=30,
    )
    if result.returncode:
        pytest.fail(
            f"RAG container cannot access the required Ollama models at {container_url}. "
            "Check the container's host resolution and the Windows/WSL gateway; "
            "host.containers.internal may point to the Linux VM rather than Windows. Set "
            "OLLAMA_CONTAINER_URL and OLLAMA_HOST_URL to the same server's respective addresses. "
            f"Container diagnostic: {result.stderr}"
        )
    return host_url


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


@pytest.fixture
def restart_reranker(podman_stack, reranker_url):
    def restart():
        _run("restart", podman_stack["reranker_container"])
        _wait_health_ready(reranker_url, timeout=600)

    return restart


@pytest.fixture(scope="session")
def ollama_url():
    return os.environ.get("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings")


@pytest.fixture(scope="session")
def ollama_model():
    return os.environ.get("OLLAMA_EMBEDDING_MODEL", "snowflake-arctic-embed2")
