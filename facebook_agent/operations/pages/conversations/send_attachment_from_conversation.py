import json

from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.local_files import extension, is_url, missing_file_error
from facebook_agent.operations.pages.conversations.participants import find_user_psid

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")


def _attachment_type(file_path: str) -> str:
    """Messenger attachment type: "image" for .jpg/.jpeg/.png/.gif, otherwise "file"."""
    return "image" if extension(file_path) in IMAGE_EXTENSIONS else "file"


def send_attachment_from_conversation(page_id: str, conversation_id: str, file_path: str, page_token: str) -> dict:
    """Send a file or an image in a Messenger conversation of the page.

    The recipient is the conversation participant whose ID differs from page_id (read with
    GET /{conversation_id}?fields=participants). Facebook only accepts such messages within
    24 hours after the user's last message to the page.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page, used to recognize the page among the participants.
          Example: "PAGE_ID_EXAMPLE"
        - Input-conversation_id (str, mandatory): ID of the conversation.
          Example: "CONVERSATION_ID_EXAMPLE"
        - Input-file_path (str, mandatory): http(s) URL of a hosted file, or path of a local file (sent as multipart).
          A .jpg, .jpeg, .png or .gif file is sent as an "image" (shown in the conversation);
          any other file as a "file" (offered for download).
          Example: "https://example.com/photo.jpg"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict with recipient_id, message_id and attachment_id, the raw Graph API answer.
        Example (success):
            {
                "status": "success",
                "data": {
                    "recipient_id": "USER_PSID_EXAMPLE",
                    "message_id": "MESSAGE_ID_EXAMPLE",
                    "attachment_id": "ATTACHMENT_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, or the local file is not found (no request is sent).
            - logic: no participant other than the page was found in the conversation.
            - api: reading the participants or sending the attachment failed (details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception, e.g. a local file that cannot be read (details.info).
    """
    try:
        if invalid := check_required(
            page_id=page_id, conversation_id=conversation_id, file_path=file_path, page_token=page_token
        ):
            return invalid
        # Un chemin qui n'est pas une URL http(s) doit être un fichier existant (vérifié avant toute requête)
        if not is_url(file_path) and (invalid := missing_file_error(file_path)):
            return invalid

        user_psid, failure = find_user_psid(conversation_id, page_token, page_id)
        if failure:
            return failure

        # Une image est affichée dans la conversation ; tout autre fichier est proposé au téléchargement.
        attachment_type = _attachment_type(file_path)

        # Fichier hébergé : envoi par URL
        if is_url(file_path):
            return call_graph(
                "POST", "me/messages", page_token,
                json_body={
                    "recipient": {"id": user_psid},
                    "message": {
                        "attachment": {
                            "type": attachment_type,
                            "payload": {"url": file_path, "is_reusable": True},
                        }
                    },
                },
                error_message="Échec de l'envoi de la pièce jointe.",
            )

        # Fichier local : upload multipart
        data = {
            "recipient": json.dumps({"id": user_psid}, separators=(",", ":")),
            "message": json.dumps({"attachment": {"type": attachment_type, "payload": {"is_reusable": True}}},
                                  separators=(",", ":")),
        }
        with open(file_path, "rb") as attachment:
            return call_graph(
                "POST", "me/messages", page_token,
                data=data,
                files={"filedata": attachment},
                error_message="Échec de l'envoi de la pièce jointe.",
                timeout=UPLOAD_TIMEOUT,
            )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
