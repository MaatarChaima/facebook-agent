import json

from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.operations.ads.account_guard import (
    with_meta_explanation,
    DEFAULT_COUNTRIES,
    OPTIMIZATION_GOALS,
    PAUSED,
    account_path,
    checked_account,
    country_errors,
    owned_object,
    safety_error,
)

CREATE_ERROR = "Échec de la création de l'ensemble de publicités."


@with_meta_explanation
def create_ad_set(ad_account_id: str, campaign_id: str, name: str, access_token: str,
                  countries: list | None = None, page_id: str | None = None) -> dict:
    """Create an ad set, always PAUSED and at the minimum daily budget, in a campaign of the account.

    Reads the ad account (same check as create_campaign; its min_daily_budget is kept), then the
    campaign (GET /{campaign_id}?fields=account_id,objective,status), which must belong to this
    account. Then sends POST /act_{id}/adsets with status=PAUSED, daily_budget = min_daily_budget of
    the account (in its currency, smallest unit: 100 = 1.00 USD), billing_event=IMPRESSIONS,
    bid_strategy=LOWEST_COST_WITHOUT_CAP, targeting = the countries only, and the optimization goal
    of the campaign objective (OUTCOME_AWARENESS: REACH, OUTCOME_TRAFFIC: LINK_CLICKS,
    OUTCOME_ENGAGEMENT: POST_ENGAGEMENT with destination_type=ON_POST, to boost a post of the page;
    OUTCOME_LEADS: LEAD_GENERATION with promoted_object = the page and destination_type=ON_AD, as in
    Meta's Lead Ads guide). Without ON_POST, Meta handles an engagement ad set as a conversions one
    and refuses its ads without a tracking pixel (subcode 1487888). The budget and the status
    cannot be chosen.

    Parameters:
        - Input-ad_account_id (str, mandatory): ID of the ad account, "act_<digits>" or "<digits>".
          Example: "act_AD_ACCOUNT_ID_EXAMPLE"
        - Input-campaign_id (str, mandatory): ID of a campaign of this account (see list_campaigns).
          Example: "CAMPAIGN_ID_EXAMPLE"
        - Input-name (str, mandatory): Name of the ad set.
          Example: "Tunisie - adultes"
        - Input-access_token (str, mandatory): User access token (or the token of Marketing API >
          Tools) with the ads_management permission.
        - Input-countries (list[str], optional): Countries targeted, as ISO 3166-1 alpha-2 codes
          (two capital letters). Default: ["TN"]. Countries of the European Union are refused (Meta
          then requires DSA beneficiary and payer fields, not handled here).
          Example: ["TN"]
        - Input-page_id (str, optional): ID of the page of the Lead Ads forms; mandatory when the
          campaign objective is OUTCOME_LEADS, ignored otherwise.
          Example: "PAGE_ID_EXAMPLE"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<id of the ad set>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "AD_SET_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, ad_account_id is not an ad account ID, or a
              country is not a two-letter code or is in the European Union (no request is sent);
              page_id is missing for an OUTCOME_LEADS campaign, or the campaign objective is not
              one of the four handled (found after reading the campaign; no ad set is sent).
            - safety: the ad account has a payment method or has already spent money, or has no
              min_daily_budget; the campaign belongs to another account
              (details.problems); no ad set is sent.
            - api: reading the ad account or the object failed (nothing is sent), or the Graph API
              returned an error (details.status_code, details.error), or answered without id
              (details.response).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(ad_account_id=ad_account_id, campaign_id=campaign_id, name=name,
                                     access_token=access_token):
            return invalid
        path, invalid = account_path(ad_account_id)
        if invalid:
            return invalid
        countries = DEFAULT_COUNTRIES if countries is None else countries
        if errors := country_errors(countries):
            return validation_error(errors)
        account, refused = checked_account(path, access_token)
        if refused:
            return refused
        budget = account.get("min_daily_budget")
        if not budget:
            return safety_error([f"le compte {path} n'indique pas de min_daily_budget : budget minimal inconnu"])
        campaign, refused = owned_object(campaign_id, path, access_token, "objective,status")
        if refused:
            return refused
        goal = OPTIMIZATION_GOALS.get(campaign.get("objective"))
        if goal is None:
            return validation_error(f"objectif de la campagne {campaign.get('objective')!r} non géré "
                                    f"(gérés : {', '.join(OPTIMIZATION_GOALS)}).")
        data = {"name": name, "campaign_id": campaign_id, "daily_budget": str(budget), "billing_event": "IMPRESSIONS",
                "optimization_goal": goal, "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
                "targeting": json.dumps({"geo_locations": {"countries": countries}}), "status": PAUSED}
        if goal == "LEAD_GENERATION":
            if not page_id:
                return validation_error("page_id est obligatoire pour une campagne OUTCOME_LEADS (page des formulaires).")
            data["promoted_object"] = json.dumps({"page_id": page_id})
            data["destination_type"] = "ON_AD"
        elif goal == "POST_ENGAGEMENT":  # booster un post : interactions sur le post lui-même
            data["destination_type"] = "ON_POST"
        result = call_graph("POST", f"{path}/adsets", access_token, data=data, error_message=CREATE_ERROR)
        if result["status"] == "success" and not result["data"].get("id"):
            return error(CREATE_ERROR, {"type": "api", "response": result["data"]})
        return result
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
