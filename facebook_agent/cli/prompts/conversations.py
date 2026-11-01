import json


def get_conversation_id() -> str:
    """Ask the user for the ID of a conversation.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("ID de la conversation : ").strip()


def get_text() -> str:
    """Ask the user for the text of a message.

    Returns:
        The text typed by the user, without surrounding spaces.
    """
    return input("Texte du message : ").strip()


def get_file_path() -> str:
    """Ask the user for the path or URL of a file.

    Returns:
        The text typed by the user, as typed.
    """
    return input("Chemin du fichier (local ou URL) : ")


def get_options() -> list[str | dict]:
    """Ask the quick-reply options, separated by commas.

    An option written as JSON ({"title": ..., "payload": ...}) becomes a dict; an invalid
    JSON option is ignored with a message.

    Returns:
        The list of options (strings or dicts).
    """
    print("Saisir les options de quick replies (séparées par une virgule).")
    print('Exemple : Oui, Non, {"title": "Plus tard", "payload": "LATER"}')
    opts = input("Options : ")

    # Transformation en liste
    options = []
    for opt in opts.split(","):
        opt = opt.strip()
        if opt.startswith("{") and opt.endswith("}"):
            try:
                options.append(json.loads(opt.replace("'", '"')))
            except json.JSONDecodeError:
                print(f"Option ignorée (format invalide) : {opt}")
        else:
            options.append(opt)
    return options
