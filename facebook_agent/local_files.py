"""Shared helpers for the operations that accept a local file or a URL (not an operation itself)."""
import os
from urllib.parse import urlparse

from facebook_agent.graph import validation_error


def is_url(value: str) -> bool:
    """Tell whether a value is an http(s) URL.

    Args:
        value: Local path or URL given by the caller.

    Returns:
        True only for a value starting with "http://" or "https://" (case-insensitive).
    """
    return isinstance(value, str) and value.strip().lower().startswith(("http://", "https://"))


def extension(value: str) -> str:
    """Return the lower-case extension of a local path or of the path part of a URL.

    Args:
        value: Local path or URL; the query string and fragment of a URL are ignored.

    Returns:
        The extension with its dot (e.g. ".jpg"), or "" if there is none.
    """
    path = urlparse(value).path if is_url(value) else value
    return os.path.splitext(path)[1].lower()


def missing_file_error(path: str) -> dict | None:
    """Check that a local file exists.

    Args:
        path: Path of the local file.

    Returns:
        None if the file exists, otherwise a validation error (no request must be sent).
    """
    if os.path.isfile(path):
        return None
    return validation_error(f"Fichier introuvable : {path} (ni un fichier local existant, ni une URL http/https).",
                            message="Le fichier local spécifié est introuvable.")
