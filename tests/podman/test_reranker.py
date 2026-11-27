"""Container integration test for the cross-encoder reranker."""

import math

import pytest

from common import request


@pytest.mark.reranker
@pytest.mark.podman
def test_reranker(reranker_url, restart_reranker):
    health = request(reranker_url, "/actuator/health")
    assert health["status"] == "UP"
    assert health["build"]["time"]
    bad = request(reranker_url, "/rerank", "POST", {"query": "hello"}, 400)
    assert bad["type"] == "urn:rag:problem:invalid-request"
    result = request(reranker_url, "/rerank", "POST", {
        "query": "Wie funktioniert maschinelles Lernen?",
        "documents": [
            "Maschinelles Lernen ist ein Teilbereich der künstlichen Intelligenz, der Computern das Lernen aus Daten ermöglicht.",
            "Deep Learning ist eine spezialisierte Form des maschinellen Lernens, die neuronale Netze mit vielen Schichten verwendet.",
            "Das Training eines Modells beinhaltet die Anpassung von Parametern, um Vorhersagen zu verbessern.",
            "Quantencomputing nutzt Prinzipien der Quantenmechanik für die Datenverarbeitung.",
        ],
    })
    ranked = result["ranked_documents"]
    assert sorted(item["original_index"] for item in ranked) == [0, 1, 2, 3]
    assert all(math.isfinite(item["score"]) for item in ranked)
    assert all(a["score"] >= b["score"] for a, b in zip(ranked, ranked[1:]))
    assert all(item["text"] for item in ranked)

    assert result["model"] == "cross-encoder/ms-marco-MiniLM-L6-v2"
    alternative = "cross-encoder/ms-marco-TinyBERT-L2-v2"
    for selected in [alternative, result["model"]]:
        switched = request(reranker_url, "/rerank", "POST", {
            "model": selected, "query": "What is Rome?", "documents": ["Rome is a city.", "A fish swims."]
        }, timeout=600)
        assert switched["model"] == selected
        assert len(switched["ranked_documents"]) == 2
        assert all(math.isfinite(item["score"]) for item in switched["ranked_documents"])
        assert request(reranker_url, "/actuator/info")["models"]["active"] == selected

    restart_reranker()
    assert request(reranker_url, "/actuator/info")["models"]["active"] == result["model"]
