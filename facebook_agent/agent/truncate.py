"""Shorten an operation result before sending it to the LLM (rate limit of 8,000 tokens per minute).

The user always sees the full result; only the copy sent to the LLM is shortened, in this order:
1. the pagination cursors are removed (the LLM uses all_pages instead);
2. long texts are shortened (200, then 80, then 40 characters);
3. then, for a list, the last items are removed.
IDs and every field are always kept: only texts get shorter and items fewer. The LLM is told
what was shortened.
"""
import json

MAX_CHARS = 1000  # environ 200 tokens réels par résultat
LIST_MAX_CHARS = 4000  # liste compacte : environ 25 éléments (ID, date, 80 caractères de texte)
MESSAGES_MAX_CHARS = 5000  # messages Messenger : textes gardés (300 caractères), les plus anciens retirés si besoin
TEXT_LIMITS = (200, 80, 40)
ELLIPSIS = "…"


def _is_id_key(key: str | None) -> bool:
    """IDs are never shortened (id, post_id, retailer_id, ...)."""
    return key is not None and (key == "id" or key.endswith("_id") or key.endswith("_ids"))


def _shorten(value, limit: int, key: str | None = None):
    """Copy of a JSON value whose long strings are cut at limit characters (IDs excepted)."""
    if isinstance(value, dict):
        return {k: _shorten(v, limit, k) for k, v in value.items()}
    if isinstance(value, list):
        return [_shorten(item, limit, key) for item in value]
    if isinstance(value, str) and len(value) > limit and not _is_id_key(key):
        return value[:limit] + ELLIPSIS
    return value


def _size(value) -> int:
    """Length of the JSON sent to the LLM."""
    return len(json.dumps(value, ensure_ascii=False))


def _items(value) -> tuple[list | None, str | None]:
    """The list to cut: the value itself, or its "data" list (raw Graph API list)."""
    if isinstance(value, list):
        return value, None
    for key in ("data", "messages"):  # liste brute de la Graph API, ou vue des messages Messenger
        if isinstance(value, dict) and isinstance(value.get(key), list):
            return value[key], key
    return None, None


def item_counts(original, shortened) -> tuple[int, int] | None:
    """Number of items of a list result before and after the shortening.

    Args:
        original: The value before truncate_for_llm.
        shortened: The value it returned.

    Returns:
        (items received, items sent), or None if the value is not a list.
    """
    received, _ = _items(original)
    sent, _ = _items(shortened)
    if received is None or sent is None:
        return None
    return len(received), len(sent)


def truncate_for_llm(data, max_chars: int = MAX_CHARS, shorten_texts: bool = True) -> tuple[object, str | None]:
    """Return (shortened copy of data, note for the LLM or None if nothing was changed).

    Args:
        data: The "data" of a successful operation result.
        max_chars: Target size of the JSON sent to the LLM.
        shorten_texts: False to keep the texts whole and only remove the last items (messages).

    Returns:
        The copy and, when something was shortened, a note in French that says how many
        items are shown and how to get the rest.
    """
    notes = []
    value = data
    has_more = False
    if isinstance(value, dict) and "paging" in value:
        has_more = bool((value.get("paging") or {}).get("next"))
        value = {k: v for k, v in value.items() if k != "paging"}
    if isinstance(value, dict) and value.get("truncated"):
        has_more = True  # limite de 50 pages de all_pages atteinte

    shortened = False
    for limit in TEXT_LIMITS if shorten_texts else ():
        if _size(value) <= max_chars:
            break
        value = _shorten(value, limit)
        shortened = True
    if shortened:
        notes.append("textes raccourcis (ID complets)")

    items, list_key = _items(value)
    total = len(items) if items is not None else 0
    shown = total
    if items is not None:
        while shown > 1 and _size(value) > max_chars:
            shown -= 1
            kept = items[:shown]
            value = kept if list_key is None else {**value, list_key: kept}
    if items is not None and (shown < total or has_more):
        count = f"{shown} éléments affichés sur {total}" + (" (d'autres pages existent)" if has_more else "")
        notes.insert(0, count + ", utilise all_pages ou affine la demande")
    return value, ("Résultat raccourci : " + " ; ".join(notes) + ".") if notes else None
