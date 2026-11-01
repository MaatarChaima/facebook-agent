def _ask_id_list(prompt: str) -> list[str]:
    """Ask a comma-separated list of IDs and return the non-empty ones."""
    ids = input(prompt).strip()
    if not ids:
        return []
    return [str(rid).strip() for rid in ids.split(",") if str(rid).strip()]


def get_product_set_id() -> str:
    """Ask the user for the ID of a product set.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID du set : ").strip()


def get_set_name() -> str:
    """Ask the user for the name of a new product set.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Nom : ")


def get_new_set_name() -> str:
    """Ask the user for the new name of a product set (empty to keep it).

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("Nouveau nom (laisser vide pour garder le nom actuel) : ").strip()


def get_retailer_ids() -> dict | None:
    """Ask retailer IDs, separated by commas, and build the product set filter.

    Returns:
        {"retailer_id": {"in": [...]}}, or None if no ID is typed.
    """
    id_list = _ask_id_list("Liste des retailer_id (séparés par des virgules) : ")
    if not id_list:
        return None
    return {"retailer_id": {"in": id_list}}


def get_retailer_ids_to_add() -> list[str]:
    """Ask the retailer IDs to add to a product set, separated by commas.

    Returns:
        The list of IDs (empty if none).
    """
    return _ask_id_list("Retailer IDs à AJOUTER (séparés par des virgules, laisser vide si aucun) : ")


def get_retailer_ids_to_remove() -> list[str]:
    """Ask the retailer IDs to remove from a product set, separated by commas.

    Returns:
        The list of IDs (empty if none).
    """
    return _ask_id_list("Retailer IDs à SUPPRIMER (séparés par des virgules, laisser vide si aucun) : ")
