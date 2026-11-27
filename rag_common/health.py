"""Shared Actuator-style health endpoints for the Flask APIs."""

import os
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Lock

from flask import jsonify

UP = "UP"
OUT_OF_SERVICE = "OUT_OF_SERVICE"
DOWN = "DOWN"


def install_actuator(app, *, info, status=lambda: UP, check=None, timeout=2):
    """Register health and info with an optional bounded dependency check."""
    build = {"time": os.getenv("RAG_BUILD_TIME") or None}
    if check is not None:
        executor = ThreadPoolExecutor(max_workers=1)
        lock = Lock()
        pending = None

    def run_check():
        try:
            return UP if check() else DOWN
        except Exception:
            app.logger.warning("Health check failed")
            return DOWN

    def check_status():
        nonlocal pending
        with lock:
            if pending is None or pending.done():
                pending = executor.submit(run_check)
            future = pending
        done, _ = wait((future,), timeout=timeout)
        return future.result() if done else DOWN

    @app.get("/actuator/health")
    def health():
        current = check_status() if check is not None else status()
        return jsonify({"status": current, "build": build}), 200 if current == UP else 503

    @app.get("/actuator/info")
    def runtime_info():
        return jsonify(info())
