from facebook_agent.graph import check_required, error, fetch_list
from facebook_agent.operations.ads.account_guard import ADS_GET_RETRIES, account_path, with_meta_explanation

AD_FIELDS = "id,name,adset_id,campaign_id,status,effective_status,creative,created_time"


@with_meta_explanation
def list_ads(ad_account_id: str, access_token: str, ad_set_id: str | None = None, all_pages: bool = False,
             limit: int | None = None) -> dict:
    """List the ads of an ad account, or of one of its ad sets.

    Sends GET /act_{id}/ads, or GET /{ad_set_id}/ads when ad_set_id is given, with the fields id,
    name, adset_id, campaign_id, status, effective_status, creative and created_time. Reading needs
    no money check (nothing is changed).

    Parameters:
        - Input-ad_account_id (str, mandatory): ID of the ad account, "act_<digits>" or "<digits>".
          Example: "act_AD_ACCOUNT_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (or the token of Marketing API > Tools)
          with the ads_read permission.
        - Input-ad_set_id (str, optional): Only the ads of this ad set. Default: every ad of the account.
          Example: "AD_SET_ID_EXAMPLE"
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 10

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of ads (id, name, adset_id,
            campaign_id, status, effective_status, creative {id}, created_time), and "paging" holds
            the cursors (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "AD_ID_EXAMPLE",
                            "name": "Test facebook_agent 20261031-1232 - post de test (renommée)",
                            "adset_id": "AD_SET_ID_EXAMPLE",
                            "campaign_id": "CAMPAIGN_ID_EXAMPLE",
                            "status": "PAUSED",
                            "effective_status": "IN_PROCESS",
                            "creative": {
                                "id": "CREATIVE_ID_EXAMPLE"
                            },
                            "created_time": "2026-10-31T12:36:34+0100"
                        }
                    ],
                    "paging": {
                        "cursors": {
                            "before": "CURSOR_BEFORE_EXAMPLE",
                            "after": "CURSOR_AFTER_EXAMPLE"
                        }
                    }
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, ad_account_id is not an ad account ID, or
              limit is not an integer from 1 to 100 (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(ad_account_id=ad_account_id, access_token=access_token):
            return invalid
        path, invalid = account_path(ad_account_id)
        if invalid:
            return invalid
        source = f"{ad_set_id}/ads" if ad_set_id else f"{path}/ads"
        return fetch_list(source, access_token, all_pages=all_pages, limit=limit, params={"fields": AD_FIELDS},
                          error_message="Échec de la récupération des publicités.",
                          throttle_retries=ADS_GET_RETRIES)
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
