from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.local_files import extension, is_url, missing_file_error
from facebook_agent.operations.catalogs.product_feeds.feed_files import (
    FEED_EXTENSIONS,
    FORMAT_ERROR,
    FORMAT_HELP,
    upload_local_feed,
)


def reupload_product_feed(feed_id: str, access_token: str, feed_url: str) -> dict:
    """Upload a new file to an existing product feed.

    Sends POST /{feed_id}/uploads. Facebook imports the products asynchronously.

    Parameters:
        - Input-feed_id (str, mandatory): ID of the product feed.
          Example: "FEED_ID_EXAMPLE"
        - Input-access_token (str, mandatory): User access token (not a Page token) with the catalog_management permission.
        - Input-feed_url (str, mandatory): Public http(s) URL of the feed file, or path of a local file (an .xlsx file is
          converted to CSV first). Accepted extensions: .csv, .tsv, .xml, .xlsx, .json.
          Example: "https://example.com/products.csv"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<upload session id>"}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "ID_EXAMPLE_4"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, the file extension is not one of .csv, .tsv,
              .xml, .xlsx, .json, or the local file is not found (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(feed_id=feed_id, access_token=access_token, feed_url=feed_url):
            return invalid

        feed_url = feed_url.strip()
        if extension(feed_url) not in FEED_EXTENSIONS:  # chemin de l'URL, sans les paramètres
            return validation_error(FORMAT_HELP, message=FORMAT_ERROR)
        # Fichier local vérifié avant toute requête
        if not is_url(feed_url) and (invalid := missing_file_error(feed_url)):
            return invalid

        upload_path = f"{feed_id}/uploads"
        upload_error = "Erreur lors de l'upload du feed."

        # Cas 1 : fichier en ligne (URL publique)
        if is_url(feed_url):
            return call_graph(
                "POST", upload_path, access_token.strip(),
                data={"url": feed_url},
                error_message=upload_error,
                timeout=UPLOAD_TIMEOUT,
            )

        # Cas 2 : fichier local (existence déjà vérifiée)
        return upload_local_feed(feed_url, upload_path, access_token.strip(), upload_error)

    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
