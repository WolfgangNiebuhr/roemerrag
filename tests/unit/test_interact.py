"""CLI boundary and TS-08 behavior without external services."""
import sys
from unittest.mock import Mock
import pytest
import requests
import interact as cli


def arguments(monkeypatch, *extra):
    monkeypatch.setattr(sys, 'argv', ['interact.py', '--query', 'Rome?', *extra])


def test_problem_details_are_readable(monkeypatch):
    response = Mock(status_code=503)
    response.json.return_value = {'type':'urn:rag:problem:model-unavailable','title':'Modell fehlt','detail':'Bitte bereitstellen','request_id':'abc'}
    post = Mock(return_value=response)
    monkeypatch.setattr(cli.requests, 'post', post)
    with pytest.raises(RuntimeError, match='HTTP 503.*Modell fehlt.*Bitte bereitstellen.*abc'):
        cli.post_json('http://example', {}, 'Reranking', 600)
    assert post.call_args.kwargs['timeout'] == (5, 600)


@pytest.mark.parametrize('error,message', [(requests.Timeout(), 'Zeitlimit'), (requests.ConnectionError(), 'nicht erreichbar')])
def test_network_errors_and_exit_code(monkeypatch, capsys, error, message):
    arguments(monkeypatch)
    monkeypatch.setattr(cli.requests, 'post', Mock(side_effect=error))
    assert cli.main() == 1
    assert message in capsys.readouterr().err


@pytest.mark.parametrize('results', [[], [{'chunk_id':'c','chunktext':'  '}]])
def test_no_context_skips_models_and_export(monkeypatch, capsys, results):
    arguments(monkeypatch)
    monkeypatch.setattr(cli, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(cli, 'search_vectors', Mock(return_value=results))
    for name in ('generate_answer','rerank_results','export_results'):
        monkeypatch.setattr(cli, name, Mock(side_effect=AssertionError(name)))
    assert cli.main() == 0
    assert 'no_context' in capsys.readouterr().out


@pytest.mark.parametrize('value', [None, 0, -1, 'bad', True, float('nan'), float('inf')])
def test_bad_metrics_keep_answer(monkeypatch, value):
    monkeypatch.setattr(cli, 'post_json', Mock(return_value={'response':'answer', 'eval_duration':value, 'eval_count':2}))
    answer = cli.generate_answer('text', 'q')
    assert answer.startswith('answer')
    assert 'nicht verfuegbar' in answer


@pytest.mark.parametrize('extra', [('--metric','bad'),('--num_results','0'),('--top_k','-1')])
def test_invalid_cli_has_exit_two(monkeypatch, extra):
    arguments(monkeypatch, *extra)
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2


def test_export_failure_aborts(monkeypatch, capsys):
    arguments(monkeypatch)
    monkeypatch.setattr(cli, 'generate_embedding', Mock(return_value=[1]))
    monkeypatch.setattr(cli, 'search_vectors', Mock(return_value=[{'chunk_id':'c','chunktext':'text'}]))
    monkeypatch.setattr(cli, 'export_results', Mock(side_effect=OSError('disk full')))
    generate = Mock()
    monkeypatch.setattr(cli, 'generate_answer', generate)
    assert cli.main() == 1
    assert 'disk full' in capsys.readouterr().err
    generate.assert_not_called()


def test_non_json_error_does_not_print_raw_body(monkeypatch):
    response = Mock(status_code=502, text='secret html')
    response.json.side_effect = ValueError()
    monkeypatch.setattr(cli.requests, 'post', Mock(return_value=response))
    with pytest.raises(RuntimeError) as caught:
        cli.post_json('url', {}, 'Retrieval', 60)
    assert 'HTTP 502' in str(caught.value) and 'secret' not in str(caught.value)

@pytest.mark.parametrize('extra,expected', [
    (('--metric','L2'), ('--metric', 'L2', 'cosine', 'euclidean')),
    (('--num_results','101'), ('--num_results', '101', '1 bis 100')),
    (('--top_k','-1'), ('--top_k', '-1', '>= 0')),
    (('--query',' '), ('--query', 'nichtleerer Text')),
    (('--embedding-set-id',' '), ('--embedding-set-id', 'nichtleerer Text')),
    (('--reranker',' '), ('--reranker', 'nichtleerer Text')),
])
def test_invalid_parameter_message_is_specific(monkeypatch, capsys, extra, expected):
    arguments(monkeypatch, *extra)
    post = Mock()
    monkeypatch.setattr(cli.requests, 'post', post)
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2
    error = capsys.readouterr().err
    assert all(fragment in error for fragment in expected)
    post.assert_not_called()

@pytest.mark.parametrize('argv,fragments', [
    ([], ('Pflichtparameter fehlen', '--query')),
    (['--query'], ('Parameter --query', 'ein Wert muss angegeben werden')),
    (['--query','q','--metric','L2'], ('Parameter --metric', 'L2', 'erlaubt sind cosine und euclidean')),
    (['--query','q','--metric'], ('Parameter --metric', 'ein Wert muss angegeben werden')),
    (['--query','q','--num_results','abc'], ('Parameter --num_results', 'abc', 'keine ganze Zahl')),
    (['--query','q','--top_k','1.5'], ('Parameter --top_k', '1.5', 'keine ganze Zahl')),
    (['--query','q','--embedding'], ('Parameter --embedding', 'ein Wert muss angegeben werden')),
    (['--query','q','--embedding-set-id'], ('Parameter --embedding-set-id', 'ein Wert muss angegeben werden')),
    (['--query','q','--reranker'], ('Parameter --reranker', 'ein Wert muss angegeben werden')),
    (['--query','q','--unbekannt'], ('Unbekannte Argumente', '--unbekannt')),
])
def test_argparse_errors_are_german(monkeypatch, capsys, argv, fragments):
    monkeypatch.setattr(sys, 'argv', ['interact.py', *argv])
    post = Mock()
    monkeypatch.setattr(cli.requests, 'post', post)
    with pytest.raises(SystemExit) as caught:
        cli.main()
    assert caught.value.code == 2
    message = capsys.readouterr().err
    assert 'Aufruf:' in message and 'Fehler:' in message
    assert all(fragment in message for fragment in fragments)
    for english in ('invalid choice', 'invalid int value', 'expected one argument', 'required:', 'unrecognized arguments', 'error:'):
        assert english not in message
    post.assert_not_called()


def test_ollama_error_field_is_reported(monkeypatch):
    response = Mock(status_code=500)
    response.json.return_value = {'error': 'CUDA error: shared object initialization failed'}
    monkeypatch.setattr(cli.requests, 'post', Mock(return_value=response))
    with pytest.raises(RuntimeError, match='Embedding: HTTP 500 - CUDA error: shared object initialization failed'):
        cli.post_json('http://localhost:11434/api/embeddings', {}, 'Embedding', 300)


@pytest.mark.parametrize('body', [{'error': {'secret': 'value'}}, {'error': None}])
def test_nontext_ollama_error_is_not_dumped(monkeypatch, body):
    response = Mock(status_code=500)
    response.json.return_value = body
    monkeypatch.setattr(cli.requests, 'post', Mock(return_value=response))
    with pytest.raises(RuntimeError) as caught:
        cli.post_json('url', {}, 'Embedding', 300)
    assert str(caught.value) == 'Embedding: HTTP 500'
