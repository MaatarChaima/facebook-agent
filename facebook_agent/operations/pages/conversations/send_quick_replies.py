from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.operations.pages.conversations.participants import find_user_psid


def send_quick_replies(
    conversation_id: str, text: str, options: list[str | dict], page_token: str, page_id: str
) -> dict:
    """Send a text message with quick-reply buttons in a Messenger conversation of the page.

    The recipient is the conversation participant whose ID differs from page_id (read with
    GET /{conversation_id}?fields=participants). Facebook only accepts such messages within
    24 hours after the user's last message to the page.

    Parameters:
        - Input-conversation_id (str, mandatory): ID of the Messenger conversation.
          Example: "CONVERSATION_ID_EXAMPLE"
        - Input-text (str, mandatory): Text shown above the buttons.
          Example: "Do you want to continue?"
        - Input-options (list, mandatory): Buttons, as strings or dicts.
          A string becomes a button whose payload is the text in upper case ("Yes" -> "YES");
          a dict must have "title" and may have "payload" (default: title in upper case).
          Example: ["Yes", "No", {"title": "Later", "payload": "LATER"}]
        - Input-page_token (str, mandatory): Page access token with the pages_messaging permission.
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
            - unexpected: any other exception, e.g. a dict option without "title" (details.info).
    """
    try:
        if invalid := check_required(
            conversation_id=conversation_id, text=text, options=options, page_token=page_token, page_id=page_id
        ):
            return invalid

        user_psid, failure = find_user_psid(conversation_id, page_token, page_id)
        if failure:
            return failure

        # Construire les quick replies
        quick_replies = []
        for opt in options:
            if isinstance(opt, dict):
                quick_replies.append({
                    "content_type": "text",
                    "title": opt["title"],
                    "payload": opt.get("payload", opt["title"].upper()),
                })
            else:
                quick_replies.append({
                    "content_type": "text",
                    "title": opt,
                    "payload": opt.upper(),
                })

        return call_graph(
            "POST", "me/messages", page_token,
            json_body={
                "recipient": {"id": user_psid},
                "message": {"text": text, "quick_replies": quick_replies},
            },
            error_message="Échec de l'envoi des réponses rapides.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
