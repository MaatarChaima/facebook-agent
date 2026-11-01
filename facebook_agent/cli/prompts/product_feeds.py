def get_feed_id() -> str:
    """Ask the user for the ID of a product feed.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID du feed existant : ").strip()


def get_feed_name() -> str:
    """Ask the user for the name of a new product feed.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Nom du flux : ")


def get_feed_url() -> str:
    """Ask the user for the URL or path of a feed file.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Lien du fichier : ")


def get_new_feed_url() -> str:
    """Ask the user for the URL or path of the new feed file.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Nouveau lien du fichier CSV : ")
