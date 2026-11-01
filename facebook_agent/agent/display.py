"""Readable summary of an operation result for the terminal (the full JSON goes to the log)."""
import re
from datetime import datetime, timezone

# Caractères que certains terminaux Windows affichent mal (espaces et tirets insécables)
TERMINAL_REPLACEMENTS = {"\u202f": " ", "\u00a0": " ", "\u2009": " ", "\u2007": " ",
                         "\u2011": "-", "\u2010": "-"}
MAX_LINES = 5
LEADS_ELSEWHERE = "(réponses dans le bloc « Réponses complètes des leads »)"
TEXT_KEYS = ("message", "story", "name", "title", "description", "text")
TIME_KEYS = ("created_time", "updated_time")
TEXT_WIDTH = 60


GRAPH_TIME = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}$")


def to_local_time(value: str) -> str:
    """Convert a Graph API date ("2026-10-20T17:00:00+0000", UTC) to the local time of the computer.

    Args:
        value: Date as returned by the Graph API.

    Returns:
        "2026-10-20 18:00 (heure locale)", or the value unchanged if it is not such a date.
    """
    if not isinstance(value, str) or not GRAPH_TIME.match(value):
        return value
    local = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone()
    return local.strftime("%Y-%m-%d %H:%M") + " (heure locale)"


def localize_times(value):
    """Copy of a JSON value where every Graph API date of a *_time key is in local time.

    Args:
        value: Result data.

    Returns:
        The copy (the original, kept in the log, is not changed).
    """
    if isinstance(value, dict):
        return {key: to_local_time(item) if key.endswith("_time") else localize_times(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [localize_times(item) for item in value]
    return value


FRENCH_MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def french_date(value, with_time: bool = True) -> str:
    """Graph API date or Unix timestamp as "24 oct. 2026, 20:59", in local time.

    Args:
        value: "2026-10-24T19:59:00+0000" (UTC) or a number of seconds.
        with_time: False gives "24 oct. 2026".

    Returns:
        The French date, or "" if the value is not a date.
    """
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        local = datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
    elif isinstance(value, str) and GRAPH_TIME.match(value):
        local = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z").astimezone()
    else:
        return ""
    day = f"{local.day} {FRENCH_MONTHS[local.month - 1]} {local.year}"
    return f"{day}, {local:%H:%M}" if with_time else day


# Date brute écrite par le modèle (« 2026-11-01 20:24 », « 2026‑11‑01 », « 2026-11-01T20:24 (heure locale) »)
RAW_DATE = re.compile(r"(?<![\d_])(\d{4})[-‐‑–](\d{2})[-‐‑–](\d{2})"
                      r"(?:[ T  ](\d{2}):(\d{2})(?::\d{2})?)?(?:\s*\(heure locale\))?(?![\d_])")


def readable_dates(text: str) -> str:
    """Replace the raw dates of an answer by French ones (« 1 nov. 2026, 20:24 »), already in local time.

    The dates given to the model are local times (to_local_time), so they are only rewritten, not converted.

    Args:
        text: Answer of the agent.

    Returns:
        The answer with readable dates; an impossible date (month 13) is left as it is.
    """
    def rewrite(match: re.Match) -> str:
        year, month, day, hour, minute = match.groups()
        if not 1 <= int(month) <= 12 or not 1 <= int(day) <= 31:
            return match.group(0)
        date = f"{int(day)} {FRENCH_MONTHS[int(month) - 1]} {year}"
        return f"{date}, {hour}:{minute}" if hour else date
    return RAW_DATE.sub(rewrite, text or "")


def for_terminal(text: str) -> str:
    """Replace the special spaces and hyphens of a text by plain ones, for the terminal.

    Args:
        text: Text to show (e.g. the answer of the LLM).

    Returns:
        The same text with plain spaces and hyphens.
    """
    for special, plain in TERMINAL_REPLACEMENTS.items():
        text = text.replace(special, plain)
    return text


def _short(text: str, width: int = TEXT_WIDTH) -> str:
    """One-line text, cut at width characters."""
    text = " ".join(str(text).split())
    return text if len(text) <= width else text[:width - 1] + "…"


def _lead_answers(field_data: list) -> str:
    """Answers of a lead, in full, as "field : value ; field : value" (shown to the user only).

    The model receives masked values and the log none (agent/lead_privacy.py); the user asked for
    the leads, so the terminal shows them as they are.

    Args:
        field_data: The field_data of a lead ([{"name": ..., "values": [...]}, ...]).

    Returns:
        One line, or "(aucune réponse)".
    """
    answers = [f"{field.get('name')} : {', '.join(str(v) for v in field.get('values') or [])}"
               for field in field_data if isinstance(field, dict)]
    return " ; ".join(answers) or "(aucune réponse)"


def lead_line(item: dict) -> str:
    """One lead with its answers in full: "date - field : value ; ... - id" (shown to the user only).

    Args:
        item: A lead of list_form_leads or list_test_leads (with its field_data).

    Returns:
        The line.
    """
    return _item_line(item)


def _item_line(item, full_leads: bool = True) -> str:
    """One item of a list: "date - text - id" (the parts that exist).

    With full_leads=False, the answers of a lead are replaced by LEADS_ELSEWHERE (web interface:
    they are in a separate folded block).
    """
    if not isinstance(item, dict):
        return _short(item)
    parts = []
    stamp = next((item[k] for k in TIME_KEYS if item.get(k)), None)
    if stamp:
        parts.append(to_local_time(str(stamp)).replace(" (heure locale)", ""))
    if isinstance(item.get("field_data"), list):  # lead : réponses complètes, pour l'écran seulement
        parts.append(_lead_answers(item["field_data"]) if full_leads else LEADS_ELSEWHERE)
    else:
        text = next((item[k] for k in TEXT_KEYS if isinstance(item.get(k), str) and item[k].strip()), None)
        if text is None and isinstance(item.get("from"), dict):
            text = item["from"].get("name")
        parts.append(_short(text) if text else "(sans texte)")
    if item.get("price"):  # « 20,00 TND (promo 12,00 TND) » quand une promotion est en cours
        promo = f" (promo {item['sale_price']})" if item.get("sale_price") else ""
        parts.append(f"{item['price']}{promo}")
    if item.get("id"):
        parts.append(str(item["id"]))
    return " - ".join(parts)


def summarize_output(output: dict | None, max_lines: int = MAX_LINES, full_leads: bool = True) -> list[str]:
    """Lines shown in the terminal for an operation result.

    Args:
        output: Standard result of the operation ({"status", "data"} or an error).
        max_lines: Maximum number of list items shown.
        full_leads: False: the answers of the leads are not in the lines (web interface).

    Returns:
        The lines: "N éléments reçus, K affichés :" and one line per item for a list,
        "key : value" lines for an object, or the message of an error.
    """
    if not output:
        return []
    if output.get("status") != "success":
        details = output.get("details") or {}
        cause = details.get("cause")
        lines = [f"    {output.get('message')}" + (f" [{cause}]" if cause else "")]
        api_error = details.get("error") if isinstance(details.get("error"), dict) else {}
        facebook = api_error.get("error_user_msg") or api_error.get("message")
        if facebook:  # message détaillé de Facebook, avec son code
            title = f"{api_error['error_user_title']} : " if api_error.get("error_user_title") else ""
            code = f" (code {api_error.get('code')}" + (f", sous-code {api_error['error_subcode']}"
                                                      if api_error.get("error_subcode") else "") + ")"
            lines.append(f"    Facebook : {title}{facebook}{code if api_error.get('code') else ''}")
        lines += [f"    - {error}" for error in details.get("errors", [])[:5] if isinstance(error, str)]
        return lines
    data = output.get("data")
    items = data if isinstance(data, list) else data.get("data") if isinstance(data, dict) else None
    if isinstance(items, list):
        more = isinstance(data, dict) and (bool((data.get("paging") or {}).get("next")) or data.get("truncated"))
        head = f"    {len(items)} élément(s) reçu(s)" + (" (d'autres pages existent)" if more else "")
        if not items:
            return [head + "."]
        shown = items[:max_lines]
        return [head + f", {len(shown)} affiché(s) :"] + [f"      {_item_line(item, full_leads)}" for item in shown]
    if isinstance(data, dict):
        return [f"    {key} : {_short(value if not isinstance(value, (dict, list)) else str(value))}"
                for key, value in list(data.items())[:max_lines]]
    return [f"    {_short(data)}"]
