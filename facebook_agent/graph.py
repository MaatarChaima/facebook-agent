"""Common wrapper around the Facebook Graph API.

Every operation calls the API through ``call_graph()`` and returns one of
the two standard result formats:

    {"status": "success", "data": <API response>}
    {"status": "error", "message": "<message in French>", "details": {...}}
"""
import json
import time
from typing import Any

import requests

from facebook_agent.config import BASE_URL, DEFAULT_TIMEOUT
from facebook_agent.masking import mask_urls


def success(data: Any) -> dict:
    """Build a standard success result.

    Args:
        data: Data of the result (usually the raw Graph API answer).

    Returns:
        {"status": "success", "data": data}.
    """
    return {"status": "success", "data": data}


def error(message: str, details: dict | None = None) -> dict:
    """Build a standard error result.

    Args:
        message: Message in French, shown to the user.
        details: Details of the error, e.g. {"type": "api", ...}; None gives {}.

    Returns:
        {"status": "error", "message": message, "details": details}.
    """
    return {"status": "error", "message": message, "details": details or {}}


def validation_error(errors: list[str] | str, message: str | None = None) -> dict:
    """Build a standard error result for invalid input parameters.

    Args:
        errors: One message or a list of messages (in French).
        message: Main message; default "Certains paramètres sont manquants ou invalides.".

    Returns:
        An error result whose details are {"type": "validation", "errors": [...]}.
    """
    if isinstance(errors, str):
        errors = [errors]
    return error(
        message or "Certains paramètres sont manquants ou invalides.",
        {"type": "validation", "errors": errors},
    )


def check_required(**params: Any) -> dict | None:
    """Return a validation error listing the empty mandatory parameters, or None.

    A parameter is empty when it is None, a blank string, or an empty list / dict / tuple.
    Call it at the top of each operation, before any request.

    Args:
        **params: Mandatory parameters, by name.

    Returns:
        None if every parameter is set, otherwise a validation error with one message per
        empty parameter.
    """
    missing = [
        name for name, value in params.items()
        if value is None
        or (isinstance(value, str) and not value.strip())
        or (isinstance(value, (list, dict, tuple)) and not value)
    ]
    if missing:
        return validation_error([f"Le paramètre {name} est obligatoire." for name in missing])
    return None


NETWORK_RETRY_DELAY = 3  # secondes avant le nouvel essai d'une lecture (GET) après une erreur réseau


def network_cause(exc: BaseException) -> str:
    """Readable cause of a network error (delay, DNS, SSL, refused or cut connection), without any secret.

    Args:
        exc: The exception raised by requests or by the LLM client.

    Returns:
        The cause in French, followed by the exception name, e.g. "DNS : nom de serveur introuvable (ConnectionError)".
    """
    chain, current = [], exc
    while current is not None and len(chain) < 6:  # l'exception et ses causes
        chain.append(current)
        current = current.__cause__ or current.__context__
    names = " ".join(type(e).__name__ for e in chain).lower()
    text = " ".join(str(e) for e in chain).lower()
    if "timeout" in names or "timed out" in text:
        cause = "délai dépassé"
    elif any(word in text for word in ("getaddrinfo", "name or service", "nodename", "name resolution", "11001")):
        cause = "DNS : nom de serveur introuvable"
    elif "ssl" in names or "ssl" in text or "certificate" in text:
        cause = "erreur SSL (certificat ou connexion sécurisée)"
    elif "refused" in text or "10061" in text:
        cause = "connexion refusée"
    elif any(word in text for word in ("reset", "aborted", "10054", "remote end closed", "disconnected")):
        cause = "connexion coupée par le serveur"
    else:
        cause = "connexion impossible"
    return f"{cause} ({type(exc).__name__})"


def call_graph(
    method: str,
    path: str,
    access_token: str | None,
    *,
    params: dict | None = None,
    data: dict | None = None,
    json_body: dict | None = None,
    files: dict | None = None,
    error_message: str = "Erreur renvoyée par l'API Facebook.",
    timeout: float = DEFAULT_TIMEOUT,
    throttle_retries: int = 0,
) -> dict:
    """Send a request to the Graph API and return a standard result.

    The access token is always sent through ``params`` (query parameters), never
    concatenated into the URL string.

    Args:
        method: HTTP method ("GET", "POST", "DELETE").
        path: Graph API path, without the version (e.g. "PAGE_ID/feed").
        access_token: Token sent in the query parameters; None sends no token (used by
            the OAuth token exchange, which authenticates with the app).
        params: Extra query parameters.
        data: Form fields of the request body.
        json_body: JSON body of the request.
        files: Files of a multipart upload.
        error_message: Message (in French) of the error result if the API returns an error.
        timeout: Timeout in seconds; use UPLOAD_TIMEOUT (config) for file uploads.
        throttle_retries: New tries of a GET refused because too many calls were made (codes of
            THROTTLE_CODES), after the wait given by Meta's usage headers (throttle_wait); 0 = none
            (default). A write is never sent again.

    Returns:
        {"status": "success", "data": <JSON answer>} (secret URL parameters such as the
        access_token of paging.next replaced by "REDACTED", see masking.mask_urls), or an error result whose
        details["type"] is "api", "timeout", "network" or "invalid_response".
        A GET is sent again once, NETWORK_RETRY_DELAY seconds after a network error or a
        timeout; a POST or a DELETE never is (it may have reached Facebook).
    """
    url = f"{BASE_URL}/{path.lstrip('/')}"
    query = dict(params or {})
    if access_token is not None:
        query["access_token"] = access_token

    # Une lecture (GET) est réessayée une fois après une erreur réseau ; une écriture jamais
    # (elle a pu être reçue par Facebook avant la coupure).
    attempts = 2 if method.upper() == "GET" else 1
    for attempt in range(1, attempts + 1):
        try:
            response = requests.request(
                method, url, params=query, data=data, json=json_body, files=files, timeout=timeout
            )
            break
        except requests.RequestException as exc:
            if attempt < attempts:
                time.sleep(NETWORK_RETRY_DELAY)
                continue
            tried = " (après 2 essais)" if attempts == 2 else ""
            if isinstance(exc, requests.Timeout):
                return error(f"L'API Facebook n'a pas répondu à temps{tried}.",
                             {"type": "timeout", "timeout_seconds": timeout, "cause": network_cause(exc)})
            return error(f"Impossible de contacter l'API Facebook{tried} : {network_cause(exc)}.",
                         {"type": "network", "info": str(exc), "cause": network_cause(exc)})

    try:
        body = response.json()
    except ValueError:
        return error(
            "Réponse invalide de l'API Facebook.",
            {"type": "invalid_response", "status_code": response.status_code, "info": response.text[:500]},
        )

    if isinstance(body, dict) and "error" in body:
        details = {"type": "api", "status_code": response.status_code, "error": body["error"]}
        if is_throttled(body["error"]):
            wait = throttle_wait(getattr(response, "headers", None) or {}, attempt=throttle_retries)
            if method.upper() == "GET" and throttle_retries > 0 and wait is not None:
                time.sleep(wait)
                return call_graph(method, path, access_token, params=params, data=data, json_body=json_body,
                                  files=files, error_message=error_message, timeout=timeout,
                                  throttle_retries=throttle_retries - 1)
            retry_after = throttle_wait(getattr(response, "headers", None) or {}, attempt=0, cap=None)
            if retry_after is not None:
                details["retry_after_seconds"] = retry_after
        return error(error_message, details)
    return success(mask_urls(body))  # paging.next / previous : l'URL contient le token de la requête


# Codes Graph API de limitation du nombre d'appels (app, utilisateur, compte publicitaire)
THROTTLE_CODES = frozenset({4, 17, 32, 613}) | frozenset(range(80000, 80100))
THROTTLE_DEFAULT_WAITS = {2: 10, 1: 30}  # essais restants -> attente (s) quand Meta n'en indique pas
THROTTLE_MAX_WAIT = 120  # au-delà, pas de nouvel essai : l'erreur indique retry_after_seconds


def is_throttled(api_error: Any) -> bool:
    """True if a Graph API error says that too many calls were made (code in THROTTLE_CODES).

    Args:
        api_error: The "error" object of the answer.

    Returns:
        True for a rate-limit error.
    """
    return isinstance(api_error, dict) and api_error.get("code") in THROTTLE_CODES


def throttle_wait(headers: Any, attempt: int, cap: int | None = THROTTLE_MAX_WAIT) -> int | None:
    """Seconds to wait before a new try, from Meta's usage headers, or a default wait.

    Reads x-business-use-case-usage (estimated_time_to_regain_access, in minutes) and
    x-ad-account-usage (reset_time_duration, in seconds).

    Args:
        headers: Headers of the answer (case-insensitive mapping, or {}).
        attempt: Tries left; gives the default wait when Meta gives none (THROTTLE_DEFAULT_WAITS).
        cap: Longest wait accepted (None = no limit).

    Returns:
        The wait in seconds, or None when it is longer than cap (or unknown and no default applies).
    """
    waits = []
    try:
        usage = json.loads(headers.get("x-business-use-case-usage") or "{}")
        for entries in usage.values() if isinstance(usage, dict) else []:
            for entry in entries if isinstance(entries, list) else []:
                minutes = entry.get("estimated_time_to_regain_access") if isinstance(entry, dict) else None
                if isinstance(minutes, (int, float)) and minutes > 0:
                    waits.append(int(minutes * 60))
        account = json.loads(headers.get("x-ad-account-usage") or "{}")
        seconds = account.get("reset_time_duration") if isinstance(account, dict) else None
        if isinstance(seconds, (int, float)) and seconds > 0:
            waits.append(int(seconds))
    except (ValueError, TypeError, AttributeError):
        waits = []
    wait = max(waits) if waits else THROTTLE_DEFAULT_WAITS.get(attempt)
    if wait is None or (cap is not None and wait > cap):
        return None
    return wait


MAX_PAGES = 50  # limite de sécurité de la pagination
MAX_LIMIT = 100  # éléments par page acceptés par le paramètre limit des fonctions de liste


def collect_pages(
    path: str,
    access_token: str,
    *,
    params: dict | None = None,
    error_message: str = "Erreur renvoyée par l'API Facebook.",
    max_pages: int = MAX_PAGES,
    throttle_retries: int = 0,
) -> dict:
    """GET every page of a Graph API list and return all items in one result.

    Follows the cursor-based pagination: the ``after`` cursor of each page is sent
    through ``params`` (never the ``paging.next`` URL, which contains the token), and
    the pagination stops when ``paging.next`` is absent, as documented by Meta.

    Args:
        path: Graph API path of the list (e.g. "PAGE_ID/photos").
        access_token: Token sent in the query parameters.
        params: Extra query parameters (e.g. fields).
        error_message: Message of the error result if a page fails.
        max_pages: Safety limit on the number of pages read.
        throttle_retries: See call_graph (new tries of each page after a rate-limit error).

    Returns:
        {"status": "success", "data": {"data": [...]}} with the items of all pages, plus
        "truncated": true if max_pages was reached (or a next link without cursor was met);
        or the error result of the first page that failed.
    """
    items: list = []
    query = dict(params or {})
    for _ in range(max_pages):
        page = call_graph("GET", path, access_token, params=query, error_message=error_message,
                          throttle_retries=throttle_retries)
        if page["status"] == "error":
            return page
        body = page["data"] if isinstance(page["data"], dict) else {}
        items.extend(body.get("data", []))
        paging = body.get("paging") or {}
        if not paging.get("next"):
            return success({"data": items})
        after = (paging.get("cursors") or {}).get("after")
        if not after:
            return success({"data": items, "truncated": True})
        query = {**query, "after": after}
    return success({"data": items, "truncated": True})


def fetch_list(
    path: str,
    access_token: str,
    *,
    all_pages: bool = False,
    params: dict | None = None,
    error_message: str = "Erreur renvoyée par l'API Facebook.",
    limit: int | None = None,
    throttle_retries: int = 0,
) -> dict:
    """GET a Graph API list: the first page as returned by the API, or all pages merged.

    Args:
        path: Graph API path of the list.
        access_token: Token sent in the query parameters.
        all_pages: False returns the raw first page ({"data": [...], "paging": {...}});
            True returns {"data": [...all items...]} (see collect_pages).
        params: Extra query parameters (e.g. fields).
        error_message: Message of the error result.
        limit: Items per page (Graph API "limit" parameter), from 1 to MAX_LIMIT; None = API default.
        throttle_retries: See call_graph.

    Returns:
        A standard result (see call_graph and collect_pages), or a validation error if limit is
        invalid (no request is sent).
    """
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_LIMIT:
            return validation_error(f"limit doit être un entier de 1 à {MAX_LIMIT} (reçu : {limit!r}).")
        params = {**(params or {}), "limit": limit}
    if all_pages:
        return collect_pages(path, access_token, params=params, error_message=error_message,
                             throttle_retries=throttle_retries)
    return call_graph("GET", path, access_token, params=params, error_message=error_message,
                      throttle_retries=throttle_retries)
