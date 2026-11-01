from facebook_agent.graph import call_graph, check_required, error


def unlike_post(post_id: str, page_token: str) -> dict:
    """Remove the like of the page from a post.

    Parameters:
        - Input-post_id (str, mandatory): ID of the post.
          Example: "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE"
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
        if invalid := check_required(post_id=post_id, page_token=page_token):
            return invalid
        return call_graph(
            "DELETE", f"{post_id}/likes", page_token, error_message="Échec du retrait du like du post."
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
