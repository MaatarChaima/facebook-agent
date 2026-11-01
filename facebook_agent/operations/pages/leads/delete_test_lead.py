from facebook_agent.graph import call_graph, check_required, error, success

DELETE_ERROR = "Échec de la suppression du lead de test."
TRANSIENT_CODES = (1, 2)  # erreurs temporaires de la Graph API (« Service temporarily unavailable »…)
CONFIRMED_NOTE = "supprimé, confirmé par relecture"


def _api_error(result: dict) -> dict:
    """The Facebook error of a failed result ({} when it is not an API error)."""
    api_error = (result.get("details") or {}).get("error")
    return api_error if isinstance(api_error, dict) else {}


def _is_transient(api_error: dict) -> bool:
    """A temporary error: code 1 or 2, or flagged is_transient by Facebook."""
    return api_error.get("code") in TRANSIENT_CODES or api_error.get("is_transient") is True


def _does_not_exist(api_error: dict) -> bool:
    """The object no longer exists (code 100, subcode 33: "... does not exist ...")."""
    return api_error.get("code") == 100 and api_error.get("error_subcode") == 33


def delete_test_lead(lead_id: str, page_token: str) -> dict:
    """Delete a test lead of a Lead Ads form (Meta allows one test lead per form).

    Sends DELETE /{lead_id}. After a temporary error of Facebook (code 1 or 2, or is_transient),
    the lead is read again (GET /{lead_id}): if it no longer exists, the deletion did happen and a
    success is returned with a note; otherwise the error is returned. Meta allows only the owner of
    a lead to delete it: use it for the test leads created with create_test_lead, never for the
    leads of real people.

    Parameters:
        - Input-lead_id (str, mandatory): ID of the test lead (see list_test_leads).
          Example: "LEAD_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page that owns the form.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"success": true}; after a temporary error
            confirmed by the reading, {"success": true, "note": "supprimé, confirmé par relecture"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "success": true,
                    "note": "supprimé, confirmé par relecture"
                }
            }
        Example (success, variant "suppression directe"):
            {
                "status": "success",
                "data": {
                    "success": true
                }
            }
        Errors:
            - validation: a mandatory parameter is empty (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error), e.g. the
              lead does not belong to the caller; after a temporary error, the lead still exists
              or could not be read (the error of the deletion is returned).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(lead_id=lead_id, page_token=page_token):
            return invalid
        result = call_graph("DELETE", lead_id, page_token, error_message=DELETE_ERROR)
        if result["status"] == "success" or not _is_transient(_api_error(result)):
            return result
        # Erreur temporaire : la suppression a pu être faite quand même ; la relecture le dit
        read = call_graph("GET", lead_id, page_token, params={"fields": "id"},
                          error_message="Relecture du lead de test impossible.")
        if read["status"] == "error" and _does_not_exist(_api_error(read)):
            return success({"success": True, "note": CONFIRMED_NOTE})
        return result
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
