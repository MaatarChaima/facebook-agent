from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.local_files import missing_file_error


def upload_photo_to_album(album_id: str, file_path: str, page_token: str) -> dict:
    """Add a local photo to an existing album of the page.

    Sends POST /{album_id}/photos with the file: the photo is published in the album.

    Parameters:
        - Input-album_id (str, mandatory): ID of the album.
          Example: "ALBUM_ID_EXAMPLE"
        - Input-file_path (str, mandatory): Path of the local image (URLs are not supported).
          Example: "photos/vitrine.png"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: the id of the photo and the post_id of the post created with it.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "PHOTO_ID_EXAMPLE",
                    "post_id": "PAGE_ID_EXAMPLE_PHOTO_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, or the local file is not found (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception, e.g. a file that cannot be read (details.info).
    """
    try:
        if invalid := check_required(album_id=album_id, file_path=file_path, page_token=page_token):
            return invalid
        if invalid := missing_file_error(file_path):
            return invalid
        with open(file_path, "rb") as image:
            return call_graph(
                "POST", f"{album_id}/photos", page_token,
                files={"source": image},
                error_message="Échec de l'ajout de la photo à l'album.",
                timeout=UPLOAD_TIMEOUT,
            )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
