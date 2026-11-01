from facebook_agent.graph import check_required, error
from facebook_agent.operations.pages.comments.comment_publishing import publish_comment


def create_comment(post_id: str, message: str, page_token: str) -> dict:
    """Publish a comment of the page on a post.

    Sends POST /{post_id}/comments.

    Parameters:
        - Input-post_id (str, mandatory): ID of the post.
          Example: "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE"
        - Input-message (str, mandatory): Text of the comment.
          Example: "Thank you for your message"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<id of the new comment>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "POST_ID_EXAMPLE_COMMENT_ID_EXAMPLE"
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
        if invalid := check_required(post_id=post_id, message=message, page_token=page_token):
            return invalid

        return publish_comment(post_id, message, page_token, "Échec de la création du commentaire.")

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
