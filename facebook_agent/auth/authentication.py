from facebook_agent.graph import call_graph, check_required, error, validation_error

AUTH_ERROR = "Échec de l'authentification."
EXCHANGE_ERROR = "Échec de l'échange contre un token longue durée."


def _exchange_long_lived_token(user_access_token: str, app_id: str, app_secret: str) -> tuple[str | None, dict | None]:
    """Exchange a user token for a long-lived one: (token, None) or (None, error result)."""
    exchange = call_graph(
        "GET", "oauth/access_token", None,
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": user_access_token,
        },
        error_message=EXCHANGE_ERROR,
    )
    if exchange["status"] == "error":
        return None, exchange
    long_lived_token = exchange["data"].get("access_token")
    if not long_lived_token:
        return None, error(EXCHANGE_ERROR, {"type": "api", "response": exchange["data"]})
    return long_lived_token, None


def authenticate(
    user_access_token: str,
    choice: str,
    app_id: str | None = None,
    app_secret: str | None = None,
) -> dict:
    """Read the Facebook pages managed by the user, with their Page access tokens.

    Choice "1" sends GET me/accounts with the given token. Choice "2" first sends
    GET oauth/access_token (grant_type=fb_exchange_token, with the app ID and secret),
    then GET me/accounts with the long-lived token: the Page tokens returned are
    long-lived too.

    Parameters:
        - Input-user_access_token (str, mandatory): User access token (e.g. from the Graph API Explorer) with the page permissions
          (pages_show_list and the permissions of the operations to use).
          Example: "ACCESS_TOKEN_EXAMPLE"
        - Input-choice (str, mandatory): How the user token is used.
          Choices:
              - "1" -> use the token as given (short-lived token)
              - "2" -> exchange it first for a long-lived user token; needs app_id and app_secret
        - Input-app_id (str, optional): App ID of the Facebook app (FB_APP_ID). Needed for choice "2" only.
          Example: "APP_ID_EXAMPLE"
        - Input-app_secret (str, optional): App Secret of the Facebook app (FB_APP_SECRET). Needed for choice "2" only.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw answer of GET me/accounts: "data" is the list of pages (id, name,
            access_token = Page access token, category, category_list, tasks), plus "paging".
            Both choices return this structure (both are captured; the example shows choice "1").
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "access_token": "ACCESS_TOKEN_EXAMPLE",
                            "category": "Vêtements (Marque)",
                            "category_list": [
                                {
                                    "id": "2209",
                                    "name": "Example name"
                                }
                            ],
                            "name": "Example Page",
                            "id": "PAGE_ID_EXAMPLE",
                            "tasks": [
                                "MANAGE"
                            ]
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
            - validation: user_access_token or choice is empty, choice is neither "1" nor "2", or
              app_id / app_secret is missing for choice "2" (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error), or the
              token exchange answered without access_token (details.response).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(user_access_token=user_access_token, choice=choice):
            return invalid

        if choice == "1":
            # Récupérer les pages avec le token court terme
            return call_graph("GET", "me/accounts", user_access_token, error_message=AUTH_ERROR)

        if choice == "2":
            if not app_id or not app_secret:
                return validation_error(
                    "app_id ou app_secret manquant (FB_APP_ID / FB_APP_SECRET dans le .env)",
                    message="App ID et App Secret sont requis pour l'échange en token long terme.",
                )

            # 1. Échanger le token court terme contre un token utilisateur longue durée
            long_lived_token, failure = _exchange_long_lived_token(user_access_token, app_id, app_secret)
            if failure:
                return failure

            # 2. Récupérer les pages avec ce token (les tokens de page obtenus sont aussi longue durée)
            return call_graph("GET", "me/accounts", long_lived_token, error_message=AUTH_ERROR)

        return validation_error(f"choice={choice}", message="Choix invalide. Tape 1 ou 2.")

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
