"""Tokens hidden in texts: query parameters of URLs (paging.next...) and token-like strings.

The Graph API puts the access token of the request in the URLs of its answers (paging.next,
paging.previous). call_graph() masks them in every answer, so that no operation returns a token
inside a URL; the agent's log, the anonymizer and the capture script use the same patterns.
A field whose value IS a token (e.g. "access_token" of a page in authenticate) is not touched here.
"""
import re
from typing import Any

MASK = "REDACTED"
# Valeur d'un paramètre secret dans une URL (après ?, & ou #, ou en début de texte) : access_token=...
SECRET_PARAMS = r"(?:access_token|appsecret_proof|client_secret|fb_exchange_token|input_token)"
TOKEN_IN_URL = re.compile(r"((?:(?<=[?&#])|^)" + SECRET_PARAMS + r"=)[^&\s\"'#]+")
# Jetons reconnaissables n'importe où : Meta (EAA...), Groq (gsk_...), clés de type sk-...
TOKEN_LIKE = re.compile(r"EAA[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{16,}")
# Paramètre secret encore présent dans une URL (sa valeur n'est ni masquée ni un exemple)
UNMASKED_URL_TOKEN = re.compile(r"(?:(?<=[?&#])|^)" + SECRET_PARAMS
                                + r"=(?!REDACTED\b|ACCESS_TOKEN_EXAMPLE\b|APP_SECRET_EXAMPLE\b)[^&\s\"'#]+")


def mask_text(text: str) -> str:
    """Text where the secret URL parameters and the token-like strings are replaced by "REDACTED".

    Args:
        text: Any text (URL, message, JSON...).

    Returns:
        The text, masked.
    """
    return TOKEN_LIKE.sub(MASK, TOKEN_IN_URL.sub(rf"\1{MASK}", text))


def mask_urls(value: Any) -> Any:
    """Copy of a JSON value where the secret parameters of the URLs are replaced by "REDACTED".

    Only URL parameters (access_token=..., appsecret_proof=...) are masked: a field whose value is a
    token (e.g. the Page token returned by authenticate) is kept, the code needs it.

    Args:
        value: Answer of the Graph API, or any JSON value.

    Returns:
        The copy (dicts and lists are rebuilt; other values are returned as they are).
    """
    if isinstance(value, dict):
        return {key: mask_urls(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_urls(item) for item in value]
    if isinstance(value, str) and "=" in value:
        return TOKEN_IN_URL.sub(rf"\1{MASK}", value)
    return value


def mask_all(value: Any) -> Any:
    """Copy of a JSON value where every string goes through mask_text() (for display and logs).

    Args:
        value: Any JSON value.

    Returns:
        The copy, without any token in URLs nor token-like string.
    """
    if isinstance(value, dict):
        return {key: mask_all(item) for key, item in value.items()}
    if isinstance(value, list):
        return [mask_all(item) for item in value]
    return mask_text(value) if isinstance(value, str) else value


def has_unmasked_token(text: str) -> bool:
    """True if a text still holds a token: a secret URL parameter not masked, or a token-like string.

    Args:
        text: Text to check (e.g. a JSON dump).

    Returns:
        True when a token is found.
    """
    return bool(UNMASKED_URL_TOKEN.search(text) or TOKEN_LIKE.search(text))
