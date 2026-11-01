"""Prompts of the "Campagnes" section of the menu (values are checked by the operations)."""
from facebook_agent.cli.prompts import InvalidInputError

OBJECTIVES = ("OUTCOME_ENGAGEMENT", "OUTCOME_TRAFFIC", "OUTCOME_AWARENESS", "OUTCOME_LEADS")
CALLS_TO_ACTION = ("SIGN_UP", "LEARN_MORE", "SUBSCRIBE", "GET_QUOTE", "APPLY_NOW")


def get_object_id(label: str) -> str:
    """Ask the ID of a campaign, an ad set or an ad.

    Args:
        label: What is asked, e.g. "de la campagne".

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input(f"ID {label} : ").strip()


def get_name(label: str) -> str:
    """Ask the name of a new campaign, ad set or ad.

    Args:
        label: What is named, e.g. "de la campagne".

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input(f"Nom {label} : ").strip()


def get_new_name() -> str | None:
    """Ask an optional new name.

    Returns:
        The new name, or None when it is empty (the name is not changed).
    """
    return input("Nouveau nom (vide = inchangé) : ").strip() or None


def get_pause() -> bool:
    """Ask whether the object is put on pause.

    Returns:
        True when the user types "o".
    """
    return input("Mettre en pause (PAUSED) ? (o/n) : ").strip().lower() == "o"


def get_objective() -> str:
    """Ask the objective of a new campaign, among OBJECTIVES (number or name).

    Returns:
        The objective, e.g. "OUTCOME_ENGAGEMENT".

    Raises:
        InvalidInputError: The answer is neither a number of the list nor an objective.
    """
    print("Objectifs : " + ", ".join(f"{i}. {objective}" for i, objective in enumerate(OBJECTIVES, 1))
          + " (ENGAGEMENT = booster un post)")
    answer = input("Objectif (numéro ou nom) : ").strip().upper()
    if answer.isdigit() and 1 <= int(answer) <= len(OBJECTIVES):
        return OBJECTIVES[int(answer) - 1]
    if answer in OBJECTIVES:
        return answer
    raise InvalidInputError([f"Objectif inconnu : {answer!r}."])


def get_countries() -> list[str] | None:
    """Ask the targeted countries, as two-letter codes separated by commas.

    Returns:
        The codes in capital letters, or None when it is empty (the default of the operation, ["TN"]).
    """
    codes = [code.strip().upper() for code in input("Pays (codes séparés par des virgules, vide = TN) : ").split(",")]
    return [code for code in codes if code] or None


def get_ad_creative() -> dict:
    """Ask what the ad shows: an existing post, or a Lead Ads form (with text, image and button).

    Returns:
        The arguments of create_ad for the creative: {"post_id"} or {"lead_form_id", "message",
        "image_url", "call_to_action"}.
    """
    post_id = input("ID du post existant à mettre en publicité (vide = publicité Lead Ads) : ").strip()
    if post_id:
        return {"post_id": post_id}
    button = input(f"Bouton ({', '.join(CALLS_TO_ACTION)} ; vide = SIGN_UP) : ").strip().upper() or "SIGN_UP"
    return {"lead_form_id": input("ID du formulaire Lead Ads : ").strip(),
            "message": input("Texte de la publicité : ").strip(),
            "image_url": input("URL de l'image (http/https, vide = aucune) : ").strip() or None,
            "call_to_action": button}
