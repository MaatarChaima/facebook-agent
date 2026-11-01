def get_user_id() -> str:
    """Ask the user for the ID of a user.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID de l'utilisateur : ").strip()
