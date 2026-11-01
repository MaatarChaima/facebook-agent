from datetime import datetime, timedelta

from facebook_agent.cli.prompts import InvalidInputError


def get_post_id() -> str:
    """Ask the user for the ID of a post.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID du post : ").strip()


def get_post_message() -> str:
    """Ask the user for the text of a post.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Message : ")


def get_new_message() -> str:
    """Ask the user for the new text of a post.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Nouveau message : ")


def get_message() -> str:
    """Ask the user for the text of a scheduled post.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Message de la publication : ")


def get_file_paths_or_urls() -> list[str]:
    """Ask one or more files (local paths or URLs), separated by commas.

    Returns:
        The list of non-empty paths or URLs, without surrounding spaces.
    """
    value = input("Chemins des fichiers (locaux ou URL, séparés par des virgules) : ")
    return [item.strip() for item in value.split(",") if item.strip()]


PUBLISH_AT_FORMAT = "%Y-%m-%d %H:%M"
MIN_DELAY = timedelta(minutes=10)


def parse_publish_at(text: str, now: datetime | None = None) -> int:
    """Convert "AAAA-MM-JJ HH:MM" (local time) to a Unix timestamp.

    Args:
        text: Date typed by the user.
        now: Current time (for the tests); default datetime.now().

    Returns:
        The Unix timestamp in seconds.

    Raises:
        InvalidInputError: The date is empty, badly formatted, or less than 10 minutes in
            the future.
    """
    text = text.strip()
    if not text:
        raise InvalidInputError(["La date de publication est obligatoire pour un post programmé."])
    try:
        publish_at = datetime.strptime(text, PUBLISH_AT_FORMAT)
    except ValueError:
        raise InvalidInputError([f"Format de date invalide : « {text} ». Format attendu : AAAA-MM-JJ HH:MM "
                                 "(exemple : 2026-12-31 14:30)."]) from None
    now = now or datetime.now()
    if publish_at < now + MIN_DELAY:
        raise InvalidInputError(["La date de publication doit être au moins 10 minutes après l'heure actuelle "
                                 f"(au plus tôt : {(now + MIN_DELAY).strftime(PUBLISH_AT_FORMAT)})."])
    return int(publish_at.timestamp())  # heure locale -> timestamp Unix


def get_publish_at() -> int:
    """Ask the scheduled publication date (local time).

    Returns:
        The Unix timestamp in seconds (see parse_publish_at).

    Raises:
        InvalidInputError: The date is invalid.
    """
    print("Format attendu : AAAA-MM-JJ HH:MM (heure locale), au moins 10 minutes dans le futur.")
    return parse_publish_at(input("Date de publication : "))
