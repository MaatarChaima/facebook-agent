from facebook_agent.graph import check_required, error, fetch_list

LEAD_FIELDS = "id,created_time,ad_id,form_id,field_data"


def list_form_leads(form_id: str, page_token: str, all_pages: bool = False, limit: int | None = None) -> dict:
    """List the leads received by a Lead Ads form (people who sent it from an ad).

    Sends GET /{form_id}/leads with the fields id, created_time, ad_id, form_id and field_data.
    Requires the leads_retrieval permission and a Page access token of a person with the
    ADVERTISE task. The answers are personal data (name, e-mail, phone...): show them to the user,
    but keep them out of logs and never send them elsewhere.

    Parameters:
        - Input-form_id (str, mandatory): ID of the Lead Ads form.
          Example: "LEAD_FORM_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page that owns the form.
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 25

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of leads (id, created_time,
            ad_id, form_id, field_data = [{"name": "<question key>", "values": [...]}]), and
            "paging" holds the cursors (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "LEAD_ID_EXAMPLE",
                            "created_time": "2026-10-31T11:35:40+0000",
                            "form_id": "LEAD_FORM_ID_EXAMPLE",
                            "field_data": [
                                {
                                    "name": "nom",
                                    "values": [
                                        "Client Test"
                                    ]
                                }
                            ]
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
            - api: the Graph API returned an error (details.status_code, details.error), e.g. the
              leads_retrieval permission is missing.
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(form_id=form_id, page_token=page_token):
            return invalid
        return fetch_list(f"{form_id}/leads", page_token, all_pages=all_pages, limit=limit,
                          params={"fields": LEAD_FIELDS},
                          error_message="Échec de la récupération des leads du formulaire.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
