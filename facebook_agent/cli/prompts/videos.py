def get_video_id() -> str:
    """Ask the user for the ID of a video.

    Returns:
        The text typed by the user, as typed.
    """
    return input("ID vidéo : ")


def get_video_url() -> str:
    """Ask the user for the URL or path of a video.

    Returns:
        The text typed by the user, as typed.
    """
    return input("URL vidéo : ")


def get_video_title() -> str:
    """Ask the user for the title of a video.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Titre : ")


def get_video_description() -> str:
    """Ask the user for the description of a video.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Description : ")
