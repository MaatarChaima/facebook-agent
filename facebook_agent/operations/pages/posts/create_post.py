from facebook_agent.graph import call_graph, check_required, error


def create_post(message: str, page_token: str) -> dict:
    """Publish a text post on the page.

    Sends POST me/feed: with a Page token, "me" is the page itself.

    Parameters:
        - Input-message (str, mandatory): Text of the post.
          Example: "Hello from the page"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<page id>_<post id>"}.
        Example (success):
            {
                "status": "success",
                "data": {
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
        if invalid := check_required(message=message, page_token=page_token):
            return invalid
        return call_graph(
            "POST", "me/feed", page_token,
            data={"message": message},
            error_message="Échec de la création du post.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
