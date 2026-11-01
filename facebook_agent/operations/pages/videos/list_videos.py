from facebook_agent.graph import check_required, error, fetch_list

# picture (miniature) sert aux cartes de l'interface web (retiré pour le modèle). Depuis la v2.5, le titre est
# « title » : demander « name » renvoie l'erreur (#12) « name is deprecated for versions v2.5 and higher ». La
# référence Video de Meta ne documente pas de lien vers la vidéo : aucun n'est demandé.
VIDEO_FIELDS = "id,title,description,created_time,updated_time,picture"


def list_videos(page_id: str, page_token: str, all_pages: bool = False, limit: int | None = None) -> dict:
    """List the videos of the page.

    Parameters:
        - Input-page_id (str, mandatory): ID of the page.
          Example: "PAGE_ID_EXAMPLE"
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 3

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of videos (id, title,
            description, created_time, updated_time, picture = URL of the thumbnail), and "paging" holds the
            cursors (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "ID_EXAMPLE_16",
                            "description": "Example description",
                            "created_time": "2025-07-09T00:23:06+0000",
                            "updated_time": "2025-07-10T23:24:33+0000",
                            "picture": "https://example.com/media.jpg"
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
            - validation: a mandatory parameter is empty or limit is not an integer from 1 to 100 (no request is sent).
            - api: the Graph API returned an error (details.status_code, details.error).
            - timeout, network, invalid_response: the API did not answer in time, could not be
              reached, or did not return JSON.
            - unexpected: any other exception (details.info).
    """
    try:
        if invalid := check_required(page_id=page_id, page_token=page_token):
            return invalid
        return fetch_list(f"{page_id}/videos", page_token, all_pages=all_pages, limit=limit,
                          params={"fields": VIDEO_FIELDS}, error_message="Échec de la récupération des vidéos.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
