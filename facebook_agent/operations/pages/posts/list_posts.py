from facebook_agent.graph import check_required, error, fetch_list

# permalink_url, full_picture et les deux compteurs servent aux cartes de l'interface web (retirés pour le modèle)
POST_LIST_FIELDS = ("id,created_time,message,story,permalink_url,full_picture,"
                    "reactions.summary(total_count).limit(0),comments.summary(total_count).limit(0)")


def list_posts(page_token: str, all_pages: bool = False, limit: int | None = None) -> dict:
    """List the posts of the page feed.

    Sends GET me/feed: with a Page token, "me" is the page itself. Fields: id, created_time, message,
    story, permalink_url, full_picture, and the total counts of reactions and comments.

    Parameters:
        - Input-page_token (str, mandatory): Page access token of the page (see authenticate).
        - Input-all_pages (bool, optional): False (default) returns the first page as sent by the API ("data" and "paging");
          True follows paging.next and returns every item in "data" (at most 50 pages,
          with "truncated": true when this limit is reached).
        - Input-limit (int, optional): Maximum number of items per page (Graph API limit parameter),
          from 1 to 100. Default: None (the default of the API, often 25).
          Example: 3

    Returns:
        dict: {"status": "success", "data": ...} or {"status": "error", "message": ..., "details": {...}}
        Output type: dict, the raw Graph API answer: "data" is the list of posts (id, created_time, message or
            story, permalink_url, full_picture when the post has a picture, reactions.summary.total_count,
            comments.summary.total_count), and "paging" holds the cursors (absent when all_pages=True).
        Example (success):
            {
                "status": "success",
                "data": {
                    "data": [
                        {
                            "id": "PAGE_ID_EXAMPLE_ID_EXAMPLE_1",
                            "created_time": "2026-10-31T10:00:19+0000",
                            "message": "Example message",
                            "permalink_url": "https://www.facebook.com/EXAMPLE_LINK",
                            "reactions": {
                                "data": [],
                                "summary": {
                                    "total_count": 0
                                }
                            },
                            "comments": {
                                "data": [],
                                "summary": {
                                    "total_count": 1
                                }
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
        if invalid := check_required(page_token=page_token):
            return invalid
        return fetch_list("me/feed", page_token, all_pages=all_pages, limit=limit,
                          params={"fields": POST_LIST_FIELDS}, error_message="Échec de la récupération des posts.")
    except Exception as e:
        return error("Une erreur inattendue est survenue", {"type": "unexpected", "info": str(e)})
