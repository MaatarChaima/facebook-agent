from facebook_agent.graph import call_graph, check_required, error


def archive_lead_form(form_id: str, page_token: str) -> dict:
    """Archive a Lead Ads form: it can no longer be used by a new ad (Meta does not allow deleting a form).

    Sends POST /{form_id} with status=ARCHIVED. The leads already received stay readable. Requires
    a Page access token of a person with the ADVERTISE task.

    Parameters:
        - Input-form_id (str, mandatory): ID of the Lead Ads form.
          Example: "LEAD_FORM_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page that owns the form.

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
        if invalid := check_required(form_id=form_id, page_token=page_token):
            return invalid
        return call_graph("POST", form_id, page_token, data={"status": "ARCHIVED"},
                          error_message="Échec de l'archivage du formulaire Lead Ads.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
