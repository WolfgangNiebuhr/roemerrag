from unittest.mock import Mock

import pytest

import analyze


def response(status, body):
    result = Mock(status_code=status)
    result.json.return_value = body
    return result


@pytest.mark.parametrize("compare_gold", [False, True])
def test_analysis_uses_only_evaluate_endpoints(monkeypatch, capsys, compare_gold):
    monkeypatch.setenv("RAG_API_BASE_URL", "http://rag.example/prefix/")
    next_request = {"query": "Frage", "results": [{"chunk_id": "c", "chunktext": "Kontext"}], "answer_model": "m"}
    diagnostics = {"hits": [{"chunk_id": "c", "distance": 0.25,
                             "cosine_similarity": 0.75, "euclidean_distance": 1.5}]}
    if compare_gold:
        diagnostics["reference"] = {"cosine_similarity": 0.5, "euclidean_distance": 2.0}
    post = Mock(side_effect=[
        response(200, {"diagnostics": diagnostics, "next_request": next_request}),
        response(200, {"status": "ok", "response": "Antworttext", "metrics": {"answer_tokens": 3}}),
    ])
    monkeypatch.setattr("requests.post", post)
    arguments = ["--query", "Frage", "--num_results", "3", "--embedding-set-id", "set", "--answer-model", "m"]
    payload = {"query": "Frage", "metric": "cosine", "num_results": 3, "include_distances": True,
               "embedding_set_id": "set", "answer_model": "m"}
    if compare_gold:
        arguments.append("--compare-gold")
        payload["reference_text"] = analyze.GOLDCHUNK
        assert analyze.GOLDCHUNK.startswith("Vesta, Italus, Ackerbau, Stammsagen, Volk")
        assert "Εστία" in analyze.GOLDCHUNK
        assert analyze.GOLDCHUNK.endswith("Feldarbeiter (Opsci)")

    assert analyze.main(arguments) == 0
    assert [call.args[0] for call in post.call_args_list] == [
        "http://rag.example/prefix/evaluate/retrieve", "http://rag.example/prefix/evaluate/generate",
    ]
    assert [call.kwargs["json"] for call in post.call_args_list] == [payload, next_request]
    output = capsys.readouterr().out
    assert ("Gold-Chunk:" in output) is compare_gold
    assert "Rankingdistanz: 0.25" in output and "Cosinus-Ähnlichkeit: 0.75" in output
    assert "Euklidischer Abstand: 1.5" in output and "Antworttext" in output and '"answer_tokens": 3' in output


def test_analysis_preserves_no_context(monkeypatch, capsys):
    post = Mock(side_effect=[
        response(200, {"diagnostics": {"hits": []}, "next_request": {"query": "q", "results": []}}),
        response(200, {"status": "no_context", "response": "Kein Kontext", "metrics": None}),
    ])
    monkeypatch.setattr("requests.post", post)
    assert analyze.main(["--query", "q"]) == 0
    assert post.call_args.kwargs["json"]["results"] == []
    assert "Kein Kontext" in capsys.readouterr().out


def test_analysis_reports_problem_and_stops_before_generation(monkeypatch, capsys):
    post = Mock(return_value=response(503, {"detail": "Retrieval ausgefallen", "request_id": "abc"}))
    monkeypatch.setattr("requests.post", post)
    assert analyze.main(["--query", "q"]) == 1
    post.assert_called_once()
    error = capsys.readouterr().err
    assert "HTTP 503" in error and "Retrieval ausgefallen" in error and "abc" in error
