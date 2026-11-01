from facebook_agent.graph import call_graph, check_required, error


def delete_photo(photo_id: str, page_token: str) -> dict:
    """Delete a photo of the page.

    Parameters:
        - Input-photo_id (str, mandatory): ID of the photo of the page to delete.
          Example: "PHOTO_ID_EXAMPLE"
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
        if invalid := check_required(photo_id=photo_id, page_token=page_token):
            return invalid
        return call_graph("DELETE", photo_id, page_token, error_message="Échec de la suppression de la photo.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
