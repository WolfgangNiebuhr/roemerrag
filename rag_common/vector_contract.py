"""Vector API input constraints used by the Vector API and its RAG client."""
import math


class VectorInputError(ValueError):
    def __init__(self, field, detail):
        self.field = field
        super().__init__(detail)


def parse_search_options(data, default_count):
    metric = data.get('metric', 'euclidean')
    if not isinstance(metric, str) or metric not in ('euclidean', 'cosine'):
        raise VectorInputError('metric', 'metric muss euclidean oder cosine sein.')
    count = data.get('num_results', default_count)
    if type(count) is not int or not 1 <= count <= 100:
        raise VectorInputError('num_results', 'num_results muss eine ganze Zahl zwischen 1 und 100 sein.')
    return metric, count


def parse_vector(value, metric):
    if not isinstance(value, list):
        raise VectorInputError('vector', 'vector muss eine JSON-Zahlenliste sein.')
    if len(value) != 1024:
        raise VectorInputError('vector', 'vector muss genau 1024 Zahlen enthalten.')
    try:
        valid = all(type(x) in (int, float) and math.isfinite(x) for x in value)
    except OverflowError:
        valid = False
    if not valid:
        raise VectorInputError('vector', 'vector muss endliche Zahlen enthalten.')
    if metric == 'cosine' and not any(value):
        raise VectorInputError('vector', 'Cosine erfordert einen Vektor mit positiver Norm.')
    return value


def embedding_norm(vector):
    """Validate an Ollama embedding before normalization."""
    parse_vector(vector, None)
    norm = math.hypot(*vector)
    if not math.isfinite(norm) or norm <= 0:
        raise VectorInputError("vector", "Das Embedding muss eine positive, endliche Norm haben.")
    return norm
