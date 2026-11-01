from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.operations.pages.photos.page_images import upload_page_image


def update_cover_photo(page_id: str, page_token: str, image_path_or_url: str) -> dict:
    """Replace the cover photo of the page by an image given by its URL or as a local file.

    Two requests: the image is uploaded as a photo of the page with no_story=true (POST /{page_id}/photos:
    url for an http(s) URL, the file as multipart for a local path), then set as cover with
    no_feed_story=true and no_notification=true (POST /{page_id}). Meta does not document a cover made
    from an unpublished photo, so the photo stays among the photos of the page; no story is created in
    the feed.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of a person who can edit the page profile (EDIT_PROFILE task,
          business_management permission).
        - Input-image_path_or_url (str, mandatory): http(s) URL of a hosted image, or path of a local image (uploaded as
          multipart). A value that is not an http(s) URL must be an existing file.
          Example: "https://example.com/cover.jpg"

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"success": true}.
        Example (success):
            {
                "status": "success",
                "data": {
                    "success": true
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, or the local file is not found (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error), or the photo
              upload answered without id (details.response; the cover is not changed).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, page_token=page_token, image_path_or_url=image_path_or_url):
            return invalid

        # 1. Téléverser l'image comme photo de la page, sans story dans le fil (no_story)
        upload = upload_page_image(page_id, page_token, image_path_or_url,
                                   "Échec de l'upload de la photo de couverture.")
        if upload["status"] == "error":
            return upload
        if not upload["data"].get("id"):  # photo sans id : la couverture ne peut pas être changée
            return error("Échec de l'upload de la photo de couverture.", {"type": "api", "response": upload["data"]})

        # 2. Définir cette photo comme couverture, sans story dans le fil ni notification aux abonnés
        return call_graph(
            "POST", page_id, page_token,
            data={"cover": upload["data"]["id"], "no_feed_story": "true", "no_notification": "true"},
            error_message="Échec de la mise à jour de la photo de couverture.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
