# Definiert den Prompt für die Keyword-Anreicherung.

MAX_SIZE = 1000  # Max Size für 5 Keywords

# Waehlt anhand der Chunklaenge eine Frage mit passender Keyword-Anzahl.
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
        question = (f"generiere mir  {n_keywords} Keywords aus dem Kontext und gib mir diese als kommaseparierte Liste ohne weiteren Text. "
                    )
    return question

# Baut den Systemprompt und die kontextbezogene Keyword-Anfrage zusammen.
def keyword_messages(chunk):
    """Erstellt Systemprompt, Anfrage und Frage für einen Chunk."""
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

    return system_prompt, query, question
