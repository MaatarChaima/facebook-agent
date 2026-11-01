import json
import re
import time

from facebook_agent.graph import call_graph, check_required, error, success, validation_error
from facebook_agent.local_files import missing_file_error
from facebook_agent.operations.catalogs.products.prices import parse_display_price, to_cents
from facebook_agent.operations.catalogs.products.product_images import (
    is_local_image,
    missing_page_credentials,
    upload_local_image,
)

REQUIRED_FIELDS = ["name", "description", "availability", "condition", "price", "image_url"]
OPTIONAL_FIELDS = ["sale_price", "currency", "url", "brand", "fb_product_category", "quantity_to_sell_on_facebook",
                   "gender", "color", "size", "age_group", "material", "gtin"]
ACCEPTED_KEYS = REQUIRED_FIELDS + OPTIONAL_FIELDS
UPDATE_ERROR = "Erreur lors de la mise à jour du produit"
REMOVE = "-"  # marqueur de suppression d'un champ optionnel ; pour sale_price : retrait de la promotion
BATCH_POLL_WAIT = 5   # secondes entre deux lectures du statut du lot items_batch
BATCH_MAX_WAIT = 30   # au-delà, le traitement est encore en cours chez Facebook (statut "pending")
PENDING_MESSAGE = "Traitement toujours en cours chez Facebook : vérifie dans quelques minutes."
NO_CATALOG = ("Retrait de la promotion impossible sans catalog_id (CATALOG_ID du .env) : Facebook ne l'efface que "
              "par le Catalog Batch API du catalogue.")


def _given(value: object) -> bool:
    """True if a price is really provided (not missing, empty or the "-" deletion marker)."""
    return value not in (None, "", "-")


def _remove_promotion(product_id: str, catalog_id: str, access_token: str) -> dict:
    """Clear sale_price with the Catalog Batch API, then wait for Facebook to process the batch.

    Reads the retailer_id (GET /{product_id}?fields=retailer_id), sends POST /{catalog_id}/items_batch
    with an UPDATE {"id": retailer_id, "sale_price": ""}, then reads
    GET /{catalog_id}/check_batch_request_status every 5 s, for at most 30 s.

    Args:
        product_id: ID of the product.
        catalog_id: ID of its catalog.
        access_token: User access token with the catalog_management permission.

    Returns:
        A success ({"success": true, "promotion_removed": true}), an error, or {"status": "pending",
        ...} when the batch is still being processed after 30 s (neither a success nor a failure).
    """
    read = call_graph("GET", product_id, access_token, params={"fields": "retailer_id"},
                      error_message="Lecture du retailer_id du produit impossible.")
    if read["status"] != "success":
        return read
    retailer_id = read["data"].get("retailer_id")
    if not retailer_id:
        return error("Retrait de la promotion impossible : retailer_id du produit introuvable.",
                     {"type": "api", "answer": read["data"]})
    requests = json.dumps([{"method": "UPDATE", "data": {"id": retailer_id, "sale_price": ""}}])
    sent = call_graph("POST", f"{catalog_id}/items_batch", access_token,
                      data={"item_type": "PRODUCT_ITEM", "requests": requests},
                      error_message="Erreur lors du retrait de la promotion.")
    if sent["status"] != "success":
        return sent
    handles = sent["data"].get("handles") or []
    if not handles:
        return error("Facebook n'a pas pris en compte le retrait de la promotion (aucun lot créé).",
                     {"type": "api", "answer": sent["data"]})
    waited = 0
    while True:
        status = call_graph("GET", f"{catalog_id}/check_batch_request_status", access_token,
                            params={"handle": handles[0]}, error_message="Lecture du statut du lot impossible.")
        if status["status"] != "success":
            return status
        row = (status["data"].get("data") or [{}])[0]
        if row.get("errors"):
            return error("Facebook a refusé le retrait de la promotion.", {"type": "api", "errors": row["errors"]})
        if row.get("status") == "finished":
            return success({"success": True, "promotion_removed": True})
        if waited >= BATCH_MAX_WAIT:
            return {"status": "pending", "message": PENDING_MESSAGE,
                    "details": {"type": "pending", "batch_status": row.get("status")}}
        time.sleep(BATCH_POLL_WAIT)
        waited += BATCH_POLL_WAIT


def update_product(
    product_id: str,
    access_token: str,
    data: dict,
    page_id: str | None = None,
    page_token: str | None = None,
    catalog_id: str | None = None,
) -> dict:
    """Update the fields of a catalog product.

    Sends POST /{product_id}. When sale_price is given without price, the current price
    is read first (GET /{product_id}?fields=price). sale_price "-" (remove the promotion) is sent
    afterwards through the Catalog Batch API (see Key-sale_price): POST /{product_id} first for the
    other fields, then the batch.

    Parameters:
        - Input-product_id (str, mandatory): ID of the product to update.
          Example: "PRODUCT_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.
        - Input-data (dict, mandatory): Fields to update, with the Graph API field names. Only the keys present are sent.
          An empty string leaves a field unchanged; "-" clears an optional field and is refused
          for name, description, availability, condition, price and image_url. Any other key
          is refused.
          Keys:
              - Key-name (str, optional): New product name.
              - Key-description (str, optional): New description.
              - Key-availability (str, optional): Stock status.
                Choices:
                    - in stock -> available, ships immediately
                    - out of stock -> currently not available
                    - preorder -> can be ordered before it is available
                    - available for order -> can be ordered, ships later
                    - discontinued -> no longer sold
                    - pending -> availability not known yet
                    - mark_as_sold -> marked as sold
                    - mark_as_expired -> marked as expired
              - Key-condition (str, optional): Product condition.
                Choices:
                    - new -> new product
                    - refurbished -> restored to working order
                    - used -> second-hand product
                    - used_like_new -> second-hand, like new
                    - used_good -> second-hand, good condition
                    - used_fair -> second-hand, fair condition
                    - cpo -> certified pre-owned
                    - open_box_new -> new product, opened box
              - Key-price (str, optional): New price, up to 2 decimals, dot or comma ("21,50"); sent in cents.
              - Key-image_url (str, optional): Image URL (http/https), or a local file path; a local file requires
                page_id and page_token (uploaded as an unpublished photo of the page).
              - Key-sale_price (str, optional): Discounted price, same format; must be lower than price, or than the
                current price (read first) when price is not given. "-" removes the promotion and needs
                catalog_id: the retailer_id is read, then POST /{catalog_id}/items_batch (item_type
                PRODUCT_ITEM, UPDATE {"id": retailer_id, "sale_price": ""}) is sent and its status read every
                5 s (GET /{catalog_id}/check_batch_request_status), for at most 30 s. Tested on the real API on
                2026-10-23: only this request clears sale_price; sale_price "" in POST /{product_id}, and null
                in items_batch or in a JSON body, leave it.
              - Key-currency (str, optional): ISO 4217 currency code, e.g. "EUR".
              - Key-url (str, optional): Link to the product page.
              - Key-brand (str, optional): Brand name.
              - Key-fb_product_category (str, optional): Facebook product category.
              - Key-quantity_to_sell_on_facebook (str, optional): Quantity for sale on Facebook.
              - Key-gender (str, optional): Target gender, sent as given.
              - Key-color (str, optional): Color, sent as given.
              - Key-size (str, optional): Size, sent as given.
              - Key-age_group (str, optional): Target age group, sent as given.
              - Key-material (str, optional): Material, sent as given.
              - Key-gtin (str, optional): Global Trade Item Number, sent as given.
          Example: {"name": "Blue T-shirt", "price": "21,50"}
        - Input-page_id (str, optional): ID of the page that hosts a local image. Needed only when image_url is a local file.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, optional): Page access token for page_id. Needed only when image_url is a local file.
        - Input-catalog_id (str, optional): ID of the catalog of the product. Needed only to remove the promotion
          (sale_price "-").
          Example: "CATALOG_ID_EXAMPLE"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"success": true} (variants fields and price, sale_price
            only, local image); {"success": true, "promotion_removed": true} when the promotion was removed.
            The removal can also return {"status": "pending", "message": ..., "details": {...}} when Facebook
            is still processing the batch after 30 s: neither a success nor a failure, to check later.
        Example (success):
            {
                "status": "success",
                "data": {
                    "success": true
                }
            }
        Example (success, variant "promotion retirée"):
            {
                "status": "success",
                "data": {
                    "success": true,
                    "promotion_removed": true
                }
            }
        Errors:
            - validation: product_id, access_token or data is empty; an unknown key in data (the error
              lists the accepted keys); a local image without page_id / page_token or not
              found; an invalid or unreadable price; sale_price not lower than the price;
              deletion of a mandatory field; no field to update; sale_price "-" without catalog_id.
            - api: uploading the local image, reading its URL or updating the product failed
              (details.status_code, details.error); the batch removing the promotion failed or was
              refused (details.errors); when the other fields were already updated, the message says so.
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    update_data = {}
    errors = []

    try:
        if invalid := check_required(product_id=product_id, access_token=access_token, data=data):
            return invalid
        unknown = sorted(set(data) - set(ACCEPTED_KEYS))
        if unknown:
            return validation_error(
                [f"Clé inconnue dans data : {key}" for key in unknown]
                + [f"Clés acceptées : {', '.join(ACCEPTED_KEYS)}"],
                message="Certaines clés de data ne sont pas acceptées.",
            )
        if is_local_image(data.get("image_url")) and (invalid := missing_page_credentials(page_id, page_token)):
            return invalid
        remove_promotion = data.get("sale_price") == REMOVE
        if remove_promotion and not catalog_id:
            return validation_error([NO_CATALOG], message=NO_CATALOG)

        # Si price et sale_price sont fournis ensemble, sale_price doit être inférieur à price
        if _given(data.get("price")) and _given(data.get("sale_price")):
            try:
                if parse_display_price(data["sale_price"]) >= parse_display_price(data["price"]):
                    errors.append("Le prix soldé doit être inférieur au prix normal.")
            except ValueError:
                pass  # format invalide : signalé plus bas par la validation de chaque prix

        # Si sale_price est fourni sans price, comparer avec le prix actuel
        if _given(data.get("sale_price")) and "price" not in data:
            current = call_graph("GET", product_id, access_token, params={"fields": "price"})
            product_info = current["data"] if current["status"] == "success" else {}
            old_price = product_info.get("price", 0)
            try:
                # Le prix actuel est renvoyé tel qu'affiché (ex. "€21.50", "TND19.98", "19,98 €")
                if parse_display_price(data["sale_price"]) >= parse_display_price(old_price):
                    errors.append("Le prix soldé doit être inférieur au prix normal existant.")
            except ValueError:
                errors.append(f"Prix actuel ou prix soldé illisible (prix actuel reçu : {old_price!r}).")

        for key, value in data.items():
            # Suppression d'un champ obligatoire : interdite
            if value == "-" and key in REQUIRED_FIELDS:
                errors.append(f"Impossible de supprimer un champ obligatoire : {key}")
                continue

            # Suppression d'un champ optionnel (sale_price : retrait de la promotion, par le lot ci-dessous)
            if value == REMOVE:
                if key != "sale_price":
                    update_data[key] = ""
                continue

            # Validation de price et sale_price (virgule acceptée : 19,99 -> 19.99)
            if key in ["price", "sale_price"]:
                value = str(value).replace(",", ".")
                if not re.match(r'^\d+(\.\d{1,2})?$', str(value)):
                    errors.append(
                        f"{key} invalide : saisis un nombre valide avec au maximum 2 chiffres "
                        f"après la virgule (ex: 99.99)"
                    )
                    continue
                update_data[key] = to_cents(value)
                continue

            # Autres champs
            if value != "":
                update_data[key] = value
        if not update_data and not remove_promotion:
            errors.append("Aucun champ à mettre à jour : au moins un attribut doit être renseigné.")

        local_image = is_local_image(data.get("image_url"))
        if local_image and (invalid := missing_file_error(data["image_url"])):
            return invalid

        # Toutes les validations sont faites AVANT d'envoyer l'image locale (aucune photo orpheline)
        if errors:
            return validation_error(errors, message="Des erreurs ont été détectées lors de la mise à jour du produit")

        # Image locale : publiée (non visible) sur la page, puis référencée par son URL publique.
        # Un lien distant (http/https) est déjà dans update_data.
        if local_image:
            image_url, failure = upload_local_image(data["image_url"], page_id, page_token, UPDATE_ERROR)
            if failure:
                return failure
            update_data["image_url"] = image_url

        result = None
        if update_data:  # les autres champs d'abord (POST /{product_id}), puis le retrait de la promotion
            result = call_graph("POST", product_id, access_token, data=update_data, error_message=UPDATE_ERROR)
            if result["status"] != "success" or not remove_promotion:
                return result
        removal = _remove_promotion(product_id, catalog_id, access_token)
        if result and removal["status"] != "success":  # les autres champs, eux, ont bien été modifiés
            removal = {**removal, "message": f"{removal['message']} Les autres champs "
                                             f"({', '.join(update_data)}) ont bien été modifiés."}
        return removal

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
