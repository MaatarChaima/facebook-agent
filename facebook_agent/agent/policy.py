"""Which operations need a confirmation, and how they are shown to the user (in French).

Rule: every operation that writes asks for a confirmation (o/n) typed by the user; reading
operations never do. The confirmation is asked by the code, never by the LLM.
"""
IRREVERSIBLE, PUBLIC, MODIFICATION = "IRRÉVERSIBLE", "PUBLIC", "MODIFICATION"
# Bandeau en tête de chaque confirmation des campagnes (agent et menu), selon AD_ACCOUNT_MODE
ADS_BANNERS = {"sandbox": "SANDBOX : aucune diffusion, aucun coût, statut PAUSED",
               "no_payment": "SANS MOYEN DE PAIEMENT : aucun coût, statut PAUSED, aucune publicité possible"}

READ_OPERATIONS = frozenset({
    "get_page_info", "get_post", "get_post_reactions", "list_albums", "list_comments", "list_conversation_messages",
    "list_conversations", "list_photos", "list_posts", "list_product_feeds", "list_product_sets",
    "list_scheduled_posts", "list_videos", "search_products",
    "list_lead_forms", "list_test_leads", "list_form_leads", "list_campaigns", "list_ad_sets", "list_ads",
})

# opération -> (niveau, action affichée, conséquence)
WRITE_OPERATIONS = {
    # --- Irréversible ---------------------------------------------------------------
    "delete_post": (IRREVERSIBLE, "supprimer un post",
                    "le post, ses commentaires et ses réactions seront supprimés définitivement."),
    "delete_comment": (IRREVERSIBLE, "supprimer un commentaire",
                       "le commentaire et ses réponses seront supprimés définitivement."),
    "delete_photo": (IRREVERSIBLE, "supprimer une photo", "la photo sera supprimée définitivement."),
    "delete_video": (IRREVERSIBLE, "supprimer une vidéo", "la vidéo sera supprimée définitivement."),
    "delete_product": (IRREVERSIBLE, "supprimer un produit", "le produit sera retiré du catalogue définitivement."),
    "delete_product_set": (IRREVERSIBLE, "supprimer un product set",
                           "le product set sera supprimé (ses produits restent dans le catalogue)."),
    "delete_product_feed": (IRREVERSIBLE, "supprimer un feed",
                            "le feed sera supprimé ; les produits qu'il a importés peuvent disparaître avec lui."),
    "send_text_message": (IRREVERSIBLE, "envoyer un message Messenger", "le message ne pourra pas être retiré."),
    "send_quick_replies": (IRREVERSIBLE, "envoyer un message Messenger avec des réponses rapides",
                           "le message ne pourra pas être retiré."),
    "send_attachment_from_conversation": (IRREVERSIBLE, "envoyer une pièce jointe Messenger",
                                          "la pièce jointe ne pourra pas être retirée."),
    "mark_conversation_read": (IRREVERSIBLE, "marquer une conversation comme lue",
                               "la personne verra que son message a été lu."),
    "ban_user": (IRREVERSIBLE, "bannir un utilisateur",
                 "la personne ne pourra plus interagir avec la page tant qu'elle n'est pas débannie."),
    "create_and_upload_feed": (IRREVERSIBLE, "créer un feed et importer son fichier",
                               "les produits du fichier seront ajoutés au catalogue."),
    # --- Public -----------------------------------------------------------------------
    "create_post": (PUBLIC, "publier un post", "le post sera visible publiquement ; les abonnés peuvent être notifiés."),
    "update_post": (PUBLIC, "modifier un post", "le nouveau texte sera visible publiquement."),
    "create_scheduled_photos_post": (PUBLIC, "programmer un post",
                                     "le post sera publié automatiquement à la date choisie."),
    "upload_photo": (PUBLIC, "publier une photo", "la photo sera visible publiquement."),
    "upload_photo_to_album": (PUBLIC, "ajouter une photo à un album", "la photo sera visible publiquement."),
    "upload_video": (PUBLIC, "publier ou programmer une vidéo",
                     "la vidéo sera visible publiquement (tout de suite ou à la date choisie)."),
    "update_cover_photo": (PUBLIC, "changer la photo de couverture",
                           "la nouvelle couverture sera visible publiquement ; l'image reste parmi les photos de "
                           "la page, sans publication dans le fil."),
    "update_profile_picture": (PUBLIC, "changer la photo de profil",
                               "la nouvelle photo de profil sera visible publiquement ; un fichier local reste parmi "
                               "les photos de la page, sans publication dans le fil."),
    "create_comment": (PUBLIC, "commenter un post", "le commentaire sera publié au nom de la page."),
    "reply_to_comment": (PUBLIC, "répondre à un commentaire", "la réponse sera publiée au nom de la page."),
    "like_post": (PUBLIC, "aimer un post", "le « j'aime » sera visible au nom de la page."),
    "unlike_post": (PUBLIC, "retirer le « j'aime » d'un post", "le « j'aime » de la page sera retiré."),
    "hide_comment": (PUBLIC, "masquer un commentaire",
                     "le commentaire ne sera plus visible du public (son auteur et ses amis le voient encore)."),
    "unhide_comment": (PUBLIC, "réafficher un commentaire", "le commentaire redeviendra visible publiquement."),
    "unban_user": (PUBLIC, "débannir un utilisateur", "la personne pourra de nouveau interagir avec la page."),
    # --- Modification du catalogue ---------------------------------------------------------
    "create_product": (MODIFICATION, "créer un produit", "le produit sera ajouté au catalogue."),
    "update_product": (MODIFICATION, "modifier un produit",
                       "les champs indiqués (prix compris) seront modifiés dans le catalogue."),
    "create_product_set": (MODIFICATION, "créer un product set", "le product set sera ajouté au catalogue."),
    "update_product_set": (MODIFICATION, "modifier un product set", "le nom ou les produits du set seront modifiés."),
    "reupload_product_feed": (MODIFICATION, "réimporter le fichier d'un feed",
                              "les produits du catalogue seront mis à jour depuis le fichier."),
    # --- Lead Ads -------------------------------------------------------------------------------
    "create_lead_form": (MODIFICATION, "créer un formulaire Lead Ads",
                         "le formulaire sera ajouté à la page ; Meta ne permet pas de le supprimer, seulement de "
                         "l'archiver."),
    "create_test_lead": (MODIFICATION, "créer un lead de test", "un lead fictif sera ajouté au formulaire."),
    "archive_lead_form": (IRREVERSIBLE, "archiver un formulaire Lead Ads",
                          "le formulaire ne recevra plus de leads ; l'agent ne pourra pas le réactiver."),
    "delete_test_lead": (IRREVERSIBLE, "supprimer un lead de test", "le lead de test sera supprimé définitivement."),
    # --- Campagnes (compte sandbox ou sans moyen de paiement : tout reste en PAUSED) ---------------
    "create_campaign": (MODIFICATION, "créer une campagne", "la campagne sera créée en PAUSED, sans diffusion."),
    "update_campaign": (MODIFICATION, "modifier une campagne", "le nom changera et/ou la campagne passera en PAUSED."),
    "delete_campaign": (IRREVERSIBLE, "supprimer une campagne",
                        "la campagne, ses ensembles et ses publicités seront supprimés."),
    "create_ad_set": (MODIFICATION, "créer un ensemble de publicités",
                      "l'ensemble sera créé en PAUSED, au budget minimal du compte."),
    "update_ad_set": (MODIFICATION, "modifier un ensemble de publicités",
                      "le nom ou les pays changeront et/ou l'ensemble passera en PAUSED."),
    "delete_ad_set": (IRREVERSIBLE, "supprimer un ensemble de publicités",
                      "l'ensemble et ses publicités seront supprimés."),
    "create_ad": (MODIFICATION, "créer une publicité", "la publicité sera créée en PAUSED, sans diffusion."),
    "update_ad": (MODIFICATION, "modifier une publicité", "le nom changera et/ou la publicité passera en PAUSED."),
    "delete_ad": (IRREVERSIBLE, "supprimer une publicité", "la publicité sera supprimée."),
}

# Écriture réussie -> phrase du résumé généré par le code (réponse de secours après une action)
DONE_LABELS = {
    "create_post": "Post publié", "update_post": "Post modifié", "delete_post": "Post supprimé",
    "create_scheduled_photos_post": "Post programmé", "like_post": "Post aimé", "unlike_post": "« J'aime » retiré",
    "create_comment": "Commentaire publié", "reply_to_comment": "Réponse publiée", "delete_comment": "Commentaire supprimé",
    "hide_comment": "Commentaire masqué", "unhide_comment": "Commentaire réaffiché", "upload_photo": "Photo publiée",
    "upload_photo_to_album": "Photo ajoutée à l'album", "delete_photo": "Photo supprimée",
    "update_cover_photo": "Couverture changée", "update_profile_picture": "Photo de profil changée",
    "upload_video": "Vidéo publiée ou programmée",
    "delete_video": "Vidéo supprimée", "send_text_message": "Message envoyé", "send_quick_replies": "Message envoyé",
    "send_attachment_from_conversation": "Pièce jointe envoyée", "mark_conversation_read": "Conversation marquée comme lue",
    "ban_user": "Utilisateur banni", "unban_user": "Utilisateur débanni", "create_product": "Produit créé",
    "update_product": "Produit modifié", "delete_product": "Produit supprimé", "create_product_set": "Product set créé",
    "update_product_set": "Product set modifié", "delete_product_set": "Product set supprimé",
    "create_and_upload_feed": "Feed créé et importé", "reupload_product_feed": "Feed réimporté",
    "delete_product_feed": "Feed supprimé",
    "create_lead_form": "Formulaire Lead Ads créé", "create_test_lead": "Lead de test créé",
    "archive_lead_form": "Formulaire Lead Ads archivé", "delete_test_lead": "Lead de test supprimé",
    "create_campaign": "Campagne créée (PAUSED)", "update_campaign": "Campagne modifiée",
    "delete_campaign": "Campagne supprimée", "create_ad_set": "Ensemble de publicités créé (PAUSED)",
    "update_ad_set": "Ensemble de publicités modifié", "delete_ad_set": "Ensemble de publicités supprimé",
    "create_ad": "Publicité créée (PAUSED)", "update_ad": "Publicité modifiée", "delete_ad": "Publicité supprimée",
}

# Suppression ou archivage d'un objet relu déjà dans cet état -> (statuts, phrase) : ni confirmation ni envoi
ALREADY_DONE = {
    "delete_campaign": (("DELETED",), "Cette campagne est déjà supprimée."),
    "delete_ad_set": (("DELETED",), "Cet ensemble de publicités est déjà supprimé."),
    "delete_ad": (("DELETED",), "Cette publicité est déjà supprimée."),
    "archive_lead_form": (("ARCHIVED", "DELETED"), "Ce formulaire est déjà archivé."),
}

# Suppression -> (paramètre de l'ID, champs lus avant de demander la confirmation)
PREVIEW_FIELDS = {
    "delete_post": ("post_id", "message,story,full_picture,created_time"),
    "delete_comment": ("comment_id", "message,from,created_time"),
    "delete_photo": ("photo_id", "name,created_time"),
    "delete_video": ("video_id", "title,description,created_time"),
    "delete_product": ("product_id", "name,retailer_id,price"),
    "delete_product_set": ("product_set_id", "name"),
    "delete_product_feed": ("feed_id", "name"),
    "archive_lead_form": ("form_id", "name,status,leads_count"),
    "delete_test_lead": ("lead_id", "created_time"),  # jamais field_data (données personnelles)
    "delete_campaign": ("campaign_id", "name,status,objective"),
    "delete_ad_set": ("ad_set_id", "name,status"),
    "delete_ad": ("ad_id", "name,status"),
}
# Champ relu avant une suppression montré sous un nom en clair (« Auteur : <nom> » au lieu de son objet JSON)
PREVIEW_LABELS = {"from": "Auteur"}


def preview_value(value) -> str:
    """Readable value of a field read before a deletion: a person or an object by its name, never its ID.

    Args:
        value: Value read on Facebook ({"name": "…", "id": "…"} for the author of a comment).

    Returns:
        The name of an object, its other fields as « key : value » without the IDs, or the value as text.
    """
    if isinstance(value, dict):
        if isinstance(value.get("name"), str) and value["name"].strip():
            return value["name"].strip()
        return " · ".join(f"{key} : {preview_value(item)}" for key, item in value.items() if key != "id")
    if isinstance(value, list):
        return ", ".join(preview_value(item) for item in value)
    return str(value)


def preview_line(key: str, value) -> str:
    """Line of the confirmation text for a field read before a deletion.

    Args:
        key: Field name ("from", "status"…).
        value: Its value.

    Returns:
        « Auteur : Stage D'été » for a labelled field, else « Actuellement, status : PAUSED ».
    """
    label = PREVIEW_LABELS.get(key)
    return f"{label} : {preview_value(value)}" if label else f"Actuellement, {key} : {preview_value(value)}"


def argument_value(value) -> str:
    """Readable value of an argument of a write: an object as « key : value » pairs, a list item by item.

    Unlike preview_value, nothing is dropped: the user confirms exactly what is sent.

    Args:
        value: Argument sent ({"sale_price": "10,00"}, a list of questions…).

    Returns:
        « sale_price : 10,00 · currency : TND », « (type : EMAIL), (type : FULL_NAME) » or the value as text.
    """
    if isinstance(value, dict):
        return " · ".join(f"{key} : {argument_value(item)}" for key, item in value.items())
    if isinstance(value, list):
        return ", ".join(f"({argument_value(item)})" if isinstance(item, dict) else argument_value(item)
                         for item in value)
    return str(value)


def needs_confirmation(name: str) -> bool:
    """Tell whether an operation writes and must be confirmed.

    Args:
        name: Operation name.

    Returns:
        True for every operation that is not a known read; an unknown name is treated as a write.
    """
    return name not in READ_OPERATIONS


def describe(name: str) -> tuple[str, str, str]:
    """Return (level, action, consequence) shown before an operation.

    Args:
        name: Operation name.

    Returns:
        The entry of WRITE_OPERATIONS, or a generic IRRÉVERSIBLE description for an unknown write.
    """
    return WRITE_OPERATIONS.get(name, (IRREVERSIBLE, f"exécuter {name}", "conséquences inconnues."))
