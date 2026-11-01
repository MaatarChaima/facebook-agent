import json

from facebook_agent.graph import call_graph, check_required, collect_pages, error, validation_error
from facebook_agent.operations.catalogs.product_sets.filters import (
    FILTER_FORMAT_HELP,
    creation_retailer_ids,
    is_valid_creation_filter,
)

VALIDATION_MESSAGE = "Une ou plusieurs erreurs de validation sont survenues."
CREATION_ERROR = "Échec de la création du product set."


def create_product_set(catalog_id: str, name: str, product_filter: dict, access_token: str) -> dict:
    """Create a product set (a group of products) in a catalog.

    Before creating the set, checks that no set of the catalog has this name
    (GET /{catalog_id}/product_sets, every page) and that each retailer ID exists in the catalog
    (one GET per ID). Then sends POST /{catalog_id}/product_sets.

    Parameters:
        - Input-catalog_id (str, mandatory): ID of the catalog.
          Example: "CATALOG_ID_EXAMPLE"
        - Input-name (str, mandatory): Name of the set; it must not be used by another set of the catalog.
          Example: "Summer collection"
        - Input-product_filter (dict, mandatory): Products of the set, in the form
          {"retailer_id": {"is_any": [<retailer IDs>]}} (operator documented by Meta) or
          {"retailer_id": {"in": [<retailer IDs>]}} (accepted by the API), with a non-empty list of
          non-empty strings. The values are retailer IDs (the ID chosen by the seller, e.g. "CASQ-001"),
          NOT the Facebook ID of the product (that one is the field product_item_id): read the product
          with search_products to get its retailer_id. Other filter forms are refused.
          Meta also documents other fields (name, brand, product_type, price, availability...) and
          operators (eq, neq, contains, not_contains, is_not_any, lt, lte, gt, gte, and, or), not
          accepted here: https://developers.facebook.com/docs/marketing-api/reference/product-catalog/product_sets/
          Example: {"retailer_id": {"is_any": ["RETAILER_ID_EXAMPLE_1", "RETAILER_ID_EXAMPLE_2"]}}
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<product set id>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "PRODUCT_SET_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty or the filter has another form (no request is
              sent); a set with the same name exists; some retailer IDs are not in the catalog.
            - api: reading the sets or the products, or creating the set failed (details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    errors = []
    try:
        if invalid := check_required(
            catalog_id=catalog_id, name=name, product_filter=product_filter, access_token=access_token
        ):
            return invalid
        if not is_valid_creation_filter(product_filter):
            return validation_error(FILTER_FORMAT_HELP)

        # Vérifier si le nom existe déjà, sur toutes les pages de sets du catalogue
        existing = collect_pages(f"{catalog_id}/product_sets", access_token, error_message=CREATION_ERROR)
        if existing["status"] == "error":
            return existing
        for product_set in existing["data"]["data"]:
            if product_set.get("name") == name:
                errors.append(f"Un product set avec le nom '{name}' existe déjà (ID: {product_set.get('id')}).")

        # Vérifier que chaque retailer_id existe dans le catalogue
        invalid_ids = []
        for rid in creation_retailer_ids(product_filter):
            found = call_graph(
                "GET", f"{catalog_id}/products", access_token,
                params={"filter": json.dumps({"retailer_id": {"eq": rid}}, separators=(",", ":"))},
                error_message=CREATION_ERROR,
            )
            if found["status"] == "error":
                return found
            # Pas d'erreur mais aucun produit trouvé : retailer_id invalide
            if not found["data"].get("data"):
                invalid_ids.append(rid)
        if invalid_ids:
            errors.append(f"Certains retailer_id sont invalides : {', '.join(invalid_ids)}")
        if errors:
            return validation_error(errors, message=VALIDATION_MESSAGE)

        return call_graph(
            "POST", f"{catalog_id}/product_sets", access_token,
            data={"name": name, "filter": json.dumps(product_filter)},
            error_message=CREATION_ERROR,
        )

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
