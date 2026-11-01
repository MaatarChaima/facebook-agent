def get_comment_id() -> str:
    """Ask the user for the ID of a comment.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID du commentaire : ").strip()


def get_comment_message() -> str:
    """Ask the user for the text of a comment.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Message : ")
