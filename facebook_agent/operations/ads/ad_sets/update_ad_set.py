import json

from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.operations.ads.account_guard import (
    with_meta_explanation,
    PAUSED,
    account_path,
    checked_account,
    country_errors,
    owned_object,
)


@with_meta_explanation
def update_ad_set(ad_set_id: str, ad_account_id: str, access_token: str, name: str | None = None,
                  countries: list | None = None, pause: bool = False) -> dict:
    """Rename an ad set, change its countries and/or put it on pause; it can never be made ACTIVE.

    Reads the ad account (money check, as in create_campaign), then the ad set
    (GET /{ad_set_id}?fields=account_id,name,status), which must belong to this account. Then
    sends POST /{ad_set_id} with the new name, targeting = the new countries only, and/or
    status=PAUSED. The budget cannot be changed (it stays the minimum of the account).

    Parameters:
        - Input-ad_set_id (str, mandatory): ID of the ad set (see list_ad_sets).
          Example: "AD_SET_ID_EXAMPLE"
        - Input-ad_account_id (str, mandatory): ID of its ad account, "act_<digits>" or "<digits>".
          Example: "act_AD_ACCOUNT_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (or the token of Marketing API >
          Tools) with the ads_management permission.
        - Input-name (str, optional): New name of the ad set.
          Example: "Tunisie et Maroc - adultes"
        - Input-countries (list[str], optional): New countries targeted (ISO 3166-1 alpha-2); they
          replace the whole targeting. Countries of the European Union are refused.
          Example: ["TN", "MA"]
        - Input-pause (bool, optional): True puts the ad set on pause (status PAUSED). Default: False.

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
            - validation: a mandatory parameter is empty, ad_account_id is not an ad account ID, a
              country is not a two-letter code or is in the European Union, or there is nothing to
              change (no request is sent).
            - safety: the ad account could spend money, or the ad set belongs to another account (details.problems); nothing is sent.
            - api: reading the ad account or the object failed (nothing is sent), or the
              Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(ad_set_id=ad_set_id, ad_account_id=ad_account_id, access_token=access_token):
            return invalid
        path, invalid = account_path(ad_account_id)
        if invalid:
            return invalid
        if not (name and name.strip()) and countries is None and pause is not True:
            return validation_error("Rien à modifier : donner un nouveau nom, de nouveaux pays et/ou pause=True.")
        if countries is not None and (errors := country_errors(countries)):
            return validation_error(errors)
        _, refused = checked_account(path, access_token)
        if refused:
            return refused
        _, refused = owned_object(ad_set_id, path, access_token, "name,status")
        if refused:
            return refused
        data = {}
        if name and name.strip():
            data["name"] = name.strip()
        if countries is not None:
            data["targeting"] = json.dumps({"geo_locations": {"countries": countries}})
        if pause is True:
            data["status"] = PAUSED
        return call_graph("POST", ad_set_id, access_token, data=data,
                          error_message="Échec de la modification de l'ensemble de publicités.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
