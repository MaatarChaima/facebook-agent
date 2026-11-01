from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.local_files import is_url, missing_file_error


def upload_photo(page_id: str, image_path_or_url: str, page_token: str, caption: str = "") -> dict:
    """Publish a photo on the page.

    Sends POST /{page_id}/photos: the photo is published immediately.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-image_path_or_url (str, mandatory): http(s) URL of a hosted image, or path of a local image
          (uploaded as multipart). A value that is not an http(s) URL must be an existing file.
          Example: "https://example.com/photo.jpg"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-caption (str, optional): Text published with the photo (default: none).
          Example: "Our new shop"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: the id of the photo and the post_id of the post created with it.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "PHOTO_ID_EXAMPLE",
                    "post_id": "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, or the local file is not found (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, image_path_or_url=image_path_or_url, page_token=page_token):
            return invalid

        path = f"{page_id}/photos"
        error_message = "Échec de la publication de la photo."

        # Cas 1 : image déjà hébergée (URL http/https)
        if is_url(image_path_or_url):
            return call_graph(
                "POST", path, page_token,
                data={"url": image_path_or_url, "caption": caption},
                error_message=error_message,
                timeout=UPLOAD_TIMEOUT,
            )

        # Cas 2 : fichier local (upload binaire) ; un chemin inexistant n'est jamais envoyé comme URL
        if invalid := missing_file_error(image_path_or_url):
            return invalid
        with open(image_path_or_url, "rb") as image:
            return call_graph(
                "POST", path, page_token,
                data={"caption": caption},
                files={"source": image},
                error_message=error_message,
                timeout=UPLOAD_TIMEOUT,
            )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
