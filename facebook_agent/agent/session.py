"""Start of an agent session: long-lived user token, page and page token, kept in memory only.

The tokens are never written to a file, never shown and never sent to the LLM. With FB_APP_ID
and FB_APP_SECRET, the user token of the .env is first exchanged for a long-lived one (about
60 days), then the pages are read with it (their page tokens do not expire). Without them, the
token of the .env is used as is (often valid for 1 to 2 hours only).

Meta's documentation does not say whether an already long-lived token can be exchanged again: if
the exchange fails for another reason than the token itself (code 190), the token of the .env is
used as is, with a message. Every failure shows the Facebook message, code and subcode (never a
token); an expired token (code 190, subcode 463) gets a clear advice.
"""
from dataclasses import dataclass, field
from typing import Callable

from facebook_agent import config
from facebook_agent.agent.executor import Context
from facebook_agent.auth.authentication import _exchange_long_lived_token, authenticate
from facebook_agent.masking import MASK, mask_text

INVALID_TOKEN_CODE = 190  # OAuthException : token invalide, expiré ou révoqué
EXPIRED_SUBCODE = 463
EXPIRED_TOKEN = ("Ton token a expiré : génère un nouveau token, de préférence un token prolongé (60 jours) avec le "
                 "débogueur de tokens.")
EXCHANGE_CHECK = "Vérifie FB_USER_TOKEN, FB_APP_ID et FB_APP_SECRET."
TOKEN_USED_AS_IS = ("Échange contre un token longue durée refusé ({detail}) : le token du .env est utilisé tel "
                    "quel (s'il est déjà prolongé, il reste valable environ 60 jours).")


def facebook_error(result: dict, secrets: set[str] = frozenset()) -> str:
    """Short French description of a failed Graph API call: Facebook message, code and subcode, never a token.

    Args:
        result: Error result of call_graph ({"status": "error", "message", "details"}).
        secrets: Values to hide even if Facebook quotes them (tokens, app secret).

    Returns:
        "Facebook : <message> (code 190, sous-code 463)", or the cause of a network error, or "".
    """
    details = result.get("details") or {}
    api = details.get("error") if isinstance(details.get("error"), dict) else None
    if api is None:
        cause = details.get("cause") or details.get("type")
        return f"cause : {cause}" if cause else ""
    message = str(api.get("error_user_msg") or api.get("message") or "").strip()
    for secret in secrets:
        if secret:
            message = message.replace(secret, MASK)
    codes = [f"code {api['code']}"] if api.get("code") is not None else []
    if api.get("error_subcode") is not None:
        codes.append(f"sous-code {api['error_subcode']}")
    return f"Facebook : {mask_text(message)}" + (f" ({', '.join(codes)})" if codes else "")


def _error_code(result: dict) -> tuple[int | None, int | None]:
    """(code, subcode) of the Facebook error of a result, or (None, None)."""
    api = (result.get("details") or {}).get("error")
    if not isinstance(api, dict):
        return None, None
    return api.get("code"), api.get("error_subcode")


def failure_message(prefix: str, result: dict, advice: str = "", secrets: set[str] = frozenset()) -> str:
    """Message of a SessionError: the expired token said clearly, otherwise the prefix, the detail and the advice.

    Args:
        prefix: What failed (e.g. "Échec de l'échange contre un token longue durée.").
        result: Error result of call_graph.
        advice: What to check, added at the end.
        secrets: Values to hide.

    Returns:
        The message, in French.
    """
    detail = facebook_error(result, secrets)
    if _error_code(result) == (INVALID_TOKEN_CODE, EXPIRED_SUBCODE):
        return f"{EXPIRED_TOKEN} ({detail})"
    return " ".join(part for part in (prefix, f"{detail}." if detail else "", advice) if part)


class SessionError(Exception):
    """The session cannot start (missing setting, Facebook error); the message is in French."""


@dataclass
class Session:
    """What the agent needs to act on the page, and the secrets to hide from the log."""

    context: Context
    page_name: str
    long_lived: bool
    secrets: set[str] = field(default_factory=set)

    def close(self) -> None:
        """Forget the tokens (end of the session)."""
        self.context.page_token = None
        self.context.access_token = None
        self.secrets.clear()


def _choose_page(pages: list[dict], ask: Callable[[list[dict]], dict] | None) -> dict:
    """Page of FB_PAGE_ID, the only page, or the page chosen by the user."""
    if config.FB_PAGE_ID:
        page = next((p for p in pages if str(p.get("id")) == str(config.FB_PAGE_ID)), None)
        if page is None:
            raise SessionError("FB_PAGE_ID ne correspond à aucune page de ce compte.")
        return page
    if len(pages) == 1 or ask is None:
        return pages[0]
    return ask(pages)


def open_session(ask_page: Callable[[list[dict]], dict] | None = None,
                 notify: Callable[[str], None] = print) -> Session:
    """Get the tokens of the session from the .env (2 or 3 Graph API requests).

    Args:
        ask_page: Function that lets the user choose among several pages (if FB_PAGE_ID is empty).
        notify: Function that shows a message to the user.

    Returns:
        The session (context injected in the operations, page name, secrets).

    Raises:
        SessionError: FB_USER_TOKEN is empty, the token exchange or the page reading failed.
    """
    user_token = config.FB_USER_TOKEN
    if not user_token:
        raise SessionError("FB_USER_TOKEN est vide dans le .env.")
    secrets = {user_token, config.FB_APP_SECRET or ""}
    long_lived = bool(config.FB_APP_ID and config.FB_APP_SECRET)
    if long_lived:
        token, failure = _exchange_long_lived_token(user_token, config.FB_APP_ID, config.FB_APP_SECRET)
        if failure and _error_code(failure)[0] == INVALID_TOKEN_CODE:  # token expiré ou invalide : rien à essayer
            raise SessionError(failure_message(failure["message"], failure, EXCHANGE_CHECK, secrets))
        if failure:
            # La doc Meta ne garantit pas l'échange d'un token déjà prolongé : il est alors utilisé tel quel
            notify(TOKEN_USED_AS_IS.format(detail=facebook_error(failure, secrets) or failure["message"]))
            long_lived = False
        else:
            user_token = token
            secrets.add(token)
    else:
        notify("FB_APP_ID / FB_APP_SECRET vides : le token du .env est utilisé tel quel "
               "(souvent valable 1 à 2 heures seulement).")
    pages = authenticate(user_token, "1")
    if pages["status"] == "error":
        raise SessionError(failure_message(pages["message"], pages, secrets=secrets))
    accounts = pages["data"].get("data", [])
    if not accounts:
        raise SessionError("Aucune page gérée par ce compte (permission pages_show_list ?).")
    secrets |= {p.get("access_token") for p in accounts if p.get("access_token")}
    page = _choose_page(accounts, ask_page)
    if config.ADS_ACCESS_TOKEN:
        secrets.add(config.ADS_ACCESS_TOKEN)
    context = Context(page_id=str(page["id"]), page_token=page["access_token"], access_token=user_token,
                      catalog_id=config.CATALOG_ID, ad_account_id=config.AD_ACCOUNT_ID,
                      ads_access_token=config.ADS_ACCESS_TOKEN)
    return Session(context, page.get("name", ""), long_lived, {s for s in secrets if s})
