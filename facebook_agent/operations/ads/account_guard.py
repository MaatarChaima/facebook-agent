"""Money safety shared by the ads operations (not an operation itself).

Before every write, the ad account is read live and refused if it could spend money (rule of
facebook_agent/ads_safety.py: a payment method, or something already spent). An object to change
must belong to this account. Every object is created or set PAUSED: no operation can send ACTIVE.
"""
import functools
import re
from typing import Callable

from facebook_agent.ads_safety import (
    ACCOUNT_FIELDS,
    BUSINESS_FIELD_ERROR,
    ESSENTIAL_ACCOUNT_FIELDS,
    ad_account_path,
    spending_problems,
)
from facebook_agent.graph import call_graph, error, validation_error

PAUSED = "PAUSED"  # seul statut envoyé par les opérations de campagnes (jamais ACTIVE)
SAFETY_MESSAGE = "Refusé par la sécurité argent : rien n'a été envoyé à Facebook."
# Objectif de la campagne -> objectif d'optimisation de ses ensembles de publicités
OPTIMIZATION_GOALS = {"OUTCOME_AWARENESS": "REACH", "OUTCOME_TRAFFIC": "LINK_CLICKS",
                      "OUTCOME_ENGAGEMENT": "POST_ENGAGEMENT", "OUTCOME_LEADS": "LEAD_GENERATION"}
COUNTRY = re.compile(r"[A-Z]{2}")
# Union européenne : Meta y exige les champs DSA (bénéficiaire, payeur), non gérés ici
EU_COUNTRIES = frozenset({"AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU", "IE",
                          "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"})
DEFAULT_COUNTRIES = ["TN"]


META_DETAIL_KEYS = ("error_user_title", "error_user_msg", "fbtrace_id")
ADS_GET_RETRIES = 2  # nouveaux essais d'une lecture (GET) quand Meta limite les appels du compte (code 17...)
NO_PAYMENT_AD = ("Meta ne permet pas de créer une publicité sur un compte sans moyen de paiement : utilise un "
                 "compte sandbox (AD_ACCOUNT_MODE=sandbox). Les campagnes et les ensembles restent possibles.")
PAGE_NOT_VISIBLE = ("le token du compte publicitaire (access_token) doit aussi avoir accès à la page : utilise un "
                    "utilisateur système de l'entreprise, avec la page et le compte publicitaire, dans "
                    "ADS_ACCESS_TOKEN.")
# Sous-codes déjà rencontrés pendant les captures : explication ajoutée au message
KNOWN_SUBCODES = {
    1359188: NO_PAYMENT_AD,
    1815520: "Une campagne OUTCOME_TRAFFIC exige un post avec un lien vers un site (hors de Facebook).",
    2446289: PAGE_NOT_VISIBLE,
    1341012: PAGE_NOT_VISIBLE,
    1487888: ("ensemble OUTCOME_ENGAGEMENT créé sans destination_type=ON_POST : Meta le traite comme une campagne "
              "de conversions ; recrée l'ensemble avec create_ad_set, qui envoie maintenant ON_POST."),
    2859024: ("un(e) admin de l'entreprise doit accepter une fois la politique de non-discrimination de Meta "
              "(Paramètres de l'entreprise > Utilisateur(ice)s système) ; rien à changer dans le code."),
}


def ads_mode() -> str | None:
    """AD_ACCOUNT_MODE of the .env, read at each call ("sandbox", "no_payment" or empty).

    Returns:
        The mode, or None when it is not set.
    """
    from facebook_agent import config  # lu à l'appel : les tests et la capture peuvent le changer
    return config.AD_ACCOUNT_MODE


def meta_explanation(api_error) -> str:
    """Meta's own explanation of a Graph API error: user title, user message and fbtrace_id.

    Args:
        api_error: The "error" object of the Graph API answer (details.error).

    Returns:
        "Meta : <title> : <message> (fbtrace_id <id>)", or "" when the error has none of them.
    """
    if not isinstance(api_error, dict):
        return ""
    title, text, trace = (str(api_error.get(key) or "").strip() for key in META_DETAIL_KEYS)
    explanation = " : ".join(part for part in (title, text) if part)
    if trace:
        explanation += f" (fbtrace_id {trace})" if explanation else f"fbtrace_id {trace}"
    return f"Meta : {explanation}" if explanation else ""


def with_meta_explanation(func: Callable[..., dict]) -> Callable[..., dict]:
    """Decorator of the ads operations: an API error message always ends with Meta's explanation.

    The error codes of the Marketing API are often too broad (e.g. code 100); error_user_title and
    error_user_msg say what was refused. They are added to the message (details.error keeps the
    raw error); a request token never appears in them.

    Args:
        func: An ads operation (returns a standard result).

    Returns:
        The same operation, whose error message ends with meta_explanation() when Meta gives one, then
        with the project's explanation of a known subcode (KNOWN_SUBCODES).
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> dict:
        result = func(*args, **kwargs)
        if isinstance(result, dict) and result.get("status") == "error":
            api_error = (result.get("details") or {}).get("error")
            message = result.get("message", "")
            explanation = meta_explanation(api_error)
            if explanation and explanation not in message:
                message = f"{message} {explanation}".strip()
            known = KNOWN_SUBCODES.get(api_error.get("error_subcode")) if isinstance(api_error, dict) else None
            if known and known not in message:
                message = f"{message} Explication : {known}"
            result = {**result, "message": message}
        return result
    return wrapper


def safety_error(problems: list[str]) -> dict:
    """Error result of a write refused by the money safety (type "safety").

    Args:
        problems: Reasons, in French.

    Returns:
        {"status": "error", "message": ..., "details": {"type": "safety", "problems": [...]}}.
    """
    return error(SAFETY_MESSAGE, {"type": "safety", "problems": problems})


def account_path(ad_account_id: str | None) -> tuple[str | None, dict | None]:
    """Graph path of the ad account given by the caller.

    Args:
        ad_account_id: "act_123…" or "123…".

    Returns:
        ("act_123…", None), or (None, validation error) when it is not an ad account ID.
    """
    path = ad_account_path(ad_account_id)
    if path is None:
        return None, validation_error(f"ad_account_id n'est pas un ID de compte publicitaire (act_123… ou 123…) : "
                                      f"{ad_account_id!r}.")
    return path, None


def needs_business_management(result: dict) -> bool:
    """True if a reading failed only because a field requires the business_management permission.

    Args:
        result: Result of call_graph.

    Returns:
        True for Meta's "(#100) Requires business_management permission to access the field".
    """
    api_error = (result.get("details") or {}).get("error") if result.get("status") == "error" else None
    return isinstance(api_error, dict) and BUSINESS_FIELD_ERROR in str(api_error.get("message", ""))


def read_account(path: str, access_token: str, fields: str = ACCOUNT_FIELDS) -> tuple[dict, bool]:
    """Read the ad account; without business_management, read it again with the essential fields only.

    The essential fields (ESSENTIAL_ACCOUNT_FIELDS) are those of the money rule (funding_source,
    amount_spent) and of the budget (min_daily_budget). If they cannot be read either, the result is
    the error, and the account stays refused.

    Args:
        path: "act_123…".
        access_token: Token with ads_read / ads_management.
        fields: Fields asked first (default ACCOUNT_FIELDS).

    Returns:
        (result of call_graph, True when the essential fields only were read).
    """
    def read(asked: str) -> dict:
        return call_graph("GET", path, access_token, params={"fields": asked},
                          error_message="Lecture du compte publicitaire impossible : rien n'a été envoyé.",
                          throttle_retries=ADS_GET_RETRIES)

    result = read(fields)
    if needs_business_management(result) and fields != ESSENTIAL_ACCOUNT_FIELDS:
        return read(ESSENTIAL_ACCOUNT_FIELDS), True
    return result, False


def checked_account(path: str, access_token: str) -> tuple[dict | None, dict | None]:
    """Read the ad account live and apply the money rule.

    Args:
        path: "act_123…".
        access_token: Token with ads_read / ads_management.

    Returns:
        (fields of the account, None), (None, safety error) when it could spend money, or (None, the
        error of the reading: api, timeout, network...) when it could not be read, even with the
        essential fields only (read_account); nothing is sent.
    """
    read, _ = read_account(path, access_token)
    if read["status"] != "success":
        return None, read
    if problems := spending_problems(read["data"]):
        return None, safety_error([f"le compte {path} peut dépenser de l'argent : " + ", ".join(problems)])
    return read["data"], None


def owned_object(object_id: str, path: str, access_token: str, fields: str) -> tuple[dict | None, dict | None]:
    """Read a campaign, ad set or ad, and check that it belongs to the ad account.

    Args:
        object_id: ID of the object.
        path: "act_123…" of the checked account.
        access_token: Token with ads_read / ads_management.
        fields: Fields to read, besides account_id.

    Returns:
        (fields of the object, None), (None, safety error) when it belongs to another account, or
        (None, the error of the reading) when it could not be read; nothing is sent.
    """
    read = call_graph("GET", object_id, access_token, params={"fields": f"account_id,{fields}"},
                      error_message="Lecture de l'objet publicitaire impossible : rien n'a été envoyé.",
                      throttle_retries=ADS_GET_RETRIES)
    if read["status"] != "success":
        return None, read
    owner = ad_account_path(str(read["data"].get("account_id", "")))
    if owner != path:
        return None, safety_error([f"{object_id} appartient à un autre compte publicitaire ({owner}), pas à {path}"])
    return read["data"], None


def country_errors(countries) -> list[str]:
    """Validation errors of the targeted countries (empty list = valid).

    Args:
        countries: List of ISO 3166-1 alpha-2 codes.

    Returns:
        The problems, in French: not a list of two capital letters, or a country of the European Union.
    """
    if not isinstance(countries, list) or not countries:
        return ["countries doit être une liste d'au moins un code pays ISO à deux lettres (ex. [\"TN\"])."]
    errors = [f"pays {c!r} : code ISO à deux lettres majuscules attendu (ex. TN)." for c in countries
              if not isinstance(c, str) or not COUNTRY.fullmatch(c)]
    eu = sorted(c for c in countries if c in EU_COUNTRIES)
    if eu:
        errors.append(f"pays de l'Union européenne refusés ({', '.join(eu)}) : Meta y exige les champs DSA "
                      "(bénéficiaire, payeur), non gérés par ce projet.")
    return errors
