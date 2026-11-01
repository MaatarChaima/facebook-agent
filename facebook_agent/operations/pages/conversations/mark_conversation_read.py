from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.operations.pages.conversations.participants import find_user_psid


def mark_conversation_read(conversation_id: str, page_token: str, page_id: str) -> dict:
    """Mark a Messenger conversation of the page as read (sender action mark_seen).

    The user is the conversation participant whose ID differs from page_id (read with
    GET /{conversation_id}?fields=participants), then POST me/messages is sent. Facebook
    only accepts it within 24 hours after the user's last message to the page.

    Parameters:
        - Input-conversation_id (str, mandatory): ID of the conversation.
          Example: "CONVERSATION_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-page_id (str, mandatory): ID of the page, used to recognize the page among the participants.
          Example: "PAGE_ID_EXAMPLE"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"recipient_id": "<user PSID>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "recipient_id": "USER_PSID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty (no request is sent).
            - logic: no participant other than the page was found in the conversation.
            - api: reading the participants or sending the action failed (details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(conversation_id=conversation_id, page_token=page_token, page_id=page_id):
            return invalid

        user_psid, failure = find_user_psid(conversation_id, page_token, page_id)
        if failure:
            return failure

        return call_graph(
            "POST", "me/messages", page_token,
            json_body={"recipient": {"id": user_psid}, "sender_action": "mark_seen"},
            error_message="Échec du marquage de la conversation comme lue.",
        )

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
