import logging
import os
import random
import time

import requests

logger = logging.getLogger(__name__)

# All adapters share bounded transport settings; generation is never retried.
CONNECT_TIMEOUT = float(os.getenv("RAG_CONNECT_TIMEOUT", "5"))
READ_TIMEOUTS = {name: float(os.getenv("RAG_" + name.upper() + "_TIMEOUT", str(default)))
                 for name, default in (("embedding", 300), ("retrieval", 60),
                                       ("reranking", 600), ("generation", 600))}


class ProviderUnavailable(RuntimeError):
    """A provider call could not complete successfully."""


class InvalidProviderResponse(ValueError):
    """A provider returned data that does not meet its response contract."""


def upstream_post(url, payload, stage, *, request_id=None):
    attempts = 1 if stage == "generation" else 2
    for attempt in range(attempts):
        try:
            response = requests.post(url, json=payload,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUTS[stage]),
                headers={"X-Request-ID": request_id} if request_id else {})
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt + 1 == attempts:
                raise ProviderUnavailable(stage + " is unavailable.") from exc
            delay = 0.1 * (2 ** attempt) + random.uniform(0, 0.1)
            logger.warning("upstream_retry stage=%s attempt=%s", stage, attempt + 1)
            time.sleep(delay)
