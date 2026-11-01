from facebook_agent.graph import call_graph, check_required, error


def delete_product_set(product_set_id: str, access_token: str) -> dict:
    """Delete a product set.

    Parameters:
        - Input-product_set_id (str, mandatory): ID of the product set to delete.
          Example: "PRODUCT_SET_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.

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
        if invalid := check_required(product_set_id=product_set_id, access_token=access_token):
            return invalid

        return call_graph(
            "DELETE",
            product_set_id,
            access_token,
            error_message="Échec de la suppression du product set.",
        )

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
