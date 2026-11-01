from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.operations.ads.account_guard import OPTIMIZATION_GOALS, PAUSED, account_path, checked_account, with_meta_explanation

CREATE_ERROR = "Échec de la création de la campagne."


@with_meta_explanation
def create_campaign(ad_account_id: str, name: str, objective: str, access_token: str) -> dict:
    """Create an advertising campaign, always PAUSED, on an ad account that cannot spend money.

    The ad account is read first (GET /act_{id}?fields=id,name,account_status,disable_reason,
    funding_source,amount_spent,spend_cap,currency,min_daily_budget,timezone_name; without the
    business_management permission, again with id,funding_source,amount_spent,min_daily_budget
    only): it is refused if it has a payment method (funding_source), has already spent something
    (amount_spent is not "0"), or if these fields cannot be read. Then sends
    POST /act_{id}/campaigns with status=PAUSED, special_ad_categories=[] and
    is_adset_budget_sharing_enabled=false. The campaign has no budget: the budget is set on its ad
    sets (create_ad_set), at the minimum of the account. No function of this project can make a
    campaign ACTIVE.

    Parameters:
        - Input-ad_account_id (str, mandatory): ID of the ad account, "act_<digits>" or "<digits>".
          Example: "act_AD_ACCOUNT_ID_EXAMPLE"
        - Input-name (str, mandatory): Name of the campaign (shown in the Ads Manager).
          Example: "Test facebook_agent - collection automne"
        - Input-objective (str, mandatory): Objective of the campaign; it sets the optimization goal
          of its ad sets.
          Choices:
              - OUTCOME_AWARENESS -> reach as many people as possible (ad sets optimized for REACH)
              - OUTCOME_TRAFFIC -> clicks to a link (LINK_CLICKS); the post of the ad must contain a link to a website
              - OUTCOME_ENGAGEMENT -> engagement with a post (POST_ENGAGEMENT)
              - OUTCOME_LEADS -> Lead Ads forms (LEAD_GENERATION, page needed on the ad set)
        - Input-access_token (str, mandatory): User access token (or the token of Marketing API >
          Tools) with the ads_management permission.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<id of the campaign>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "CAMPAIGN_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, ad_account_id is not an ad account ID, or
              objective is not one of the choices (no request is sent).
            - safety: the ad account has a payment method or has already spent money
              (details.problems); no campaign is sent.
            - api: reading the ad account or the object failed (nothing is sent), or the Graph API
              returned an error (details.status_code, details.error), or answered without id
              (details.response).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(ad_account_id=ad_account_id, name=name, objective=objective,
                                     access_token=access_token):
            return invalid
        path, invalid = account_path(ad_account_id)
        if invalid:
            return invalid
        if objective not in OPTIMIZATION_GOALS:
            return validation_error(f"objective {objective!r} inconnu (choix : {', '.join(OPTIMIZATION_GOALS)}).")
        _, refused = checked_account(path, access_token)
        if refused:
            return refused
        data = {"name": name, "objective": objective, "status": PAUSED, "special_ad_categories": "[]",
                "is_adset_budget_sharing_enabled": "false"}
        result = call_graph("POST", f"{path}/campaigns", access_token, data=data, error_message=CREATE_ERROR)
        if result["status"] == "success" and not result["data"].get("id"):
            return error(CREATE_ERROR, {"type": "api", "response": result["data"]})
        return result
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
