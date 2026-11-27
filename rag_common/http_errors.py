"""Shared Flask handlers for the project's HTTP error contract."""
from contextlib import contextmanager
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


def invalid_request(detail, field=None, *, query_parameter=False):
    errors = {}
    if field:
        location = {'parameter': field} if query_parameter else {'pointer': '/' + field}
        errors = {'errors': [{**location, 'detail': detail}]}
    raise Problem('invalid-request', detail, **errors)


@contextmanager
def validating_request():
    """Keep the validation stage if parsing raises."""
    previous_stage = g.stage
    g.stage = 'validation'
    yield
    g.stage = previous_stage


def json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        invalid_request('Ein gültiges JSON-Objekt ist erforderlich.')
    return data


def text_field(data, key, *, required=True, query_parameter=False):
    if key not in data and not required:
        return None
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        invalid_request(key + ' muss ein nichtleerer String sein.', key, query_parameter=query_parameter)
    return value


def boolean_field(data, key, *, query_parameter=False):
    if key not in data:
        return False
    value = data[key]
    if query_parameter and value in ("true", "false"):
        return value == "true"
    if not query_parameter and type(value) is bool:
        return value
    invalid_request(key + " muss ein boolescher Wert sein.", key, query_parameter=query_parameter)


def _render_problem(type_uri, status, title, detail, extensions):
    response = jsonify(type=type_uri, title=title, status=status, detail=detail,
                       instance='urn:uuid:' + str(uuid4()), request_id=g.request_id,
                       stage=g.stage, retryable=False, **extensions)
    response.status_code = status
    response.content_type = 'application/problem+json'
    return response


def problem_response(kind, detail, **extensions):
    status, title = TYPES[kind]
    return _render_problem('urn:rag:problem:' + kind, status, title, detail, extensions)


def install(app, *, default_stage):
    @app.before_request
    def correlate_request():
        supplied = request.headers.get('X-Request-ID', '')
        g.request_id = supplied if re.fullmatch(r'[A-Za-z0-9._-]{1,128}', supplied) else str(uuid4())
        g.stage = default_stage

    @app.after_request
    def correlate(response):
        response.headers['X-Request-ID'] = g.request_id
        return response

    @app.errorhandler(Exception)
    def handle(error):
        if isinstance(error, Problem):
            return problem_response(error.kind, error.detail, **error.extensions)
        if isinstance(error, HTTPException):
            response = _render_problem('about:blank', error.code, error.name, error.name, {})
            for key, value in error.get_response().headers.items():
                if key.lower() not in ('content-type', 'content-length'):
                    response.headers[key] = value
            return response
        app.logger.exception('Unhandled error request_id=%s stage=%s', g.request_id, g.stage)
        return problem_response('internal-error', 'Ein interner Fehler ist aufgetreten.')
