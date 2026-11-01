"""Shared helpers for product set filters (not an operation itself)."""

# Opérateurs acceptés pour une liste de produits : is_any (documenté par Meta) et in (accepté par l'API,
# utilisé par la capture des exemples). Les valeurs sont des retailer_id, pas des ID Facebook.
CREATION_OPERATORS = ("is_any", "in")
FILTER_FORMAT_HELP = ('Le filtre doit être de la forme {"retailer_id": {"is_any": ["RID1", "RID2"]}} (ou "in" au lieu '
                      'de "is_any"), avec les retailer_id des produits (l\'identifiant défini par le vendeur, pas '
                      "l'ID Facebook du produit).")


def retailer_ids_from_filter(product_filter: dict) -> set[str]:
    """Return the retailer IDs selected by a product set filter.

    Supported formats:
        {"retailer_id": {"in": [...]}}       written by create_product_set
        {"retailer_id": {"is_any": [...]}}   written by update_product_set
        {"retailer_id": {"eq": "..."}}
        {"or": [<any of the above>, ...]}    used by sets created in Commerce Manager

    Args:
        product_filter: Filter of the product set, as a dict.

    Returns:
        The set of retailer IDs (as strings).
    """
    ids: set[str] = set()
    for condition in product_filter.get("or", []):
        ids |= retailer_ids_from_filter(condition)
    rule = product_filter.get("retailer_id", {})
    for operator in ("in", "is_any"):
        ids |= {str(rid) for rid in rule.get(operator, [])}
    if "eq" in rule:
        ids.add(str(rule["eq"]))
    return ids


def is_valid_creation_filter(product_filter: object) -> bool:
    """Tell whether a filter has the format accepted by create_product_set.

    Args:
        product_filter: Value to check.

    Returns:
        True for {"retailer_id": {"is_any": [...]}} or {"retailer_id": {"in": [...]}}, with a non-empty
        list of non-empty strings.
    """
    if not isinstance(product_filter, dict) or set(product_filter) != {"retailer_id"}:
        return False
    rule = product_filter["retailer_id"]
    if not isinstance(rule, dict) or len(rule) != 1 or next(iter(rule)) not in CREATION_OPERATORS:
        return False
    values = next(iter(rule.values()))
    return isinstance(values, list) and bool(values) and all(isinstance(rid, str) and rid.strip() for rid in values)


def creation_retailer_ids(product_filter: dict) -> list[str]:
    """Retailer IDs of a filter accepted by is_valid_creation_filter.

    Args:
        product_filter: {"retailer_id": {"is_any" | "in": [...]}}.

    Returns:
        The list of retailer IDs, in order.
    """
    return list(next(iter(product_filter["retailer_id"].values())))
