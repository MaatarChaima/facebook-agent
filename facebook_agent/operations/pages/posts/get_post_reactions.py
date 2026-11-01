from facebook_agent.graph import check_required, error, fetch_list


def get_post_reactions(
    post_id: str,
    page_token: str,
    all_pages: bool = False,
    limit: int | None = None,
) -> dict:
    """List the reactions to a post.

    Parameters:
        - Input-post_id (str, mandatory): ID of the post.
          Example: "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 3

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of reactions (id, name and type, e.g. LIKE or LOVE),
            and "paging" holds the cursors (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": []
                }
            }
        Errors:
            - validation: a mandatory parameter is empty or limit is not an integer from 1 to 100 (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(post_id=post_id, page_token=page_token):
            return invalid
        return fetch_list(f"{post_id}/reactions", page_token, all_pages=all_pages, limit=limit,
                          error_message="Échec de la récupération des réactions du post.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
