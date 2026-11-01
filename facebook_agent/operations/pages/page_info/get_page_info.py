from facebook_agent.graph import call_graph, check_required, error


def get_page_info(page_id: str, page_token: str) -> dict:
    """Read the main information of the page.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer with the fields name, fan_count, about, category and id.
            A field without value is absent (e.g. about when the page has no description).
        Example (success):
            {
                "status": "success",
                "data": {
                    "name": "Example Page",
                    "fan_count": 2,
                    "category": "Clothing (Brand)",
                    "id": "PAGE_ID_EXAMPLE"
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
        if invalid := check_required(page_id=page_id, page_token=page_token):
            return invalid
        return call_graph(
            "GET", page_id, page_token,
            params={"fields": "name,fan_count,about,category"},
            error_message="Échec de la récupération des informations de la page.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
