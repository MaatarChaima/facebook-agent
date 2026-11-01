from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.operations.pages.conversations.participants import find_user_psid


def send_text_message(conversation_id: str, text: str, page_token: str, page_id: str) -> dict:
    """Send a text message in a Messenger conversation of the page.

    The recipient is the conversation participant whose ID differs from page_id (read with
    GET /{conversation_id}?fields=participants). Facebook only accepts such messages within
    24 hours after the user's last message to the page.

    Parameters:
        - Input-conversation_id (str, mandatory): ID of the conversation.
          Example: "CONVERSATION_ID_EXAMPLE"
        - Input-text (str, mandatory): Text of the message.
          Example: "Hello, how can we help you?"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-page_id (str, mandatory): ID of the page, used to recognize the page among the participants.
          Example: "PAGE_ID_EXAMPLE"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict with recipient_id and message_id, the raw Graph API answer.
        Example (success):
            {
                "status": "success",
                "data": {
                    "recipient_id": "USER_PSID_EXAMPLE",
                    "message_id": "MESSAGE_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty (no request is sent).
            - logic: no participant other than the page was found in the conversation.
            - api: reading the participants or sending the message failed (details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(
            conversation_id=conversation_id, text=text, page_token=page_token, page_id=page_id
        ):
            return invalid

        user_psid, failure = find_user_psid(conversation_id, page_token, page_id)
        if failure:
            return failure

        return call_graph(
            "POST", "me/messages", page_token,
            json_body={"recipient": {"id": user_psid}, "message": {"text": text}},
            error_message="Échec de l'envoi du message.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
