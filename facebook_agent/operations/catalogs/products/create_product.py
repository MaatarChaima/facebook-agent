from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.local_files import missing_file_error
from facebook_agent.operations.catalogs.products.prices import to_cents
from facebook_agent.operations.catalogs.products.product_images import (
    is_local_image,
    missing_page_credentials,
    upload_local_image,
)

CREATION_ERROR = "Erreur lors de la création du produit."
# Noms des champs de l'API Graph, identiques à ceux de update_product
REQUIRED_KEYS = ["retailer_id", "name", "description", "availability", "condition", "price", "currency",
                 "image_url"]
OPTIONAL_KEYS = ["url", "brand", "fb_product_category", "quantity_to_sell_on_facebook", "gender", "color", "size",
                 "age_group", "material", "gtin", "sale_price"]
ACCEPTED_KEYS = REQUIRED_KEYS + OPTIONAL_KEYS
PRICE_KEYS = ("price", "sale_price")  # convertis en centimes


def create_product(
    catalog_id: str,
    access_token: str,
    data: dict,
    page_id: str | None = None,
    page_token: str | None = None,
) -> dict:
    """Create a product in a catalog.

    Sends POST /{catalog_id}/products.

    Parameters:
        - Input-catalog_id (str, mandatory): ID of the catalog.
          Example: "CATALOG_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.
        - Input-data (dict, mandatory): Product fields, with the Graph API field names (the same as update_product). Keys
          with an empty value are not sent; any other key is refused.
          Keys:
              - Key-retailer_id (str, mandatory): Your own unique ID of the product.
              - Key-name (str, mandatory): Product name.
              - Key-description (str, mandatory): Product description.
              - Key-availability (str, mandatory): Stock status.
                Choices:
                    - in stock -> available, ships immediately
                    - out of stock -> currently not available
                    - preorder -> can be ordered before it is available
                    - available for order -> can be ordered, ships later
                    - discontinued -> no longer sold
                    - pending -> availability not known yet
                    - mark_as_sold -> marked as sold
                    - mark_as_expired -> marked as expired
              - Key-condition (str, mandatory): Product condition.
                Choices:
                    - new -> new product
                    - refurbished -> restored to working order
                    - used -> second-hand product
                    - used_like_new -> second-hand, like new
                    - used_good -> second-hand, good condition
                    - used_fair -> second-hand, fair condition
                    - cpo -> certified pre-owned
                    - open_box_new -> new product, opened box
              - Key-price (str, mandatory): Price, dot or comma as decimal separator ("19,99"); sent in cents (1999).
              - Key-currency (str, mandatory): ISO 4217 currency code, e.g. "EUR".
              - Key-image_url (str, mandatory): http(s) URL of the main image, or a local file path.
                A local file requires page_id and page_token: the image is first uploaded as an
                unpublished photo of the page (POST /{page_id}/photos, published=false), then its
                public URL is used.
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
              - Key-sale_price (str, optional): Discounted price, same format as price; sent in cents.
          Example: {"retailer_id": "RETAILER_ID_EXAMPLE", "name": "Blue T-shirt", "description": "Cotton",
                    "availability": "in stock", "condition": "new", "price": "19,99", "currency": "EUR",
                    "image_url": "https://example.com/product.jpg"}
        - Input-page_id (str, optional): ID of the page that hosts a local image. Needed only when image_url is a file.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, optional): Page access token for page_id. Needed only when image_url is a file.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<product id>"}. The local image variant returns
            the same structure.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "PRODUCT_ID_EXAMPLE_A"
                }
            }
        Errors:
            - validation: catalog_id, access_token or data is empty; an unknown key in data (the error lists
              the accepted keys); a mandatory key missing or empty; a local image without page_id /
              page_token, or not found. All checks are done before any request.
            - api: uploading the local image, reading its URL or creating the product failed
              (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception, e.g. a price that is not a number (details.info).
    """
    try:
        if invalid := check_required(catalog_id=catalog_id, access_token=access_token, data=data):
            return invalid
        unknown = sorted(set(data) - set(ACCEPTED_KEYS))
        if unknown:
            return validation_error(
                [f"Clé inconnue dans data : {key}" for key in unknown]
                + [f"Clés acceptées : {', '.join(ACCEPTED_KEYS)}"],
                message="Certaines clés de data ne sont pas acceptées.",
            )
        missing_keys = [key for key in REQUIRED_KEYS if not str(data.get(key) or "").strip()]
        if missing_keys:
            return validation_error([f"La clé data['{key}'] est obligatoire." for key in missing_keys])
        local_image = is_local_image(data["image_url"])
        if local_image and (invalid := missing_page_credentials(page_id, page_token)):
            return invalid
        if local_image and (invalid := missing_file_error(data["image_url"])):
            return invalid

        # Les clés de data sont déjà les champs de l'API ; seuls les prix sont convertis en centimes
        product_data = {key: (to_cents(value) if key in PRICE_KEYS else value)
                        for key, value in data.items() if value}

        # Image locale : publiée (non visible) sur la page, puis référencée par son URL publique
        if local_image:
            image_url, failure = upload_local_image(data["image_url"], page_id, page_token, CREATION_ERROR)
            if failure:
                return failure
            product_data["image_url"] = image_url

        return call_graph("POST", f"{catalog_id}/products", access_token, data=product_data, error_message=CREATION_ERROR)

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
