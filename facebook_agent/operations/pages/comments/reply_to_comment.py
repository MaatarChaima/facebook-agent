from facebook_agent.graph import check_required, error
from facebook_agent.operations.pages.comments.comment_publishing import publish_comment


def reply_to_comment(comment_id: str, message: str, page_token: str) -> dict:
    """Reply as the page to a comment.

    A reply is a comment published on the parent comment (POST /{comment_id}/comments).

    Parameters:
        - Input-comment_id (str, mandatory): ID of the comment to answer.
          Example: "POST_ID_EXAMPLE_COMMENT_ID_EXAMPLE"
        - Input-message (str, mandatory): Text of the reply.
          Example: "Thank you!"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<id of the reply>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "POST_ID_EXAMPLE_REPLY_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error), or answered
              without id (details.response).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(comment_id=comment_id, message=message, page_token=page_token):
            return invalid
        # Une réponse est un commentaire publié sur le commentaire parent (POST /{comment-id}/comments).
        return publish_comment(comment_id, message, page_token, "Échec de la réponse au commentaire.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
