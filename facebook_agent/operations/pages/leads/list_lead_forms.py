from facebook_agent.graph import check_required, error, fetch_list

FORM_FIELDS = "id,name,status,locale,leads_count,created_time"


def list_lead_forms(page_id: str, page_token: str, all_pages: bool = False, limit: int | None = None) -> dict:
    """List the Lead Ads forms (instant forms) of the page, archived ones included.

    Sends GET /{page_id}/leadgen_forms with the fields id, name, status, locale, leads_count and
    created_time. Requires a Page access token of a person with the ADVERTISE task.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 10

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of forms (id, name, status
            ACTIVE or ARCHIVED, locale, leads_count, created_time), and "paging" holds the cursors
            (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "LEAD_FORM_ID_EXAMPLE_EXISTING_1",
                            "name": "Example name",
                            "status": "ARCHIVED",
                            "locale": "fr_FR",
                            "leads_count": 0,
                            "created_time": "2026-10-25T17:46:23+0000"
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
        if invalid := check_required(page_id=page_id, page_token=page_token):
            return invalid
        return fetch_list(f"{page_id}/leadgen_forms", page_token, all_pages=all_pages, limit=limit,
                          params={"fields": FORM_FIELDS},
                          error_message="Échec de la récupération des formulaires Lead Ads.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
