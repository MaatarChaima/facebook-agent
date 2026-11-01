from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.operations.ads.account_guard import account_path, checked_account, owned_object, with_meta_explanation


@with_meta_explanation
def delete_ad(ad_id: str, ad_account_id: str, access_token: str) -> dict:
    """Delete an ad of the ad account.

    Reads the ad account (money check, as in create_campaign), then the ad
    (GET /{ad_id}?fields=account_id,name,status), which must belong to this account. Then sends
    DELETE /{ad_id}. The post or the hidden publication used by the ad is not deleted.

    Parameters:
        - Input-ad_id (str, mandatory): ID of the ad (see list_ads).
          Example: "AD_ID_EXAMPLE"
        - Input-ad_account_id (str, mandatory): ID of its ad account, "act_<digits>" or "<digits>".
          Example: "act_AD_ACCOUNT_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (or the token of Marketing API >
          Tools) with the ads_management permission.

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
            - validation: a mandatory parameter is empty or ad_account_id is not an ad account ID (no
              request is sent).
            - safety: the ad account could spend money, or the ad belongs to another account
              (details.problems); nothing is deleted.
            - api: reading the ad account or the object failed (nothing is sent), or the
              Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(ad_id=ad_id, ad_account_id=ad_account_id, access_token=access_token):
            return invalid
        path, invalid = account_path(ad_account_id)
        if invalid:
            return invalid
        _, refused = checked_account(path, access_token)
        if refused:
            return refused
        _, refused = owned_object(ad_id, path, access_token, "name,status")
        if refused:
            return refused
        return call_graph("DELETE", ad_id, access_token, error_message="Échec de la suppression de la publicité.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
