from facebook_agent.graph import call_graph, check_required, error


def unban_user(page_id: str, user_id: str, page_token: str) -> dict:
    """Lift the ban of a user from the page.

    Sends DELETE /{page_id}/blocked with uid. Meta documents uid as deprecated ("Deprecated.
    Same as user", Graph API reference of /{page_id}/blocked); the code still sends uid. The example is built from
    the documented return type (source "documented"): a capture needs a second account.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-user_id (str, mandatory): ID of the banned user.
          Example: "USER_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

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
        if invalid := check_required(page_id=page_id, user_id=user_id, page_token=page_token):
            return invalid
        return call_graph(
            "DELETE", f"{page_id}/blocked", page_token,
            params={"uid": user_id},
            error_message="Échec du débannissement de l'utilisateur.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
