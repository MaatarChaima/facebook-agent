import re

from facebook_agent.cli.prompts import InvalidInputError


def get_lead_form_id() -> str:
    """Ask the user for the ID of a Lead Ads form.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID du formulaire Lead Ads : ").strip()


def get_lead_id() -> str:
    """Ask the user for the ID of a test lead.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID du lead de test : ").strip()


def get_lead_form_name() -> str:
    """Ask the user for the name of a new Lead Ads form.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("Nom du formulaire (visible des administrateurs de la page) : ").strip()


def _option_key(value: str, index: int) -> str:
    """Identifier of an answer of a multiple-choice question, from its text ("Taille M" -> "taille_m")."""
    return re.sub(r"\W+", "_", value.lower()).strip("_") or f"choix_{index}"


def get_lead_questions() -> list[dict]:
    """Ask the questions of a new Lead Ads form, one by one, until an empty type.

    Returns:
        The questions, e.g. [{"type": "EMAIL", "key": "email"}, {"type": "CUSTOM", "key": "taille",
        "label": "Votre taille ?", "options": [{"value": "M", "key": "m"}]}]; checked by create_lead_form.

    Raises:
        InvalidInputError: No question was typed.
    """
    print("Questions du formulaire, dans l'ordre (types : FULL_NAME, FIRST_NAME, LAST_NAME, EMAIL, PHONE, CUSTOM).")
    questions = []
    while True:
        kind = input("Type de la question (vide = fin) : ").strip().upper()
        if not kind:
            break
        question = {"type": kind, "key": input("  Clé de la question (ex. email) : ").strip()}
        if kind == "CUSTOM":
            question["label"] = input("  Texte de la question : ").strip()
            choices = [value.strip() for value in input("  Choix séparés par des virgules "
                                                        "(vide = réponse libre) : ").split(",") if value.strip()]
            if choices:
                question["options"] = [{"value": value, "key": _option_key(value, index)}
                                       for index, value in enumerate(choices, 1)]
        questions.append(question)
    if not questions:
        raise InvalidInputError(["Au moins une question est nécessaire."])
    return questions


def get_privacy_policy_url() -> str:
    """Ask the user for the URL of the privacy policy linked in the form.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("URL de la politique de confidentialité (http/https) : ").strip()


def get_optional_text(prompt: str) -> str | None:
    """Ask an optional value (link text, follow-up URL, locale).

    Args:
        prompt: Question shown to the user.

    Returns:
        The text typed, or None when it is empty (the default of the operation is used).
    """
    return input(prompt).strip() or None


def get_test_lead_answers() -> list[dict] | None:
    """Ask the answers of a test lead, as "key=value" lines, until an empty line.

    Returns:
        [{"name": key, "values": [value]}, ...], or None when no answer is typed (Facebook then
        generates the answers).

    Raises:
        InvalidInputError: A line is not of the form key=value.
    """
    print("Réponses du lead de test, une par ligne au format clé=valeur (vide = fin ; aucune = réponses "
          "générées par Facebook). N'écris jamais les données d'une vraie personne.")
    answers, errors = [], []
    while True:
        line = input("Réponse : ").strip()
        if not line:
            break
        key, separator, value = line.partition("=")
        if not separator or not key.strip() or not value.strip():
            errors.append(f"« {line} » n'est pas de la forme clé=valeur.")
            continue
        answers.append({"name": key.strip(), "values": [value.strip()]})
    if errors:
        raise InvalidInputError(errors)
    return answers or None


def confirm_lead_action(text: str) -> bool:
    """Show a Lead Ads write and ask for its confirmation.

    Args:
        text: Description of the action and its consequence.

    Returns:
        True only if the user types "o".
    """
    print(text)
    return input("Confirmer ? (o/n) : ").strip().lower() == "o"
