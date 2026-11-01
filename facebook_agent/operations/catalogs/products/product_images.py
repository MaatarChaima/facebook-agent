"""Shared helpers for product images (not an operation itself)."""
from facebook_agent.config import UPLOAD_TIMEOUT
from facebook_agent.graph import call_graph, validation_error
from facebook_agent.local_files import is_url

LOCAL_IMAGE_HELP = ("Une image locale nécessite page_id et page_token : elle est d'abord publiée (non visible) "
                    "sur la page, puis référencée par son URL. Une URL d'image fonctionne sans eux.")


def is_local_image(value: str | None) -> bool:
    """Tell whether an image is a local file path.

    Args:
        value: Image value of the product data.

    Returns:
        True if it is not empty, not an http(s) URL and not the "-" deletion marker.
    """
    return bool(value) and not is_url(str(value)) and value != "-"


def missing_page_credentials(page_id: str | None, page_token: str | None) -> dict | None:
    """Check that page_id and page_token are given for a local image.

    Args:
        page_id: ID of the page that hosts the image.
        page_token: Page access token.

    Returns:
        None if both are given, otherwise a validation error.
    """
    missing = [name for name, value in (("page_id", page_id), ("page_token", page_token))
               if not value or not str(value).strip()]
    if missing:
        return validation_error([f"Le paramètre {name} est obligatoire pour une image locale." for name in missing],
                                message=LOCAL_IMAGE_HELP)
    return None


def upload_local_image(file_path: str, page_id: str, page_token: str,
                       error_message: str) -> tuple[str | None, dict | None]:
    """Upload a local image as an unpublished photo of the page and return its public URL.

    Sends POST /{page_id}/photos (published=false), then GET /{photo_id}?fields=images,
    both with the page token.

    Args:
        file_path: Path of the local image.
        page_id: ID of the page that hosts the image.
        page_token: Page access token.
        error_message: Message of the error result.

    Returns:
        (public_image_url, None) or (None, error_result).
    """
    with open(file_path, "rb") as image:
        upload = call_graph(
            "POST", f"{page_id}/photos", page_token,
            data={"published": "false"},  # pour ne pas la publier sur la page
            files={"source": image},
            error_message=error_message,
            timeout=UPLOAD_TIMEOUT,
        )
    if upload["status"] == "error":
        return None, upload

    info = call_graph(
        "GET", upload["data"]["id"], page_token,
        params={"fields": "images"},
        error_message=error_message,
    )
    if info["status"] == "error":
        return None, info
    return info["data"]["images"][0]["source"], None
