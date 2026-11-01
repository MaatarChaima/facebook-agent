from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, check_required, error, validation_error
from facebook_agent.local_files import extension, is_url, missing_file_error
from facebook_agent.operations.pages.scheduling import POST_MAX_DELAY, check_publish_window

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif")


def create_scheduled_photos_post(
    page_id: str,
    message: str,
    publish_at: int,
    page_token: str,
    file_paths_or_urls: list[str] | None = None,
) -> dict:
    """Schedule a post on the page, with optional photos.

    Each photo is first uploaded unpublished (POST /{page_id}/photos, published=false), then
    the post is created with published=false, scheduled_publish_time and attached_media
    (POST /{page_id}/feed). Facebook publishes it at publish_at. If a step fails, the photos
    already uploaded stay as unpublished photos of the page.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-message (str, mandatory): Text of the post.
          Example: "Our new collection is coming"
        - Input-publish_at (int, mandatory): Publication date, as a Unix timestamp in seconds, between 10 minutes and
          75 days after now (window documented by Meta).
          Example: int(time.time()) + 24 * 3600 (tomorrow)
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-file_paths_or_urls (list, optional): Photos to attach: existing local files or http(s) URLs
          with the extension .jpg, .jpeg, .png or .gif (checked on the path of a URL, without its
          query string). All files are checked before the first upload.
          Example: ["https://example.com/photo.jpg"]

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: the id of the scheduled post and post_supports_client_mutation_id.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "PAGE_ID_EXAMPLE_POST_ID_EXAMPLE",
                    "post_supports_client_mutation_id": true
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, publish_at is not an integer or is outside the
              window, a file has another extension, or a local file is not found (no request is sent).
            - api: a photo upload or the post creation failed, or a photo upload answered without id.
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception, e.g. a local file that cannot be read (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, message=message, publish_at=publish_at, page_token=page_token):
            return invalid
        # Fenêtre documentée par Meta pour un post : 10 minutes à 75 jours
        if invalid := check_publish_window(publish_at, POST_MAX_DELAY, "75 jours"):
            return invalid
        # Tous les fichiers sont vérifiés avant le premier envoi (aucune photo orpheline sur la page)
        if invalid := _check_files(file_paths_or_urls or []):
            return invalid
        return _create_scheduled_photos_post(page_id, message, publish_at, page_token, file_paths_or_urls)
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})


def _check_files(file_paths_or_urls: list[str]) -> dict | None:
    """Return a validation error for the first unsupported extension or missing local file, else None."""
    for file_path_or_url in file_paths_or_urls:
        ext = extension(file_path_or_url)  # chemin de l'URL, sans les paramètres
        if ext not in IMAGE_EXTENSIONS:
            kind = "URL" if is_url(file_path_or_url) else "fichier"
            return validation_error(f"Format non supporté ({kind}, extension {ext or 'absente'}) : {file_path_or_url}")
        if not is_url(file_path_or_url) and (invalid := missing_file_error(file_path_or_url)):
            return invalid
    return None


def _create_scheduled_photos_post(
    page_id: str, message: str, publish_at: int, page_token: str, file_paths_or_urls: list[str] | None
) -> dict:
    """Upload the photos unpublished, then create the scheduled post (parameters already checked)."""
    media_ids = []

    # Upload des médias si fournis (non publiés, rattachés ensuite au post)
    if file_paths_or_urls:
        for file_path_or_url in file_paths_or_urls:
            if is_url(file_path_or_url):
                # Cas URL publique
                upload = call_graph(
                    "POST", f"{page_id}/photos", page_token,
                    data={"url": file_path_or_url, "published": "false"},
                    error_message="Échec de l'upload d'un média.",
                    timeout=UPLOAD_TIMEOUT,
                )
            else:
                # Cas fichier local (existence et extension déjà vérifiées)
                with open(file_path_or_url, "rb") as media_file:
                    upload = call_graph(
                        "POST", f"{page_id}/photos", page_token,
                        data={"published": "false"},
                        files={"source": media_file},
                        error_message="Échec de l'upload d'un média.",
                        timeout=UPLOAD_TIMEOUT,
                    )

            if upload["status"] == "error":
                return upload
            media_id = upload["data"].get("id")
            if not media_id:
                return error("Échec de l'upload d'un média.", {"type": "api", "response": upload["data"]})
            media_ids.append(media_id)

    # Créer le post programmé
    payload = {
        "message": message,
        "published": "false",
        "scheduled_publish_time": publish_at,
    }
    if media_ids:
        payload["attached_media"] = [{"media_fbid": str(mid)} for mid in media_ids]

    return call_graph(
        "POST", f"{page_id}/feed", page_token,
        json_body=payload,
        error_message="Échec de la création du post programmé.",
    )
