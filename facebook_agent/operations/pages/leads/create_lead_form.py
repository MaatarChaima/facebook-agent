import json
import re

from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.local_files import is_url

QUESTION_TYPES = ("FULL_NAME", "FIRST_NAME", "LAST_NAME", "EMAIL", "PHONE", "CUSTOM")
QUESTION_KEYS = {"type", "key", "label", "options"}
DEFAULT_LOCALE = "fr_FR"
LOCALE = re.compile(r"[a-z]{2}_[A-Z]{2}")
MAX_LINK_TEXT = 70  # limite de Meta pour privacy_policy.link_text
CREATE_ERROR = "Échec de la création du formulaire Lead Ads."


def _question_errors(questions) -> list[str]:
    """Validation errors of the questions of a form (empty list = valid)."""
    if not isinstance(questions, list) or not questions:
        return ["questions doit être une liste d'au moins une question."]
    errors, seen = [], set()
    for index, question in enumerate(questions, 1):
        where = f"question {index}"
        if not isinstance(question, dict):
            errors.append(f"{where} : un objet {{\"type\", \"key\", ...}} est attendu.")
            continue
        unknown = sorted(set(question) - QUESTION_KEYS)
        if unknown:
            errors.append(f"{where} : clé(s) inconnue(s) {', '.join(unknown)} (acceptées : type, key, label, options).")
        kind, key = question.get("type"), question.get("key")
        if kind not in QUESTION_TYPES:
            errors.append(f"{where} : type {kind!r} inconnu (types acceptés : {', '.join(QUESTION_TYPES)}).")
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{where} : key est obligatoire.")
        elif key in seen:
            errors.append(f"{where} : la key {key!r} est déjà utilisée par une autre question.")
        else:
            seen.add(key)
        label = question.get("label")
        if kind == "CUSTOM" and (not isinstance(label, str) or not label.strip()):
            errors.append(f"{where} : une question CUSTOM doit avoir un label (le texte de la question).")
        if kind != "CUSTOM" and "label" in question:
            errors.append(f"{where} : label n'est accepté que pour une question CUSTOM.")
        if "options" in question:
            options = question["options"]
            valid = (kind == "CUSTOM" and isinstance(options, list) and options
                     and all(isinstance(o, dict) and set(o) == {"value", "key"}
                             and all(isinstance(o[k], str) and o[k].strip() for k in o) for o in options))
            if not valid:
                errors.append(f"{where} : options doit être une liste de {{\"value\", \"key\"}} non vides, "
                              "pour une question CUSTOM seulement.")
    return errors


def create_lead_form(page_id: str, name: str, questions: list, privacy_policy_url: str, page_token: str,
                     follow_up_action_url: str, privacy_policy_link_text: str | None = None,
                     locale: str | None = None) -> dict:
    """Create a Lead Ads form (instant form) on the page.

    Sends POST /{page_id}/leadgen_forms. The form is not shown to anyone by itself: it is used by a
    lead ad, or tested with create_test_lead. Meta does not allow deleting a form: it can only be
    archived (archive_lead_form). Requires a Page access token of a person with the ADVERTISE task,
    and the Lead Ads terms accepted on the page.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page that owns the form.
          Example: "PAGE_ID_EXAMPLE"
        - Input-name (str, mandatory): Name of the form (only shown to the page's admins).
          Example: "Catalogue automne - demande de contact"
        - Input-questions (list[dict], mandatory): Questions, in the order shown; at least one. Each
          key must be unique in the form.
          Keys:
              - Key-type (str, mandatory): Type of question; the pre-filled types are filled in by Facebook.
                Choices:
                    - FULL_NAME -> full name (pre-filled)
                    - FIRST_NAME -> first name (pre-filled)
                    - LAST_NAME -> last name (pre-filled)
                    - EMAIL -> e-mail address (pre-filled)
                    - PHONE -> phone number (pre-filled)
                    - CUSTOM -> question written by the page (label mandatory)
              - Key-key (str, mandatory): Identifier of the question in the form and in the leads.
              - Key-label (str, optional): Text of a CUSTOM question; refused for the other types.
              - Key-options (list[dict], optional): Answers of a multiple-choice CUSTOM question, each
                {"value": "<text shown>", "key": "<identifier>"}.
          Example: [{"type": "FULL_NAME", "key": "nom"}, {"type": "EMAIL", "key": "email"}, {"type": "CUSTOM", "key": "taille", "label": "Votre taille ?", "options": [{"value": "M", "key": "m"}, {"value": "L", "key": "l"}]}]
        - Input-privacy_policy_url (str, mandatory): URL (http/https) of the page's privacy policy,
          linked in the form.
          Example: "https://example.com/confidentialite"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-follow_up_action_url (str, mandatory): URL (http/https) of the "Voir le site web" button
          shown after sending the form; Meta refuses a form without it (code 100, subcode 1892085,
          "Champs manquants : FollowUpActionURL").
          Example: "https://example.com"
        - Input-privacy_policy_link_text (str, optional): Text of the privacy policy link, 70 characters
          at most (Meta's limit); empty = Facebook's default text.
          Example: "Politique de confidentialité"
        - Input-locale (str, optional): Language of the pre-filled questions, as language_COUNTRY.
          Default: "fr_FR".
          Example: "fr_FR"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<id of the form>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "LEAD_FORM_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty; no question; a question without type or
              key, with an unknown type, or a key used twice; a CUSTOM question without label, or a
              label on another type; options that are not {"value", "key"}; a URL that is not
              http/https; a link text longer than 70 characters; a locale that is not
              language_COUNTRY (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error), e.g. Lead
              Ads terms not accepted on the page, or answered without id (details.response).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, name=name, questions=questions,
                                     privacy_policy_url=privacy_policy_url, page_token=page_token,
                                     follow_up_action_url=follow_up_action_url):
            return invalid
        locale = locale or DEFAULT_LOCALE
        errors = _question_errors(questions)
        if not is_url(privacy_policy_url):
            errors.append("privacy_policy_url doit être une URL http ou https.")
        if not is_url(follow_up_action_url):
            errors.append("follow_up_action_url doit être une URL http ou https.")
        if privacy_policy_link_text and len(privacy_policy_link_text) > MAX_LINK_TEXT:
            errors.append(f"privacy_policy_link_text : {MAX_LINK_TEXT} caractères au plus "
                          f"(reçu : {len(privacy_policy_link_text)}).")
        if not isinstance(locale, str) or not LOCALE.fullmatch(locale):
            errors.append(f"locale doit être de la forme langue_PAYS, par exemple fr_FR (reçu : {locale!r}).")
        if errors:
            return validation_error(errors, message="Des erreurs ont été détectées dans le formulaire Lead Ads.")

        policy = {"url": privacy_policy_url}
        if privacy_policy_link_text:
            policy["link_text"] = privacy_policy_link_text
        data = {"name": name, "questions": json.dumps(questions, ensure_ascii=False),
                "privacy_policy": json.dumps(policy, ensure_ascii=False), "locale": locale,
                "follow_up_action_url": follow_up_action_url}
        result = call_graph("POST", f"{page_id}/leadgen_forms", page_token, data=data, error_message=CREATE_ERROR)
        if result["status"] == "success" and not result["data"].get("id"):
            return error(CREATE_ERROR, {"type": "api", "response": result["data"]})
        return result
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
