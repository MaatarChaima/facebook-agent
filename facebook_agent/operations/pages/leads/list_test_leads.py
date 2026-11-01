from facebook_agent.graph import check_required, error, fetch_list

LEAD_FIELDS = "id,created_time,field_data"


def list_test_leads(form_id: str, page_token: str, all_pages: bool = False, limit: int | None = None) -> dict:
    """List the test leads of a Lead Ads form (created with create_test_lead).

    Sends GET /{form_id}/test_leads with the fields id, created_time and field_data. The answers of
    a test lead are personal-looking data: show them to the user, but keep them out of logs.

    Parameters:
        - Input-form_id (str, mandatory): ID of the Lead Ads form.
          Example: "LEAD_FORM_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page that owns the form.
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 5

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of test leads (id,
            created_time, field_data = [{"name": "<question key>", "values": [...]}]), and "paging"
            holds the cursors (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "LEAD_ID_EXAMPLE",
                            "created_time": "2026-10-31T11:35:40+0000",
                            "field_data": [
                                {
                                    "name": "nom",
                                    "values": [
                                        "Client Test"
                                    ]
                                }
                            ]
                        }
                    ]
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
        if invalid := check_required(form_id=form_id, page_token=page_token):
            return invalid
        return fetch_list(f"{form_id}/test_leads", page_token, all_pages=all_pages, limit=limit,
                          params={"fields": LEAD_FIELDS},
                          error_message="Échec de la récupération des leads de test.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
