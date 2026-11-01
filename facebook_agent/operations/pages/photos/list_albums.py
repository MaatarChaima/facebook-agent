from facebook_agent.graph import check_required, error, fetch_list

# count, link et cover_photo servent aux cartes de l'interface web (link et cover_photo retirés pour le modèle).
# cover_photo est de type Photo dans la référence Album : ses images (champ « images » de Photo) donnent la
# miniature de l'album.
ALBUM_FIELDS = "id,name,count,created_time,link,cover_photo{images}"


def list_albums(page_id: str, page_token: str, all_pages: bool = False, limit: int | None = None) -> dict:
    """List the photo albums of the page.

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
        Output type: dict, the raw Graph API answer: "data" is the list of albums (id, name, count = approximate
            number of photos, created_time, link to the album on Facebook, cover_photo = the cover photo with its
            stored sizes in "images", absent when the album has none), and "paging" holds the cursors
            (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "ID_EXAMPLE_12",
                            "name": "Example name",
                            "count": 8,
                            "created_time": "2025-07-05T22:41:28+0000",
                            "link": "https://www.facebook.com/EXAMPLE_LINK",
                            "cover_photo": {
                                "images": [
                                    {
                                        "height": 1200,
                                        "source": "https://example.com/media.jpg",
                                        "width": 1200
                                    }
                                ],
                                "id": "ID_EXAMPLE_6"
                            }
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
        return fetch_list(f"{page_id}/albums", page_token, all_pages=all_pages, limit=limit,
                          params={"fields": ALBUM_FIELDS}, error_message="Échec de la récupération des albums.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
