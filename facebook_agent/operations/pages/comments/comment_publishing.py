"""Shared helper for publishing comments and replies (not an operation itself)."""
from facebook_agent.graph import call_graph, error


def publish_comment(object_id: str, message: str, page_token: str, error_message: str) -> dict:
    """Publish a comment on a post, or a reply on a comment (POST /{object-id}/comments).

    Args:
        object_id: ID of the post (comment) or of the comment (reply).
        message: Text of the comment.
        page_token: Page access token.
        error_message: Message of the error result.

    Returns:
        A standard result whose data is {"id": "<new comment id>"}, or an error result
        (type "api" when the API answers without an id).
    """
    result = call_graph("POST", f"{object_id}/comments", page_token, data={"message": message},
                        error_message=error_message)
    if result["status"] == "error":
        return result
    if not result["data"].get("id"):
        return error(error_message, {"type": "api", "response": result["data"]})
    return result
