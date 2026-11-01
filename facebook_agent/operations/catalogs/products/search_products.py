from facebook_agent.graph import check_required, collect_pages, error, success

# image_url et url servent aux cartes de l'interface web (retirés pour le modèle)
PRODUCT_FIELDS = "id,name,retailer_id,description,price,sale_price,availability,condition,image_url,url"


def search_products(catalog_id: str, partial_name: str, access_token: str) -> dict:
    """Search a catalog for products whose name contains a given text (case-insensitive).

    Reads every page of products of the catalog (fields id, name, retailer_id, description,
    price, sale_price, availability, condition, image_url, url; safety limit of 50 pages), keeps those
    whose name contains partial_name, and returns a simplified list.

    Parameters:
        - Input-catalog_id (str, mandatory): ID of the product catalog.
          Example: "CATALOG_ID_EXAMPLE"
        - Input-partial_name (str, mandatory): Text to look for in the product name (case-insensitive).
          Example: "T-shirt"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict whose "data" is the list of matching products (keys id = Facebook ID,
            retailer_id = ID chosen by the seller, used by the product sets, name, description,
            price as displayed by Facebook, e.g. "19,99 €", sale_price (the promotional price, same
            format; absent when the product has no promotion), condition, availability, and image_url
            = URL of the product image and url = page of the product on the seller's site when the catalog
            has them); empty list
            when no product matches. "truncated": true is added when the 50-page limit was reached (the rest of
            the catalog was not searched).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "PRODUCT_ID_EXAMPLE_B",
                            "retailer_id": "RETAILER_ID_EXAMPLE_2",
                            "name": "Produit test facebook_agent 20261031-1232 B",
                            "description": "Produit de test créé puis supprimé automatiquement",
                            "price": "19,99 €",
                            "condition": "new",
                            "availability": "in stock"
                        }
                    ]
                }
            }
        Errors:
            - validation: catalog_id, partial_name or access_token is empty (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(catalog_id=catalog_id, partial_name=partial_name, access_token=access_token):
            return invalid

        # Toutes les pages du catalogue sont parcourues (limite de sécurité : graph.MAX_PAGES).
        result = collect_pages(
            f"{catalog_id}/products", access_token,
            params={"fields": PRODUCT_FIELDS},
            error_message="Erreur lors de la récupération des produits.",
        )
        if result["status"] == "error":
            return result

        # Filtrage des produits (liste vide si aucune correspondance)
        matching = []
        for product in result["data"].get("data", []):
            if partial_name.lower() in product.get("name", "").lower():
                item = {
                    "id": product.get("id"),
                    "retailer_id": product.get("retailer_id"),  # identifiant vendeur (product sets)
                    "name": product.get("name"),
                    "description": product.get("description"),
                    "price": product.get("price", "").replace("\xa0", " "),
                    "condition": product.get("condition"),
                    "availability": product.get("availability"),
                }
                if product.get("sale_price"):  # promotion en cours seulement : absent sinon
                    item["sale_price"] = str(product["sale_price"]).replace("\xa0", " ")
                for key in ("image_url", "url"):  # cartes de l'interface web (retirés pour le modèle)
                    if product.get(key):
                        item[key] = product[key]
                matching.append(item)
        found = {"data": matching}
        if result["data"].get("truncated"):  # limite de 50 pages atteinte : recherche incomplète
            found["truncated"] = True
        return success(found)

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
