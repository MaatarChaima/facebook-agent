def select_page(auth_result: dict) -> tuple[str, str] | dict:
    """Let the user choose a page from the result of ``authenticate()``.

    Args:
        auth_result: Result of authenticate.

    Returns:
        (page_id, page_token), or a standard error result (the error of authenticate,
        an invalid choice, or an unexpected error).
    """
    if auth_result.get("status") == "error":
        return auth_result

    try:
        pages = auth_result["data"]["data"]

        # Afficher toutes les pages
        for i, page in enumerate(pages):
            print(f"[{i}] {page['name']} (ID: {page['id']})")

        choice = int(input("Choisis la page : "))

        if 0 <= choice < len(pages):
            selected_page = pages[choice]
            return selected_page["id"], selected_page["access_token"]
        return {
            "status": "error",
            "message": "Choix invalide.",
            "details": {
                "type": "validation",
                "errors": [f"Choix invalide. Entre un nombre entre 0 et {len(pages) - 1}."],
            },
        }

    except Exception as e:
        return {
            "status": "error",
            "message": "Une erreur inattendue est survenue",
            "details": {"type": "unexpected", "info": str(e)},
        }
