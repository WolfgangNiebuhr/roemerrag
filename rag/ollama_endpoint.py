"""Resolve Windows Ollama from a WSL container without storing a gateway IP."""

import functools
from http.client import HTTPException
import json
import os
from pathlib import Path
import socket
import urllib.request


DEFAULT_URL = "http://host.containers.internal:11434"


class OllamaResolutionError(RuntimeError):
    """Automatic discovery found no usable Ollama endpoint."""


def wsl_gateways():
    if "microsoft" not in Path("/proc/sys/kernel/osrelease").read_text().lower():
        return []
    routes = []
    for line in Path("/proc/net/route").read_text().splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 8 and fields[1] == "00000000" and int(fields[3], 16) & 2:
            address = socket.inet_ntoa(int(fields[2], 16).to_bytes(4, "little"))
            routes.append((int(fields[6]), address))
    return [address for _, address in sorted(routes)]


@functools.lru_cache(maxsize=1)
def resolve_ollama_base_url():
    explicit = os.environ.get("OLLAMA_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    candidates = [DEFAULT_URL]
    try:
        candidates.extend(f"http://{address}:11434" for address in wsl_gateways())
    except (OSError, ValueError, OverflowError):
        pass
    errors = []
    # These are local connections; do not send gateway probes to an HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for base_url in dict.fromkeys(candidates):
        try:
            with opener.open(base_url + "/api/tags", timeout=3) as response:
                payload = json.load(response)
            if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
                raise ValueError("response is not an Ollama model list")
            return base_url
        except (OSError, ValueError, HTTPException) as exc:
            errors.append(f"{base_url}: {exc}")
    # Exceptions are not cached, so a later request retries after Ollama starts.
    raise OllamaResolutionError(
        "Ollama is unreachable. Set OLLAMA_BASE_URL explicitly if needed. " + "; ".join(errors)
    )
