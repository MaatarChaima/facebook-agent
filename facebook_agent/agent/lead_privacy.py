"""Personal data of the Lead Ads leads: masked for the model, never written in the log.

The user sees the leads in full on the screen (she asked for them). The model only receives:
- e-mail: c***@g***.com; phone: +216 ** *** *34 (country code and last two digits);
- name: initials; address, postal code, date of birth: [masqué];
- answers to choices (short values) are kept; free answers are shortened, with any e-mail or phone
  inside masked. The whole result is already marked untrusted by the executor.
The log keeps only the lead ID, its date, the form and the field names (see redact_field_data).
"""
import json
import re
from typing import Any

MASKED = "[masqué]"
LEAD_TOOLS = ("list_form_leads", "list_test_leads")  # résultats qui contiennent des field_data
FREE_TEXT_MAX = 30  # au-delà, une réponse est libre : raccourcie

EMAIL = re.compile(r"([\w.+-])[\w.+-]*@([\w-])[\w-]*((?:\.[\w-]+)*\.[A-Za-z]{2,})")
PHONE = re.compile(r"\+?\d[\d .-]{6,}\d")
NAME_KEYS = re.compile(r"(?:full_?name|first_?name|last_?name|^name$|^nom|pr[ée]nom)", re.I)
HIDDEN_KEYS = re.compile(r"(?:address|adresse|street|rue|city|ville|zip|post_?code|postal|code_postal|birth|"
                         r"naissance|dob)", re.I)


def mask_email(text: str) -> str:
    """E-mail addresses of a text as c***@g***.com (first letters and last domain extension kept).

    Args:
        text: Any text.

    Returns:
        The text with its e-mail addresses masked.
    """
    def masked(match: re.Match) -> str:
        extension = match.group(3).rsplit(".", 1)[1]
        return f"{match.group(1)}***@{match.group(2)}***.{extension}"
    return EMAIL.sub(masked, text)


def mask_phone_number(number: str) -> str:
    """One phone number as +216 ** *** *34: country code (after +) and last two digits kept.

    Args:
        number: The phone number, with its spaces, dots or dashes.

    Returns:
        The number with the other digits replaced by "*".
    """
    digits = [i for i, char in enumerate(number) if char.isdigit()]
    keep = set(digits[-2:])
    if number.startswith("+"):
        keep |= set(digits[:3])
    return "".join(char if not char.isdigit() or i in keep else "*" for i, char in enumerate(number))


def mask_text(text: str) -> str:
    """Free text: e-mails and phone numbers masked, then shortened to FREE_TEXT_MAX characters.

    Args:
        text: A free answer of a lead.

    Returns:
        The masked and shortened text ("…" at the end when it was cut).
    """
    text = PHONE.sub(lambda m: mask_phone_number(m.group(0)), mask_email(text))
    return text if len(text) <= FREE_TEXT_MAX else text[:FREE_TEXT_MAX] + "…"


def initials(name: str) -> str:
    """A name as its initials (« Client Test » -> « C. T. »).

    A name that is not made of ordinary words gives [masqué]: text between < > (the fictitious test
    lead of Meta gave the unreadable « <. L. D. D. F. N. »), or a word that does not start with a letter.

    Args:
        name: A first name, last name or full name.

    Returns:
        The initials, or [masqué].
    """
    words = name.split()
    if not words or "<" in name or ">" in name or any(not word[0].isalpha() for word in words):
        return MASKED
    return " ".join(f"{word[0].upper()}." for word in words)


def mask_value(key: str, value: Any) -> Any:
    """One answer of a lead, as the model may see it.

    Args:
        key: Name of the field (key of the question).
        value: The answer.

    Returns:
        The masked answer.
    """
    if not isinstance(value, str):
        return value
    if HIDDEN_KEYS.search(key):
        return MASKED
    if NAME_KEYS.search(key):
        return initials(value)
    if EMAIL.search(value) or PHONE.fullmatch(value.strip()):
        return mask_text(value)
    return value if len(value) <= FREE_TEXT_MAX and not PHONE.search(value) else mask_text(value)


def mask_leads(value: Any) -> Any:
    """Copy of a result where every field_data answer is masked for the model (field names kept).

    Args:
        value: Result of list_form_leads or list_test_leads (any JSON value).

    Returns:
        The copy; the IDs, dates and field names are unchanged.
    """
    if isinstance(value, dict):
        copy = {}
        for key, item in value.items():
            if key == "field_data" and isinstance(item, list):
                copy[key] = [{**field, "values": [mask_value(str(field.get("name", "")), v)
                                                  for v in field.get("values") or []]}
                             if isinstance(field, dict) else field for field in item]
            else:
                copy[key] = mask_leads(item)
        return copy
    if isinstance(value, list):
        return [mask_leads(item) for item in value]
    return value


def redact_field_data(value: Any) -> Any:
    """Copy for the log: every field_data answer replaced by [masqué] (the field names stay).

    Also applied inside strings that hold JSON (the raw arguments of a call, the content sent to
    the model) and to the "field_data : ..." line of a confirmation text, so that no answer of a
    lead is ever written in the log.

    Args:
        value: Fields of a log event (any JSON value).

    Returns:
        The copy, with the same number of answers, each one [masqué].
    """
    if isinstance(value, dict):
        return {key: ([{**field, "values": [MASKED] * len(field.get("values") or [])} if isinstance(field, dict)
                       else MASKED for field in item] if key == "field_data" and isinstance(item, list)
                      else redact_field_data(item))
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact_field_data(item) for item in value]
    if isinstance(value, str) and '"field_data"' in value:
        try:
            return json.dumps(redact_field_data(json.loads(value)), ensure_ascii=False)
        except ValueError:
            return re.sub(r'("field_data"\s*:\s*)\[.*?\](?=\s*[,}])', rf'\1["{MASKED}"]', value, flags=re.S)
    if isinstance(value, str) and "field_data" in value:  # texte de confirmation : « field_data : [...] »
        return re.sub(r"(field_data\s*:\s*).*", rf"\1{MASKED}", value)
    return value
