"""Shared helper of update_cover_photo and update_profile_picture (not an operation itself)."""
from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph
from facebook_agent.local_files import is_url, missing_file_error

# Photo téléversée pour servir d'image à la page : publiée (Meta ne documente pas de couverture ni de photo de
# profil faite d'une photo non publiée, supprimée après environ 24 h), mais sans story dans le fil (no_story)
UPLOAD_FLAGS = {"published": "true", "no_story": "true"}


def upload_page_image(page_id: str, page_token: str, image_path_or_url: str, error_message: str) -> dict:
    """Upload an image as a photo of the page, without any story in the feed.

    Sends POST /{page_id}/photos with published=true and no_story=true: url for an http(s) URL, the file
    as multipart for a local path.

    Args:
        page_id: ID of the page.
        page_token: Page access token.
        image_path_or_url: http(s) URL, or path of an existing local image.
        error_message: Message of the error result in French.

    Returns:
        The result of call_graph ({"id": ...} on success), or a validation error for a missing local file.
    """
    if is_url(image_path_or_url):
        return call_graph("POST", f"{page_id}/photos", page_token, data={"url": image_path_or_url, **UPLOAD_FLAGS},
                          error_message=error_message, timeout=UPLOAD_TIMEOUT)
    if invalid := missing_file_error(image_path_or_url):  # un chemin inexistant n'est jamais envoyé comme URL
        return invalid
    with open(image_path_or_url, "rb") as image:
        return call_graph("POST", f"{page_id}/photos", page_token, data=dict(UPLOAD_FLAGS), files={"source": image},
                          error_message=error_message, timeout=UPLOAD_TIMEOUT)
