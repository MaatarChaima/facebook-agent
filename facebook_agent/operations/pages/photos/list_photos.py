from facebook_agent.graph import check_required, error, fetch_list, validation_error

PHOTO_TYPES = ("uploaded", "tagged", "profile")
# link et images servent aux miniatures de l'interface web (retirés pour le modèle)
PHOTO_FIELDS = "id,name,created_time,link,images"


def list_photos(page_id: str, page_token: str, photo_type: str = "uploaded", all_pages: bool = False,
        limit: int | None = None) -> dict:
    """List the photos of the page.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-photo_type (str, optional): Which photos to list (sent as the "type" parameter).
          Choices:
              - uploaded -> photos uploaded by the page (default of this function)
              - tagged -> photos in which the page is tagged
              - profile -> profile pictures (default of the Graph API when type is absent)
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 3

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of photos (id, name = caption when
            there is one, created_time, link to the photo on Facebook, images = the stored sizes with height,
            width and source), and "paging" holds the cursors (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "ID_EXAMPLE_6",
                            "name": "Example name",
                            "created_time": "2026-10-31T09:57:27+0000",
                            "link": "https://www.facebook.com/EXAMPLE_LINK",
                            "images": [
                                {
                                    "height": 1200,
                                    "source": "https://example.com/media.jpg",
                                    "width": 1200
                                }
                            ]
                        }
                    ],
                    "paging": {
                        "cursors": {
                            "before": "CURSOR_BEFORE_EXAMPLE",
                            "after": "CURSOR_AFTER_EXAMPLE"
                        }
                    }
                }
            }
        Errors:
            - validation: a mandatory parameter is empty or limit is not an integer from 1 to 100, or photo_type is not one of the choices (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, page_token=page_token):
            return invalid
        # Sans "type", l'API renvoie les photos de profil (valeur par défaut documentée : profile).
        if photo_type not in PHOTO_TYPES:
            return validation_error(f"photo_type doit valoir {', '.join(PHOTO_TYPES)} (reçu : {photo_type!r}).")
        return fetch_list(
            f"{page_id}/photos", page_token, all_pages=all_pages, limit=limit,
            params={"type": photo_type, "fields": PHOTO_FIELDS},
            error_message="Échec de la récupération des photos.",
        )
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
