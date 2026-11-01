from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, check_required, error
from facebook_agent.local_files import is_url, missing_file_error
from facebook_agent.operations.pages.scheduling import VIDEO_MAX_DELAY, check_publish_window


def upload_video(
    page_id: str,
    video_source: str,
    page_token: str,
    title: str = "",
    description: str = "",
    publish_at: int | None = None,
) -> dict:
    """Publish or schedule a video on the page.

    Sends POST /{page_id}/videos.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-video_source (str, mandatory): Path of an existing local video (uploaded as multipart), or URL of a hosted video
          (sent as file_url). A value that is not an http(s) URL must be an existing file.
          Example: "https://example.com/video.mp4"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-title (str, optional): Title of the video (default: none).
          Example: "Behind the scenes"
        - Input-description (str, optional): Description of the video (default: none).
        - Input-publish_at (int, optional): Publication date, as a Unix timestamp in seconds, between 10 minutes and 6 months
          (180 days) after now. When given, the video is uploaded unpublished and Facebook
          publishes it at that date. Default: None (published immediately).
          Example: int(time.time()) + 24 * 3600 (tomorrow)

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: {"id": "<video id>"}. The scheduled variant
            (publish_at) returns the same structure.
        Example (success):
            {
                "status": "success",
                "data": {
                    "id": "VIDEO_ID_EXAMPLE"
                }
            }
        Errors:
            - validation: a mandatory parameter is empty, publish_at is not an integer or is outside
              the window, or the local file is not found (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, video_source=video_source, page_token=page_token):
            return invalid
        # Vidéo programmée : fenêtre documentée par Meta de 10 minutes à 6 mois
        if publish_at is not None and (invalid := check_publish_window(publish_at, VIDEO_MAX_DELAY, "6 mois")):
            return invalid
        # Un chemin qui n'est pas une URL http(s) doit être un fichier existant
        if not is_url(video_source) and (invalid := missing_file_error(video_source)):
            return invalid

        path = f"{page_id}/videos"
        data = {"title": title, "description": description}
        if publish_at is not None:
            data.update({"published": "false", "scheduled_publish_time": publish_at})
        error_message = "Échec de la publication de la vidéo."

        # Cas 1 : URL hébergée
        if is_url(video_source):
            return call_graph(
                "POST", path, page_token,
                data={"file_url": video_source, **data},
                error_message=error_message,
                timeout=UPLOAD_TIMEOUT,
            )

        # Cas 2 : fichier local (existence déjà vérifiée)
        with open(video_source, "rb") as video_file:
            return call_graph(
                "POST", path, page_token,
                data=data,
                files={"source": video_file},
                error_message=error_message,
                timeout=UPLOAD_TIMEOUT,
            )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
