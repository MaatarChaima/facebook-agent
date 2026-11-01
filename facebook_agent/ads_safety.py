"""Money safety of the ads domain: which ad account may be used, whatever the mode.

The rule is applied by the code, never only by the prompt: an ad account is accepted only if it
has no payment method (no funding_source) and has spent nothing (amount_spent = "0"), read live
from the API, in both modes ("sandbox" and "no_payment"). Without a valid mode, the ads domain is
disabled. Every object is created PAUSED, ACTIVE is refused everywhere and the budget is the
minimum (see the ads operations).
"""
import re

AD_ACCOUNT_MODES = ("sandbox", "no_payment")
# Champs lus avant chaque écriture et par le sondage : la règle (funding_source, amount_spent), le budget
# minimal et l'affichage. Aucun champ qui exige business_management (ex. "business"), que le token d'un
# compte sandbox (Marketing API > Outils) n'a pas.
ACCOUNT_FIELDS = ("id,name,account_status,disable_reason,funding_source,amount_spent,spend_cap,currency,"
                  "min_daily_budget,timezone_name")
# Relecture de secours, sans les champs d'affichage : ceux de la règle et du budget seulement
ESSENTIAL_ACCOUNT_FIELDS = "id,funding_source,amount_spent,min_daily_budget"
BUSINESS_FIELD_ERROR = "Requires business_management permission to access the field"
AD_ACCOUNT = re.compile(r"(?:act_)?(\d+)")


def ad_account_path(account_id: str | None) -> str | None:
    """Graph path of an ad account, from the .env value given with or without the "act_" prefix.

    Args:
        account_id: "act_123…" or "123…" (spaces around are ignored).

    Returns:
        "act_123…", or None if the value is empty or is not an ad account ID.
    """
    match = AD_ACCOUNT.fullmatch((account_id or "").strip())
    return f"act_{match.group(1)}" if match else None


def spending_problems(account: dict) -> list[str]:
    """Reasons why an ad account could spend money (empty list = the account is accepted).

    Args:
        account: Fields of the ad account read from the API (funding_source, amount_spent...).

    Returns:
        The problems, in French: a payment method is present, or something was already spent
        (an unreadable amount_spent is a problem too).
    """
    problems = []
    if account.get("funding_source"):
        problems.append("moyen de paiement présent")
    if str(account.get("amount_spent", "")).strip() != "0":
        problems.append(f"amount_spent = {account.get('amount_spent')!r}")
    return problems


def mode_problem(mode: str | None) -> str | None:
    """Why the ads domain is disabled by its mode, or None when the mode is valid.

    Args:
        mode: Value of AD_ACCOUNT_MODE.

    Returns:
        A sentence in French, or None for "sandbox" or "no_payment".
    """
    if not mode:
        return "AD_ACCOUNT_MODE est vide : domaine Campagnes désactivé"
    if mode not in AD_ACCOUNT_MODES:
        return f"AD_ACCOUNT_MODE = {mode!r} inconnu (sandbox ou no_payment attendu) : domaine Campagnes désactivé"
    return None
