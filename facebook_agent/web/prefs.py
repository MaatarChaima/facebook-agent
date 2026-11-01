"""Last choices of the web page (dry-run or real mode, light or dark theme), kept in a small local file.

The file web_prefs.json, at the root of the project, is ignored by git. It holds two booleans and never a
token, a page or a name. A missing or unreadable file gives the defaults (real mode, light theme); a file
that cannot be written is ignored: the choice then only lasts for the session.
"""
import json
from pathlib import Path

PREFS_FILE = Path(__file__).resolve().parents[2] / "web_prefs.json"
DEFAULTS = {"dry_run": False, "dark": False}


def load(path: Path | None = None) -> dict[str, bool]:
    """Read the last choices.

    Args:
        path: File to read (default: PREFS_FILE, read at call time so the tests can move it).

    Returns:
        {"dry_run": bool, "dark": bool}; a missing, unreadable or wrong value gives its default.
    """
    try:
        data = json.loads((path or PREFS_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULTS)
    if not isinstance(data, dict):
        return dict(DEFAULTS)
    return {key: data[key] if isinstance(data.get(key), bool) else default for key, default in DEFAULTS.items()}


def save(path: Path | None = None, **changes: bool) -> None:
    """Keep one or both choices; the other one keeps its last value.

    Args:
        path: File to write (default: PREFS_FILE).
        **changes: dry_run and/or dark; any other key is ignored.
    """
    target = path or PREFS_FILE
    prefs = load(target)
    prefs.update({key: bool(value) for key, value in changes.items() if key in DEFAULTS})
    try:
        target.write_text(json.dumps(prefs) + "\n", encoding="utf-8")
    except OSError:  # dossier en lecture seule : le choix ne vaut que pour la session
        pass
