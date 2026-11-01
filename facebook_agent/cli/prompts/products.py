import re

from facebook_agent.cli.prompts import InvalidInputError
from facebook_agent.graph import call_graph

PRICE_PATTERN = r'^\d+(\.\d{1,2})?$'
# Statuts qui ne permettent pas de définir une quantité
NO_QUANTITY_STATUS = {"out of stock", "discontinued", "pending", "mark_as_sold"}
LOWERCASE_FIELDS = ["availability", "condition", "gender", "age_group"]


def get_product_id() -> str:
    """Ask the user for the ID of a product.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID du produit : ").strip()


def get_name_partial_match() -> str:
    """Ask the user for the text to look for in product names.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("Chaîne partielle à chercher dans le nom : ").strip()


def get_create_product_data() -> dict:
    """Ask the fields of a new product (keys of create_product's data).

    The quantity is not asked when the availability does not allow a sale.

    Returns:
        The data dict, with only the fields typed.

    Raises:
        InvalidInputError: A mandatory field is missing or a price is invalid.
    """
    product_fields = {
        # Champs obligatoires
        "retailer_id": "→ ID unique du produit (retailer_id) : ",
        "name": "→ Nom du produit : ",
        "description": "→ Description : ",
        "availability": (
            "→ Disponibilité (in stock / out of stock / preorder / available for order"
            " / discontinued / pending / mark_as_sold) : "
        ),
        "condition": (
            "→ État (new / refurbished / used / used_like_new / used_good / used_fair"
            " / cpo / open_box_new) : "
        ),
        "price": "→ Prix (ex: 19.99) : ",
        "currency": "→ Devise (ex: EUR, USD, TND, etc.) : ",
        "image_url": "→ Lien vers l’image principale (URL ou fichier local) : ",

        # Champs optionnels
        "url": "→ Lien vers la page produit (facultatif) : ",
        "gender": "→ Genre (female / male / unisex, facultatif) : ",
        "color": "→ Couleur (facultatif) : ",
        "size": "→ Taille (facultatif) : ",
        "age_group": "→ Tranche d'âge (adult / kids / teen / newborn / all ages, facultatif) : ",
        "material": "→ Matériau (facultatif) : ",
        "gtin": "→ GTIN (facultatif) : ",
        "brand": "→ Nom de la marque (facultatif) : ",
        "fb_product_category": "→ Catégorie Facebook (facultatif) : ",
        "quantity_to_sell_on_facebook": "→ Quantité à vendre sur Facebook (facultatif) : ",
        "sale_price": "→ Prix soldé (facultatif) : ",
    }

    data = {}
    errors = []
    availability = None
    price = None

    for key, prompt in product_fields.items():
        # Statut qui interdit la quantité : ne pas la demander
        if key == "quantity_to_sell_on_facebook" and availability in NO_QUANTITY_STATUS:
            continue

        value = input(prompt).strip()

        if key in LOWERCASE_FIELDS and value:
            value = value.lower()

        if key == "availability" and value:
            availability = value

        # Virgule acceptée comme séparateur décimal (19,99 -> 19.99)
        if key in ("price", "sale_price"):
            value = value.replace(",", ".")

        # Validation du prix
        if key == "price" and value:
            if not re.match(PRICE_PATTERN, value):
                errors.append("Prix invalide : saisis un nombre avec au maximum 2 chiffres après la virgule ")
                continue
            try:
                price = float(value)
            except ValueError:
                errors.append("Prix invalide ")
                continue

        # Validation du prix soldé
        if key == "sale_price" and value:
            if not re.match(PRICE_PATTERN, value):
                errors.append("Prix soldé invalide : saisis un nombre avec au maximum 2 chiffres après la virgule ")
                continue
            try:
                sale_price = float(value)
                if price is not None and sale_price >= price:
                    errors.append("Le prix soldé doit être inférieur au prix normal.")
                    continue
            except ValueError:
                errors.append("Prix soldé invalide.")
                continue

        if value:
            data[key] = value

    # Vérification des champs obligatoires
    required_fields = [
        "retailer_id", "name", "description", "availability",
        "condition", "price", "currency", "image_url",
    ]
    for field in required_fields:
        if not data.get(field):
            errors.append(f"Le champ obligatoire '{field}' est manquant.")

    if errors:
        raise InvalidInputError(errors)
    return data


def get_update_data(product_id: str, access_token: str) -> dict:
    """Ask the fields to update (keys of update_product's data).

    The current availability is read (GET /{product_id}) to decide whether the quantity
    can be asked.

    Args:
        product_id: ID of the product.
        access_token: User access token.

    Returns:
        The data dict, with only the fields typed.

    Raises:
        InvalidInputError: A price is invalid, or reading the product failed.
    """
    fields = {
        "name": "→ Nouveau nom : ",
        "description": "→ Nouvelle description : ",
        "availability": (
            "→ Nouvelle disponibilité (in stock/ out of stock/ preorder/ available for order"
            "/ discontinued/ pending/ mark_as_sold) : "
        ),
        "condition": (
            "→ Nouvel état (new/ refurbished/ used/ used_like_new/ used_good/ used_fair"
            "/ cpo/ open_box_new) : "
        ),
        "price": "→ Nouveau prix (ex: 19.99) : ",
        "url": "→ Nouveau lien vers la page produit : ",
        "image_url": "→ Nouveau lien vers l’image principale : ",
        "brand": "→ Nouvelle marque : ",
        "fb_product_category": "→ Nouvelle catégorie Facebook : ",
        # quantity_to_sell_on_facebook est demandé juste après la disponibilité
        "sale_price": "→ Nouveau prix soldé : ",
        "gender": "→ Genre cible (female/ male/ unisex) : ",
        "color": "→ Couleur : ",
        "size": "→ Taille : ",
        "age_group": "→ Tranche d’âge (adult/ all ages/ infant/ kids/ newborn/ teen/ toddler) : ",
        "material": "→ Matériau : ",
        "gtin": "→ Code-barres universel : ",
    }

    data = {}
    errors = []
    price = None

    try:
        for key, prompt in fields.items():
            value = input(prompt).strip()

            if key in LOWERCASE_FIELDS and value:
                value = value.lower()

            # Virgule acceptée comme séparateur décimal (19,99 -> 19.99)
            if key in ("price", "sale_price"):
                value = value.replace(",", ".")

            # Disponibilité : demander la quantité juste après si la vente est possible
            if key == "availability":
                old_info = call_graph("GET", product_id, access_token, params={"fields": "availability"})
                if old_info["status"] == "error":
                    errors.append(old_info["message"])
                    old_availability = ""
                else:
                    old_availability = old_info["data"].get("availability", "").lower()

                new_availability = value if value else old_availability
                if new_availability not in NO_QUANTITY_STATUS:
                    quantity = input("→ Nouvelle quantité disponible : ").strip()
                    if quantity:
                        data["quantity_to_sell_on_facebook"] = quantity
                if value:
                    data[key] = value  # nouvelle disponibilité envoyée à l'API
                continue

            if key == "price" and value:
                if not re.match(PRICE_PATTERN, value):
                    errors.append("Prix invalide : saisis un nombre avec au maximum 2 chiffres après la virgule.")
                    continue
                try:
                    price = float(value)
                except ValueError:
                    errors.append("Prix invalide : saisis un nombre.")
                    continue

            if key == "sale_price" and value:
                if not re.match(PRICE_PATTERN, value):
                    errors.append(
                        "Prix soldé invalide : saisis un nombre avec au maximum 2 chiffres après la virgule"
                    )
                    continue
                try:
                    sale_price = float(value)
                    if price is not None and sale_price >= price:
                        errors.append("Le prix soldé doit être inférieur au prix normal.")
                        continue
                except ValueError:
                    errors.append("Prix soldé invalide.")
                    continue

            if value:
                data[key] = value

    except Exception as e:
        raise InvalidInputError([f"Erreur inattendue : {e}"]) from e

    if errors:
        raise InvalidInputError(errors)
    return data
