def get_auth_choice() -> str:
    """Ask which token type to use. The token and app credentials come from the .env file.

    Returns:
        "1" (short-lived token) or "2" (long-lived token), as typed by the user.
    """
    return input(
        "Tape 1 pour token court terme (dure environ 1 heure) "
        "ou 2 pour token long terme (durée prolongée, moins sécurisé) : "
    ).strip()
