from facebook_agent.graph import call_graph, check_required, error

POST_FIELDS = "message,created_time,permalink_url,full_picture"


def get_post(post_id: str, page_token: str) -> dict:
    """Read a post of the page by its ID.

    Parameters:
        - Input-post_id (str, mandatory): ID of the post.
          Example: "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer with the fields message, created_time, permalink_url,
            full_picture and id. A field without value is absent (e.g. full_picture for a text post).
        Example (success):
            {
                "status": "success",
                "data": {
                    "message": "Test automatique facebook_agent 20261031-1232 (modifié)",
                    "created_time": "2026-10-31T11:32:55+0000",
                    "permalink_url": "https://www.facebook.com/EXAMPLE_LINK",
                    "id": "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE"
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
        return call_graph("GET", post_id, page_token, params={"fields": POST_FIELDS},
                          error_message="Échec de la lecture du post.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
