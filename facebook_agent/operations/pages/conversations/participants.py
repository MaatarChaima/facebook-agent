"""Shared helper for Messenger operations (not an operation itself)."""
from facebook_agent.graph import call_graph, error


def find_user_psid(conversation_id: str, page_token: str, page_id: str | int) -> tuple[str | None, dict | None]:
    """Find the user of a Messenger conversation (the participant who is not the page).

    IDs are compared as strings: the API returns strings, but page_id may be given as an int.

    Args:
        conversation_id: ID of the conversation.
        page_token: Page access token.
        page_id: ID of the page.

    Returns:
        (user_psid, None), or (None, error_result): an API error, or a "logic" error when
        no participant other than the page is found.
    """
    result = call_graph(
        "GET", conversation_id, page_token,
        params={"fields": "participants"},
        error_message="Échec de la récupération des participants.",
    )
    if result["status"] == "error":
        return None, result

    participants = result["data"].get("participants", {}).get("data", [])
    for participant in participants:
        if str(participant["id"]) != str(page_id):
            return participant["id"], None

    return None, error(
        "Impossible de trouver le PSID de l'utilisateur.",
        {"type": "logic", "errors": ["PSID utilisateur introuvable dans les participants"]},
    )
