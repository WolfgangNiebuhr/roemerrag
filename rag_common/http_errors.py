"""Shared request validation and RFC 9457 boundary handlers."""
import json
import math
import re
from uuid import uuid4
from flask import g, request, jsonify
from werkzeug.exceptions import HTTPException

TYPES = {
    'upstream-invalid-response': (502, 'Invalid upstream response'),
    'invalid-request': (400, 'Ungültige Anfrage'),
    'not-found': (404, 'Ressource nicht gefunden'),
    'dependency-unavailable': (503, 'Abhängigkeit nicht verfügbar'),
    'model-unavailable': (503, 'Modell nicht verfügbar'),
    'internal-error': (500, 'Interner Fehler'),
}

class Problem(Exception):
    def __init__(self, kind, detail, **extensions):
        self.kind, self.detail, self.extensions = kind, detail, extensions
        super().__init__(detail)

def invalid(detail, field=None):
    location = {'parameter': field} if request.method == 'GET' else {'pointer': '/' + (field or '')}
    errors = {'errors': [{**location, 'detail': detail}]} if field else {}
    raise Problem('invalid-request', detail, **errors)

def text(data, key, required=True):
    if key not in data and not required:
        return None
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        invalid(key + ' muss ein nichtleerer String sein.', key)
    return value

def selection(data, aliases, default=None, required=False):
    values = [text(data, key) for key in aliases if key in data]
    if values and any(value != values[0] for value in values):
        invalid('Widersprüchliche Set-Kennungen.')
    if not values and required:
        invalid('embedding_set_id ist erforderlich.', 'embedding_set_id')
    return values[0] if values else default

def search_options(data, default_count):
    metric = data.get('metric', 'euclidean')
    if not isinstance(metric, str) or metric not in ('euclidean', 'cosine'):
        invalid('metric muss euclidean oder cosine sein.', 'metric')
    count = data.get('num_results', default_count)
    if type(count) is not int or not 1 <= count <= 100:
        invalid('num_results muss eine ganze Zahl zwischen 1 und 100 sein.', 'num_results')

def vector(data):
    value = data.get('vector')
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            invalid('vector muss eine Zahlenliste sein.', 'vector')
    if not isinstance(value, list) or len(value) != 1024:
        invalid('vector muss genau 1024 Zahlen enthalten.', 'vector')
    try:
        valid = all(type(x) in (int, float) and math.isfinite(x) for x in value)
    except OverflowError:
        valid = False
    if not valid:
        invalid('vector muss endliche Zahlen enthalten.', 'vector')
    if data.get('metric') == 'cosine' and not any(value):
        invalid('Cosine erfordert einen Vektor mit positiver Norm.', 'vector')

def validate(service):
    if request.routing_exception is not None:
        return
    if service == 'vector' and request.method == 'GET':
        if request.endpoint in ('count_chunks', 'get_chunk'):
            selection(request.args, ('embedding_set_id', 'embedding'))
        elif request.endpoint == 'find_chunks':
            text(request.args, 'query')
        return
    if request.method not in ('POST', 'DELETE'):
        return
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        invalid('Ein gültiges JSON-Objekt ist erforderlich.')
    if service == 'rag':
        text(data, 'query')
        selection(data, ('embedding_set_id', 'filter'))
        search_options(data, 5)
        text(data, 'reranker', required=False)
        text(data, 'answer_model', required=False)
        if type(data.get('top_k', 0)) is not int or data.get('top_k', 0) < 0:
            invalid('top_k muss eine ganze Zahl >= 0 sein.', 'top_k')
    elif service == 'reranker':
        text(data, 'query')
        text(data, 'model', required=False)
        docs = data.get('documents')
        if not isinstance(docs, list) or any(not isinstance(d, str) or not d.strip() for d in docs):
            invalid('documents muss eine Liste nichtleerer Strings sein.', 'documents')
    elif service == 'vector':
        selection(data, ('embedding_set_id', 'embedding'), required=request.endpoint in ('upsert_chunk', 'delete_chunk'))
        if request.endpoint in ('upsert_chunk', 'delete_chunk'):
            text(data, 'chunk_id')
        if request.endpoint == 'upsert_chunk' and data.get('chunktext') is not None and not isinstance(data['chunktext'], str):
            invalid('chunktext muss ein String oder null sein.', 'chunktext')
        if request.endpoint in ('upsert_chunk', 'search_vectors'):
            if request.endpoint == 'search_vectors':
                search_options(data, 10)
            vector(data)

def install(app, service):
    @app.before_request
    def boundary():
        supplied = request.headers.get('X-Request-ID', '')
        g.request_id = supplied if re.fullmatch(r'[A-Za-z0-9._-]{1,128}', supplied) else str(uuid4())
        g.stage = 'validation'
        validate(service)
        g.stage = {'rag': 'processing', 'vector': 'storage', 'reranker': 'reranking'}[service]

    @app.after_request
    def correlate(response):
        response.headers['X-Request-ID'] = g.request_id
        return response

    @app.errorhandler(Exception)
    def handle(error):
        headers = None
        if isinstance(error, Problem):
            status, title = TYPES[error.kind]
            kind, detail, extensions = 'urn:rag:problem:' + error.kind, error.detail, error.extensions
        elif isinstance(error, HTTPException):
            status, title = error.code, error.name
            kind, detail, extensions = 'about:blank', error.name, {}
            headers = error.get_response().headers
        else:
            app.logger.exception('Unhandled error request_id=%s stage=%s', g.request_id, g.stage)
            status, title = TYPES['internal-error']
            kind, detail, extensions = 'urn:rag:problem:internal-error', 'Ein interner Fehler ist aufgetreten.', {}
        response = jsonify(type=kind, title=title, status=status, detail=detail,
                           instance='urn:uuid:' + str(uuid4()), request_id=g.request_id,
                           stage=g.stage, retryable=False, **extensions)
        response.status_code = status
        response.content_type = 'application/problem+json'
        if headers:
            for key, value in headers.items():
                if key.lower() not in ('content-type', 'content-length'):
                    response.headers[key] = value
        return response

