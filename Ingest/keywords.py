from gateway import call_ollama_gateway, call_ai_gateway
import logging

MAX_SIZE = 1000  # Max Size für 5 Keywords

def get_keyword_question(chunk):
    chunk_len = len(chunk)
    fifth = MAX_SIZE // 5
    if chunk_len < fifth:
        n_keywords = 0
    elif chunk_len < 2 * fifth:
        n_keywords = 1
    elif chunk_len < 3 * fifth:
        n_keywords = 2
    elif chunk_len < 4 * fifth:
        n_keywords = 3
    else:
        n_keywords = 4

    if n_keywords == 0:
        question = "Generiere mir ein keyword aus dem Kontext. Das keyword soll prägnant, sachlich und inhaltlich beschreibend sein."
    else:
        # question = f"Generiere mir {n_keywords} keywords aus dem Kontext. Die keywords sollen prägnant, sachlich und inhaltlich beschreibend sein. Wenn in dem Kontext Namen von Personen oder Orten vorkommen, sollen diese bevorzugt als keyword verwendet werden. Sind zu Namen noch Attribute wie Titel oder ähnliches vorhanden, sollen diese mit zu dem Namen gestellt werden. Die keywords sollen als kommaseparierte Liste ausgegeben werden. Die Antwort soll ausschließlich diese Liste enthalten."
        question = (f"Extrahiere genau einen zentralen Begriff sowie {n_keywords} Keywords aus dem Kontext und gib mir diese als kommaseparierte Liste ohne weiteren Text. "
                   "Priorität der keywords: "
                    "(1) Personen mit Titel/Attribut, "
                    "(2) Götter/Orte/Ethnonyme, "
                    "(3) zentrale Sachbegriffe. "
                    "Titel-Regel: Wenn ein Name unmittelbar mit einem Titel/Attribut genannt wird (z. B. „König“, „Dr.“, „Göttin“), verwende die Kombination als EIN Keyword. "
                    "Span-Genauigkeit: Gib die exakte Zeichenkette aus dem Kontext wieder (inkl. Groß-/Kleinschreibung und Schreibweise; keine Normalisierung wie Umlaute ergänzen/ändern). "
                    "Format: Gib mir die Antwort als kommaseparierte Liste, beginnend mit dem gefundenen zentralen Begriff und gefolgt von den gefundenen keywords. Keine Halluzinationen: Verwende ausschließlich Begriffe und Keywords, die genau so im Kontext stehen. "
                    "Variante bei Mehrfachformen: Wenn derselbe Begriff in mehreren Sprachen/Schreibungen vorkommt, wähle die im Kontext erstgenannte Form."
                    )
    return question

def get_keyword_question2(chunk):
    chunk_len = len(chunk)
    fifth = MAX_SIZE // 5
    if chunk_len < fifth:
        n_keywords = 0
    elif chunk_len < 2 * fifth:
        n_keywords = 1
    elif chunk_len < 3 * fifth:
        n_keywords = 2
    elif chunk_len < 4 * fifth:
        n_keywords = 3
    else:
        n_keywords = 4

    if n_keywords == 0:
        question = "Generiere mir ein keyword aus dem Kontext. Das keyword soll prägnant, sachlich und inhaltlich beschreibend sein."
    else:
        # question = f"Generiere mir {n_keywords} keywords aus dem Kontext. Die keywords sollen prägnant, sachlich und inhaltlich beschreibend sein. Wenn in dem Kontext Namen von Personen oder Orten vorkommen, sollen diese bevorzugt als keyword verwendet werden. Sind zu Namen noch Attribute wie Titel oder ähnliches vorhanden, sollen diese mit zu dem Namen gestellt werden. Die keywords sollen als kommaseparierte Liste ausgegeben werden. Die Antwort soll ausschließlich diese Liste enthalten."
        question = (f"generiere mir  {n_keywords} Keywords aus dem Kontext und gib mir diese als kommaseparierte Liste ohne weiteren Text. "
                    )
    return question

def get_keywords_openai(chunk):
    """Generiert eine Antwort basierend auf dem Kontext und der Frage über die Ollama-API."""
    system_prompt = (
        "Du bist ein Experte für römische Geschichte. Du erfüllst Aufgaben zu Texten, die als Kontext übergeben werden."
    )
    question = get_keyword_question(chunk)

    query = f"Betrachte folgenden Kontext:\n{chunk}\n\nAufgabe: {question}"

    response = call_ai_gateway(chunk, system_prompt, query)

    data = response.json()

    answer_tokens = data["usage"]["completion_tokens"]
    prompt_tokens = data["usage"]["prompt_tokens"]

    metrics_report = (
        f"\n\n--- [Ausführungs-Metriken] ---\n"
        f"Prompt-Token:       {prompt_tokens} Token\n"
        f"Antwort-Token:      {answer_tokens} Token\n"
    )

    answer = data["choices"][0]["message"]["content"]


    return answer, metrics_report, question

def get_keywords_ollama(chunk):
    """Generiert eine Antwort basierend auf dem Kontext und der Frage über die Ollama-API."""
    system_prompt = (
        "Du bist ein Experte für die Analyse von Texten. Du extrahierst keywords aus Texten die als Kontext übergeben werden."
        "Priorität der keywords: "
        "(1) ein zentraler Begriff, der den Kontext insgesamt charakterisiert, "
        "(2) Personen mit Titel/Attribut, "
        "(3) Götter/Orte/Ethnonyme, "
        "(4) zentrale Sachbegriffe. "
        "Titel-Regel: Wenn ein Name unmittelbar mit einem Titel/Attribut genannt wird (z. B. „König“, „Dr.“, „Göttin“), verwende die Kombination als EIN Keyword. "
        "Länge der Keywords: Es sollen nicht mehr als drei Wörter für ein keyword verwendet werden."
        "Variante bei Mehrfachformen: Wenn derselbe Begriff in mehreren Sprachen/Schreibungen vorkommt, wähle die im Kontext erstgenannte Form."
        "Span-Genauigkeit: Gib die exakte Zeichenkette aus dem Kontext wieder (inkl. Groß-/Kleinschreibung und Schreibweise; keine Normalisierung wie Umlaute ergänzen/ändern). "
        "Format: Gib mir die Antwort als kommaseparierte Liste, beginnend mit dem gefundenen zentralen Begriff und gefolgt von den gefundenen keywords. "
        "Keine Halluzinationen: Verwende ausschließlich Begriffe und Keywords, die genau so im Kontext stehen. "

    )
    question = get_keyword_question2(chunk)

    query = f"<<BEGINN KONTEXT>>:\n{chunk}\n<<ENDE KONTEXT>>\nFrage: {question}\nBerücksichtige, dass als Antwort eusschließliche ien Mommaseparierte Liste von Keywords gewünscht ist, keine weiteren Erläuterungen oder Ergänzungen."

    response = call_ollama_gateway(chunk, system_prompt, query)

    data = response.json()

    # answer_tokens = data["usage"]["completion_tokens"]
    # prompt_tokens = data["usage"]["prompt_tokens"]

    total_duration = data.get("total_duration", 0) / 1e9  # Sekunden
    load_duration = data.get("load_duration", 0) / 1e6    # Millisekunden
    prompt_eval_duration = data.get("prompt_eval_duration", 0) / 1e9
    eval_duration = data.get("eval_duration", 0) / 1e9

    metrics_report = (
        f"\n\n--- [Ausführungs-Metriken] ---\n"
        f"Duration:       {total_duration} Sekunden\n"
        #        f"Antwort-Token:      {answer_tokens} Token\n"
    )

    # Sicherstellen, dass das content-Feld existiert (kommt vor wenn Antworten gefiltert werden wg zb violence)
    answer = ""
    try:
        answer = data.get("message", {}).get("content", "")
    except (KeyError, IndexError, TypeError):
        logging.warning("Keine Keywords generiert:\n"+query+"\n\n")
        answer = ""


    return answer, metrics_report, question
