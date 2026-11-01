import json

from facebook_agent.graph import call_graph, check_required, collect_pages, error, validation_error
from facebook_agent.operations.catalogs.product_sets.filters import retailer_ids_from_filter


def update_product_set(
    product_set_id: str,
    access_token: str,
    name: str | None = None,
    add_product_ids: list[str] | None = None,
    remove_product_ids: list[str] | None = None,
) -> dict:
    """Rename a product set and/or add or remove products.

    Reads the catalog of the set, checks the new name (every page of sets) and the IDs, reads the current
    filter, then sends POST /{product_set_id} with the name and the filter
    {"retailer_id": {"is_any": [<sorted retailer IDs>]}}.

    Parameters:
        - Input-product_set_id (str, mandatory): ID of the product set.
          Example: "PRODUCT_SET_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.
        - Input-name (str, optional): New name. Default: None (the current name is kept).
          Example: "Summer collection 2026"
        - Input-add_product_ids (list, optional): Retailer IDs of catalog products to add (the ID chosen by the
          seller, not the Facebook ID of the product: read it with search_products). Default: None.
          Example: ["RETAILER_ID_EXAMPLE_2"]
        - Input-remove_product_ids (list, optional): Retailer IDs of products of the set to remove (not the
          Facebook IDs). Default: None.
          Example: ["RETAILER_ID_EXAMPLE_1"]

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
            - validation: product_set_id or access_token is empty, or none of name, add_product_ids and
              remove_product_ids is given (no request is sent); the name is used by another set;
              IDs to add are not in the catalog or already in the set; IDs to remove are not
              in the set.
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception, e.g. a set without product_catalog (details.info).
    """
    errors = []  # erreurs métier cumulables

    try:
        if invalid := check_required(product_set_id=product_set_id, access_token=access_token):
            return invalid
        if not any([name, add_product_ids, remove_product_ids]):
            return validation_error(
                "Au moins un champ (name, add_product_ids, remove_product_ids) doit être renseigné."
            )

        # Récupérer le catalogue du product set
        catalog = call_graph(
            "GET", product_set_id, access_token,
            params={"fields": "product_catalog{id}"},
            error_message="Échec de la récupération du catalog id.",
        )
        if catalog["status"] == "error":
            return catalog
        catalog_id = catalog["data"]["product_catalog"]["id"]

        # Vérifier que le nouveau nom n'est pas déjà utilisé, sur toutes les pages de sets du catalogue
        existing = collect_pages(f"{catalog_id}/product_sets", access_token,
                                 error_message="Échec de la vérification du nom du product set.")
        if existing["status"] == "error":
            return existing
        for product_set in existing["data"]["data"]:
            # Le set modifié lui-même n'est pas un doublon (garder son nom actuel est permis)
            if product_set.get("name") == name and product_set.get("id") != product_set_id:
                errors.append(f"Un product set avec le nom '{name}' existe déjà (ID: {product_set.get('id')}).")

        # Vérifier que les produits à ajouter existent dans le catalogue
        invalid_add = []
        if add_product_ids:
            for rid in add_product_ids:
                found = call_graph(
                    "GET", f"{catalog_id}/products", access_token,
                    params={"filter": json.dumps({"retailer_id": {"eq": rid}}, separators=(",", ":"))},
                    error_message="Échec lors de la vérification des produits à ajouter.",
                )
                if found["status"] == "error":
                    return found
                if not found["data"].get("data"):  # produit non trouvé : erreur métier
                    invalid_add.append(rid)
        if invalid_add:
            errors.append(f"Ces produits à ajouter n'existent pas dans le catalogue : {', '.join(invalid_add)}")

        # Obtenir les infos actuelles du set
        current = call_graph(
            "GET", product_set_id, access_token,
            params={"fields": "name,filter"},
            error_message="Échec de la récupération des informations du product set.",
        )
        if current["status"] == "error":
            return current
        current_name = current["data"].get("name", "")
        current_filter = json.loads(current["data"].get("filter") or "{}")
        current_product_ids = retailer_ids_from_filter(current_filter)

        # Vérifier les produits à supprimer
        invalid_remove = []
        if remove_product_ids:
            for rid in remove_product_ids:
                if rid not in current_product_ids:  # produit absent : erreur métier
                    invalid_remove.append(rid)
        if invalid_remove:
            errors.append(
                f"Ces produits à supprimer n'existent pas dans le product set : {', '.join(invalid_remove)}"
            )

        # Vérifier les doublons dans l'ajout
        if add_product_ids:
            duplicates = [pid for pid in add_product_ids if pid in current_product_ids]
            if duplicates:
                errors.append(f"Ces produits existent déjà dans le product set : {', '.join(duplicates)}")

        if errors:
            return validation_error(errors, message="Des erreurs de validation ont été détectées.")

        # Mise à jour des IDs
        if add_product_ids:
            current_product_ids.update(add_product_ids)
        if remove_product_ids:
            current_product_ids.difference_update(remove_product_ids)

        new_filter = {"retailer_id": {"is_any": sorted(current_product_ids)}}  # ordre stable
        new_name = name if name else current_name

        return call_graph(
            "POST", product_set_id, access_token,
            data={"name": new_name, "filter": json.dumps(new_filter)},
            error_message="Échec de la mise à jour du product set.",
        )

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
