"""Shared HTTP helper for the Podman API tests."""

import json
import urllib.error
import urllib.request


def request(base_url, path, method="GET", payload=None, expected=200, timeout=30):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read()
    assert status == expected, f"{method} {path}: expected {expected}, got {status}: {body!r}"
    return json.loads(body) if body else None
