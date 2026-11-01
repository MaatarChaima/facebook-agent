"""Find texts of other people (comments, messages, names) that look like instructions to the agent.

Such a text is never executed (the tool results are data, and every write needs the user's
confirmation): it is only reported, to the LLM and to the user. The patterns cover French and
English; a match is a warning sign, not a proof.
"""
import re

TEXT_KEYS = ("message", "story", "name", "title", "description", "text", "caption")
PATTERNS = [
    r"\bignor\w*\s+(?:toutes?\s+|tous\s+)?(?:tes|vos|les|ses)\s+(?:\w+\s+)?(?:instructions?|consignes?|règles?)",
    r"\bignore\s+(?:all\s+|any\s+)?(?:previous|prior|your|the|above)\s+(?:\w+\s+)?(?:instructions?|rules?|prompts?)",
    r"\b(?:oublie|oubliez|forget|disregard)\s+(?:\w+\s+){0,3}(?:instructions?|consignes?|rules?|prompts?)",
    r"\b(?:supprim\w*|efface\w*|delete|remove|erase)\s+(?:tous|toutes|all|every|chaque)\b",
    r"\b(?:bannis|bannissez|ban)\s+(?:tous|toutes|all|everyone)\b",
    r"\b(?:nouvelles?\s+instructions?|new\s+instructions?|system\s*prompt|prompt\s+système)\b",
    r"^\s*(?:system|système|assistant|admin(?:istrat\w*)?)\s*:",
    r"\b(?:tu\s+es\s+maintenant|you\s+are\s+now|agis\s+comme|act\s+as)\b",
]
SUSPICIOUS = re.compile("|".join(f"(?:{p})" for p in PATTERNS), re.IGNORECASE | re.MULTILINE)
EXCERPT_CHARS = 120


def find_suspicious(data) -> list[dict]:
    """Texts of a result that look like instructions to the agent.

    Args:
        data: The "data" of an operation result.

    Returns:
        [{"id": ID of the object that holds the text (or None), "excerpt": the text, shortened}].
    """
    found: list[dict] = []

    def walk(value, owner_id):
        if isinstance(value, dict):
            owner_id = value.get("id", owner_id)
            for key, item in value.items():
                if key in TEXT_KEYS and isinstance(item, str) and SUSPICIOUS.search(item):
                    excerpt = item if len(item) <= EXCERPT_CHARS else item[:EXCERPT_CHARS] + "…"
                    found.append({"id": owner_id, "excerpt": excerpt})
                elif isinstance(item, (dict, list)):
                    walk(item, owner_id)
        elif isinstance(value, list):
            for item in value:
                walk(item, owner_id)

    walk(data, None)
    return found


def warning_sentence(tool: str, count: int) -> str:
    """Sentence added to the answer when instructions to the agent were found and ignored.

    Args:
        tool: Operation whose result held the texts (list_comments, list_conversation_messages...).
        count: Number of suspicious texts.

    Returns:
        The sentence in French, e.g. "Ce commentaire contient une instruction adressée à l'agent ;
        elle a été ignorée."
    """
    one, many = (("Ce commentaire", "commentaires") if "comment" in tool else
                 ("Ce message", "messages") if "message" in tool or "conversation" in tool else
                 ("Ce contenu", "contenus"))
    if count == 1:
        return f"{one} contient une instruction adressée à l'agent ; elle a été ignorée."
    return f"{count} {many} contiennent une instruction adressée à l'agent ; elles ont été ignorées."
