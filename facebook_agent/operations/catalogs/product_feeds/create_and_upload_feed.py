from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, check_required, error, success, validation_error
from facebook_agent.local_files import extension, is_url, missing_file_error
from facebook_agent.operations.catalogs.product_feeds.feed_files import (
    FEED_EXTENSIONS,
    FORMAT_ERROR,
    FORMAT_HELP,
    upload_local_feed,
)


def create_and_upload_feed(catalog_id: str, name: str, feed_url: str, access_token: str) -> dict:
    """Create a product feed in a catalog and upload a feed file to it.

    Two requests: POST /{catalog_id}/product_feeds creates the feed, then
    POST /{feed_id}/uploads sends the file. If the upload fails, the feed already exists.
    Facebook imports the products asynchronously, after the answer.

    Parameters:
        - Input-catalog_id (str, mandatory): ID of the catalog.
          Example: "CATALOG_ID_EXAMPLE"
        - Input-name (str, mandatory): Name of the new feed.
          Example: "Summer Collection Feed"
        - Input-feed_url (str, mandatory): Public http(s) URL of the feed file, or path of a local file (an .xlsx file is
          converted to CSV first). Accepted extensions: .csv, .tsv, .xml, .xlsx, .json.
          Example: "https://example.com/products.csv"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict with feed_id (the new feed, answer of the first request) and upload_id
            (the upload session, answer of the second request).
        Example (success):
            {
                "status": "success",
                "data": {
                    "feed_id": "FEED_ID_EXAMPLE",
                    "upload_id": "ID_EXAMPLE_21"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, the file extension is not one of .csv, .tsv,
              .xml, .xlsx, .json, or the local file is not found (no request is sent).
            - api: creating the feed or uploading the file failed (details.error), or the creation
              answered without id (details.response).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(catalog_id=catalog_id, name=name, feed_url=feed_url, access_token=access_token):
            return invalid

        feed_url = feed_url.strip()
        if extension(feed_url) not in FEED_EXTENSIONS:  # chemin de l'URL, sans les paramètres
            return validation_error(FORMAT_HELP, message=FORMAT_ERROR)
        # Fichier local vérifié avant toute requête (aucun feed vide créé pour rien)
        if not is_url(feed_url) and (invalid := missing_file_error(feed_url)):
            return invalid

        # Étape 1 : créer le product feed
        created = call_graph(
            "POST", f"{catalog_id}/product_feeds", access_token.strip(),
            data={"name": name.strip()},
            error_message="Échec de la création du feed",
        )
        if created["status"] == "error":
            return created
        feed_id = created["data"].get("id")
        if not feed_id:
            return error("Échec de la création du feed", {"type": "api", "response": created["data"]})

        # Étape 2 : uploader le fichier dans le feed créé
        upload_path = f"{feed_id}/uploads"
        upload_error = "Erreur lors de l'upload du fichier."
        if is_url(feed_url):
            # Cas fichier hébergé
            upload = call_graph(
                "POST", upload_path, access_token.strip(),
                data={"url": feed_url},
                error_message=upload_error,
                timeout=UPLOAD_TIMEOUT,
            )
        else:
            # Cas fichier local (existence déjà vérifiée)
            upload = upload_local_feed(feed_url, upload_path, access_token, upload_error)
        if upload["status"] == "error":
            return upload
        # L'ID du feed (étape 1) et l'ID de l'envoi (étape 2) sont renvoyés ensemble
        return success({"feed_id": feed_id, "upload_id": upload["data"].get("id")})

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
