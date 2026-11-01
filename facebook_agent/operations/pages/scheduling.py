"""Shared helper for scheduled publications (not an operation itself).

Windows documented by Meta for scheduled_publish_time:
- posts (POST /{page-id}/feed): between 10 minutes and 75 days after the request;
- videos (POST /{page-id}/videos): between 10 minutes and 6 months after the request.
"""
import time

from facebook_agent.graph import validation_error

MIN_DELAY = 10 * 60                 # 10 minutes
POST_MAX_DELAY = 75 * 24 * 3600     # 75 jours
VIDEO_MAX_DELAY = 180 * 24 * 3600   # 6 mois (180 jours, borne prudente)


def check_publish_window(publish_at: int, max_delay: int, max_label: str) -> dict | None:
    """Return a validation error if publish_at is not a Unix timestamp inside the allowed window.

    Args:
        publish_at: Unix timestamp (seconds) of the scheduled publication.
        max_delay: Maximum delay in seconds after now.
        max_label: Human-readable maximum delay used in the message (e.g. "75 jours").

    Returns:
        None if the date is valid, otherwise a standard validation error.
    """
    if isinstance(publish_at, bool) or not isinstance(publish_at, int):
        return validation_error("publish_at doit être un timestamp Unix (nombre entier de secondes).")
    now = int(time.time())
    if publish_at < now + MIN_DELAY:
        return validation_error("La date de publication doit être au moins 10 minutes après l'heure actuelle.")
    if publish_at > now + max_delay:
        return validation_error(f"La date de publication doit être au plus {max_label} après l'heure actuelle.")
    return None
