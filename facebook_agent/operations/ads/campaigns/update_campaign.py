from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.operations.ads.account_guard import PAUSED, account_path, checked_account, owned_object, with_meta_explanation


@with_meta_explanation
def update_campaign(campaign_id: str, ad_account_id: str, access_token: str, name: str | None = None,
                    pause: bool = False) -> dict:
    """Rename a campaign and/or put it on pause (PAUSED); a campaign can never be made ACTIVE.

    Reads the ad account (money check, as in create_campaign), then the campaign
    (GET /{campaign_id}?fields=account_id,name,status), which must belong to this account. Then
    sends POST /{campaign_id} with the new name and/or status=PAUSED.

    Parameters:
        - Input-campaign_id (str, mandatory): ID of the campaign (see list_campaigns).
          Example: "CAMPAIGN_ID_EXAMPLE"
        - Input-ad_account_id (str, mandatory): ID of its ad account, "act_<digits>" or "<digits>".
          Example: "act_AD_ACCOUNT_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (or the token of Marketing API >
          Tools) with the ads_management permission.
        - Input-name (str, optional): New name of the campaign.
          Example: "Test facebook_agent - collection hiver"
        - Input-pause (bool, optional): True puts the campaign on pause (status PAUSED). Default: False.

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
            - validation: a mandatory parameter is empty, ad_account_id is not an ad account ID, or
              there is nothing to change (no name and pause is not True) (no request is sent).
            - safety: the ad account could spend money, or the campaign belongs to another account (details.problems); nothing is sent.
            - api: reading the ad account or the object failed (nothing is sent), or the
              Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(campaign_id=campaign_id, ad_account_id=ad_account_id, access_token=access_token):
            return invalid
        path, invalid = account_path(ad_account_id)
        if invalid:
            return invalid
        if not (name and name.strip()) and pause is not True:
            return validation_error("Rien à modifier : donner un nouveau nom et/ou pause=True.")
        _, refused = checked_account(path, access_token)
        if refused:
            return refused
        _, refused = owned_object(campaign_id, path, access_token, "name,status")
        if refused:
            return refused
        data = {}
        if name and name.strip():
            data["name"] = name.strip()
        if pause is True:
            data["status"] = PAUSED
        return call_graph("POST", campaign_id, access_token, data=data, error_message="Échec de la modification de la campagne.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
