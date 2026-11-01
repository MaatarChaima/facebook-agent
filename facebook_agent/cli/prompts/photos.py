def get_photo_id() -> str:
    """Ask the user for the ID of a photo.

    Returns:
        The text typed by the user, as typed.
    """
    return input("ID photo : ")


def get_photo_url() -> str:
    """Ask the user for the URL or path of an image.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("URL image : ").strip()


def get_photo_caption() -> str:
    """Ask the user for the caption of a photo.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Légende : ")


def get_album_id() -> str:
    """Ask the user for the ID of an album.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID de l'album : ").strip()


def get_photo_file_path() -> str:
    """Ask the user for the local path of a photo.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("Chemin local de la photo : ").strip()
