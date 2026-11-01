from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.local_files import is_url
from facebook_agent.operations.pages.photos.page_images import upload_page_image

PROFILE_ERROR = "Échec de la mise à jour de la photo de profil."


def update_profile_picture(page_id: str, page_token: str, image_path_or_url: str) -> dict:
    """Replace the profile picture of the page by an image given by its URL or as a local file.

    An http(s) URL is sent directly: POST /{page_id}/picture with picture=<URL>. A local file is first
    uploaded as a photo of the page with no_story=true (POST /{page_id}/photos, multipart), then used with
    photo=<ID of the photo> (POST /{page_id}/picture). suppress_stories=true is always sent, so that no
    story is created in the feed. The person who gets the page token must be able to do the MANAGE task on
    the page.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of a person who can do the MANAGE task on the page.
        - Input-image_path_or_url (str, mandatory): http(s) URL of a hosted image, or path of a local image (uploaded first
          as a photo of the page). A value that is not an http(s) URL must be an existing file.
          Example: "https://example.com/logo.png"

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
              upload answered without id (details.response; the profile picture is not changed).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, page_token=page_token, image_path_or_url=image_path_or_url):
            return invalid

        if is_url(image_path_or_url):  # image hébergée : envoyée directement
            return call_graph("POST", f"{page_id}/picture", page_token,
                              data={"picture": image_path_or_url, "suppress_stories": "true"},
                              error_message=PROFILE_ERROR)

        # Fichier local : téléversé d'abord comme photo de la page (sans story), puis utilisé par son ID
        upload = upload_page_image(page_id, page_token, image_path_or_url,
                                   "Échec de l'upload de la photo de profil.")
        if upload["status"] == "error":
            return upload
        if not upload["data"].get("id"):  # photo sans id : la photo de profil ne peut pas être changée
            return error("Échec de l'upload de la photo de profil.", {"type": "api", "response": upload["data"]})
        return call_graph("POST", f"{page_id}/picture", page_token,
                          data={"photo": upload["data"]["id"], "suppress_stories": "true"},
                          error_message=PROFILE_ERROR)
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
