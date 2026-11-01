from facebook_agent.graph import call_graph, check_required, error


def hide_comment(comment_id: str, page_token: str) -> dict:
    """Hide a comment: it stays visible only to its author and their friends.

    Sends POST /{comment_id} with is_hidden=true. Facebook refuses it for a comment written
    by the page itself (error 200).

    Parameters:
        - Input-comment_id (str, mandatory): ID of the comment, written by another account.
          Example: "POST_ID_EXAMPLE_COMMENT_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"success": true}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "success": true
                }
            }
        Errors:
            - validation: a mandatory parameter is empty (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(comment_id=comment_id, page_token=page_token):
            return invalid
        return call_graph(
            "POST", comment_id, page_token,
            data={"is_hidden": "true"},
            error_message="Échec du masquage du commentaire.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
