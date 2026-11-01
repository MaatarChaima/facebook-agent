"""Shape an operation result for the LLM: only what it needs, in a form it cannot misread.

- Dates in local time.
- Fields that only cost tokens are removed (links, picture URLs, e-mail addresses).
- Messenger messages: one line per message with its author (name and ID), "page" or "client", the local
  time and the text (or "(sans texte : pièce jointe / réaction)"), newest first. A text is kept up to
  300 characters; beyond, it ends with "…[coupé]" (never shortened silently).
- Posts made by Facebook (a "story" such as a cover photo change, no "message") are marked
  "automatic": true: the API cannot delete them.
- Lists are sent in a compact form, one short object per item (IDs, dates, texts cut at 80
  characters, short values, authors and participants as {"name", "id"}: ban_user needs the ID), so
  that about 25 items fit in the size limit.
The full result is still shown to the user and kept in the log.
"""
from facebook_agent.agent.display import localize_times

# Champs qui ne servent qu'à l'affichage (cartes de l'interface web) ou coûtent des tokens : jamais envoyés au
# modèle. Les compteurs de réactions et de commentaires sont des objets imbriqués, retirés aussi.
DISPLAY_ONLY_KEYS = frozenset({"permalink_url", "full_picture", "picture", "images", "image_url", "link", "source",
                               "thumbnails", "reactions", "comments"})
DROP_KEYS = DISPLAY_ONLY_KEYS | {"email"}
# Champs demandés seulement pour les cartes d'une opération (ailleurs, la même clé peut servir au modèle)
TOOL_DISPLAY_KEYS = {"search_products": frozenset({"url"}), "list_albums": frozenset({"cover_photo"}),
                     "list_product_sets": frozenset({"product_count"}),
                     "list_product_feeds": frozenset({"product_count", "latest_upload"}),
                     "list_conversations": frozenset({"messages"})}
NO_TEXT = "(sans texte : pièce jointe / réaction)"
MESSAGE_TEXT_MAX = 300     # caractères gardés d'un message Messenger
CUT_MARK = "…[coupé]"      # texte coupé : dit explicitement, pour que le modèle ne devine pas
POST_TOOLS = frozenset({"list_posts", "list_scheduled_posts", "get_post"})
COMPACT_LISTS = frozenset({"list_posts", "list_scheduled_posts", "list_comments", "list_conversations", "list_photos",
                           "list_videos", "list_albums", "list_product_sets", "list_product_feeds", "search_products"})
COMPACT_TEXT = 80          # caractères gardés d'un texte dans une liste
COMPACT_VALUE = 40         # au-delà, une autre valeur texte est coupée aussi
TEXT_KEYS = frozenset({"message", "story", "name", "title", "description", "text", "snippet", "filter"})


def _drop(value, keys: frozenset = DROP_KEYS):
    """Copy of a JSON value without the given keys (DROP_KEYS by default), at every level."""
    if isinstance(value, dict):
        return {key: _drop(item, keys) for key, item in value.items() if key not in keys}
    if isinstance(value, list):
        return [_drop(item, keys) for item in value]
    return value


def messages_view(data: dict, page_id: str | None) -> dict:
    """Messenger messages as the LLM must read them (author and role never left to guess).

    Args:
        data: Result of list_conversation_messages ({"data": [...], "paging": ...}).
        page_id: ID of the page, to tell the page's messages from the client's ones.

    Returns:
        {"order": "du plus récent au plus ancien", "messages": [{"id", "from": {"name", "id"}, "role", "time",
        "text"}]},
        plus "paging" when the API gave one.
    """
    messages = []
    for item in data.get("data", []) if isinstance(data, dict) else []:
        author = item.get("from") or {}
        text = (item.get("message") or "").strip()
        messages.append({
            "id": item.get("id"),
            "from": _person(author),
            "role": "page" if page_id and str(author.get("id")) == str(page_id) else "client",
            "time": item.get("created_time"),
            "text": (text[:MESSAGE_TEXT_MAX] + CUT_MARK if len(text) > MESSAGE_TEXT_MAX else text) or NO_TEXT,
        })
    view = {"order": "du plus récent au plus ancien", "messages": messages}
    if isinstance(data, dict) and data.get("paging"):
        view["paging"] = data["paging"]
    return view


def _person(person) -> dict:
    """Author or participant as the LLM receives it: {"name", "id"} (the ID is needed by ban_user)."""
    return {"name": person.get("name"), "id": person.get("id")} if isinstance(person, dict) else {"name": person}


def _is_automatic(post) -> bool:
    """A post made by Facebook: a story (e.g. "a mis à jour sa photo de couverture") and no message."""
    return isinstance(post, dict) and bool(post.get("story")) and not post.get("message")


def mark_automatic(data):
    """Mark the posts made by Facebook, which the API cannot delete.

    Args:
        data: A post, or a list result {"data": [posts]}.

    Returns:
        A copy where each automatic post gets "automatic": true.
    """
    if _is_automatic(data):
        return {**data, "automatic": True}
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return {**data, "data": [{**post, "automatic": True} if _is_automatic(post) else post
                                 for post in data["data"]]}
    return data


def _cut(text: str, limit: int) -> str:
    """Text cut at limit characters, with an ellipsis."""
    return text if len(text) <= limit else text[:limit] + "…"


def compact_item(item):
    """One list item in a compact form: IDs whole, texts cut at 80 characters, authors and participants
    as {"name", "id"}.

    Args:
        item: One item of a list result.

    Returns:
        A new dict without the nested objects (images, attachments...), or the item itself if it is
        not a dict.
    """
    if not isinstance(item, dict):
        return item
    compact = {}
    for key, value in item.items():
        if key == "id" or key.endswith("_id") or isinstance(value, (bool, int, float)) or value is None:
            compact[key] = value
        elif isinstance(value, str):
            compact[key] = _cut(value, COMPACT_TEXT if key in TEXT_KEYS else COMPACT_VALUE)
        elif key == "from" and isinstance(value, dict):
            compact[key] = _person(value)
        elif key in ("participants", "senders") and isinstance(value, dict):
            compact[key] = [_person(person) for person in value.get("data", []) if isinstance(person, dict)]
    return compact


def compact_list(data):
    """Compact form of a list result (see compact_item).

    Args:
        data: A list result ({"data": [...]} or [...]).

    Returns:
        A copy with compact items; any other value is returned unchanged.
    """
    if isinstance(data, list):
        return [compact_item(item) for item in data]
    if isinstance(data, dict) and isinstance(data.get("data"), list):
        return {**data, "data": [compact_item(item) for item in data["data"]]}
    return data


def for_llm(name: str, data, page_id: str | None = None):
    """Data of a successful result, as sent to the LLM (before the size limit).

    Args:
        name: Operation name.
        data: The "data" of the result.
        page_id: ID of the page (for the Messenger messages).

    Returns:
        A new value: local dates, without the useless fields, Messenger messages reshaped,
        automatic posts marked, lists compact.
    """
    data = localize_times(data)
    if name == "list_conversation_messages":
        data = messages_view(data, page_id)
    if name in POST_TOOLS:
        data = mark_automatic(data)
    data = _drop(data, DROP_KEYS | TOOL_DISPLAY_KEYS.get(name, frozenset()))
    return compact_list(data) if name in COMPACT_LISTS else data
