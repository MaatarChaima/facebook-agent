"""Session log of the agent (logs/agent-<date>-<time>.jsonl, ignored by git).

One JSON object per line: requests, domain choices, tool calls, shortened results,
confirmations, errors and token usage. No secret is ever written: the known secrets
(tokens, API key, App Secret) and anything that looks like a token are replaced by
"REDACTED" before writing, and so are the values of keys that name a secret.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path

from facebook_agent.agent.lead_privacy import redact_field_data
from facebook_agent.config import PROJECT_ROOT
from facebook_agent.masking import TOKEN_IN_URL  # mêmes motifs que call_graph

LOG_DIR = PROJECT_ROOT / "logs"
REDACTED = "REDACTED"
# "token" mais pas "tokens" : total_tokens est un compteur, access_token un secret
SECRET_KEY = re.compile(r"token(?!s)|secret|api_?key|password|authorization", re.IGNORECASE)
TOKEN_LIKE = re.compile(r"EAA[A-Za-z0-9]{20,}|gsk_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9_-]{16,}")

def redact(value, secrets: set[str]):
    """Copy of a JSON value without any secret.

    Args:
        value: Value to write in the log.
        secrets: Known secret strings (tokens, API key, App Secret).

    Returns:
        The copy, where secrets, token-like strings and values of secret-named keys are "REDACTED".
    """
    if isinstance(value, dict):
        return {key: REDACTED if SECRET_KEY.search(str(key)) and value[key] not in (None, "")
                else redact(value[key], secrets) for key in value}
    if isinstance(value, (list, tuple)):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, REDACTED)
        return TOKEN_LIKE.sub(REDACTED, TOKEN_IN_URL.sub(rf"\1{REDACTED}", value))
    return value


class SessionLog:
    """Append-only JSON Lines log of one agent session."""

    def __init__(self, log_dir: Path = LOG_DIR, secrets: set[str] | None = None) -> None:
        """Create the log file of a new session in log_dir."""
        self.secrets = {s for s in (secrets or set()) if s}
        log_dir.mkdir(parents=True, exist_ok=True)
        self.path = log_dir / f"agent-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        self.log_dir = log_dir

    def add_secret(self, secret: str | None) -> None:
        """Register a secret obtained during the session (e.g. a page token).

        Args:
            secret: The secret value; None or "" is ignored.
        """
        if secret:
            self.secrets.add(secret)

    def write(self, event: str, **fields) -> None:
        """Append one event, without any secret.

        Args:
            event: Event name (request, domains, tool_call, tool_result, confirmation, error, usage, answer...).
            **fields: Data of the event.
        """
        # réponses des leads jamais écrites (seuls l'ID, la date, le formulaire et les noms des champs restent)
        fields = redact_field_data(fields)
        record = redact({"time": datetime.now().isoformat(timespec="seconds"), "event": event, **fields}, self.secrets)
        with open(self.path, "a", encoding="utf-8") as log:
            log.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def tokens_used_today(log_dir: Path = LOG_DIR, today: date | None = None, model: str | None = None,
                      default_model: str | None = None) -> int:
    """Sum of the tokens recorded today in the session logs (usage events of every session).

    Args:
        log_dir: Folder of the logs.
        today: Day to count (default: today).
        model: Count only this model (each Groq model has its own daily quota); None = all.
        default_model: Model of the old usage events that do not name one.

    Returns:
        The number of tokens; requests made outside the agent are not counted.
    """
    day = (today or date.today()).isoformat()
    total = 0
    for path in log_dir.glob("agent-*.jsonl"):
        with open(path, encoding="utf-8") as log:
            for line in log:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("event") != "usage" or not str(record.get("time", "")).startswith(day):
                    continue
                if model is None or (record.get("model") or default_model) == model:
                    total += int(record.get("total_tokens") or 0)
    return total
