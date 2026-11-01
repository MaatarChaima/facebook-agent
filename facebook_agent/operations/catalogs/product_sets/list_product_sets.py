from facebook_agent.graph import check_required, error, fetch_list

# product_count sert aux cartes de l'interface web (retiré pour le modèle)
PRODUCT_SET_FIELDS = "id,name,filter,product_count"


def list_product_sets(
    catalog_id: str,
    access_token: str,
    all_pages: bool = False,
    limit: int | None = None,
) -> dict:
    """List the product sets of a catalog.

    Parameters:
        - Input-catalog_id (str, mandatory): ID of the catalog.
          Example: "CATALOG_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 3

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of product sets (id, name,
            filter = the rule choosing its products, product_count = number of products in the set), and "paging" holds the cursors (absent when
            all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "ID_EXAMPLE_20",
                            "name": "Example name",
                            "product_count": 3
                        }
                    ],
                    "paging": {
                        "cursors": {
                            "before": "CURSOR_BEFORE_EXAMPLE",
                            "after": "CURSOR_AFTER_EXAMPLE"
                        }
                    }
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
        if invalid := check_required(catalog_id=catalog_id, access_token=access_token):
            return invalid

        return fetch_list(
            f"{catalog_id}/product_sets", access_token, all_pages=all_pages, limit=limit,
            params={"fields": PRODUCT_SET_FIELDS}, error_message="Échec de la récupération des product sets.",
        )

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
