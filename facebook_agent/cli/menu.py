"""Interactive command-line menu to test each Facebook operation manually.

Run from the project root with: python -m facebook_agent
"""
import json

from facebook_agent import config
from facebook_agent.ads_safety import mode_problem
from facebook_agent.auth.authentication import authenticate
from facebook_agent.cli.prompts import InvalidInputError
from facebook_agent.cli.prompts.ads import (
    get_ad_creative,
    get_countries,
    get_name,
    get_new_name,
    get_object_id,
    get_objective,
    get_pause,
)
from facebook_agent.cli.prompts.auth import get_auth_choice
from facebook_agent.cli.prompts.comments import get_comment_id, get_comment_message
from facebook_agent.cli.prompts.conversations import (
    get_conversation_id,
    get_file_path,
    get_options,
    get_text,
)
from facebook_agent.cli.prompts.leads import (
    confirm_lead_action,
    get_lead_form_id,
    get_lead_form_name,
    get_lead_id,
    get_lead_questions,
    get_optional_text,
    get_privacy_policy_url,
    get_test_lead_answers,
)
from facebook_agent.cli.prompts.pages import select_page
from facebook_agent.cli.prompts.photos import (
    get_album_id,
    get_photo_caption,
    get_photo_file_path,
    get_photo_id,
    get_photo_url,
)
from facebook_agent.cli.prompts.posts import (
    get_file_paths_or_urls,
    get_message,
    get_new_message,
    get_post_id,
    get_post_message,
    get_publish_at,
)
from facebook_agent.cli.prompts.product_feeds import (
    get_feed_id,
    get_feed_name,
    get_feed_url,
    get_new_feed_url,
)
from facebook_agent.cli.prompts.product_sets import (
    get_new_set_name,
    get_product_set_id,
    get_retailer_ids,
    get_retailer_ids_to_add,
    get_retailer_ids_to_remove,
    get_set_name,
)
from facebook_agent.cli.prompts.products import (
    get_create_product_data,
    get_name_partial_match,
    get_product_id,
    get_update_data,
)
from facebook_agent.cli.prompts.users import get_user_id
from facebook_agent.cli.prompts.videos import (
    get_video_description,
    get_video_id,
    get_video_title,
    get_video_url,
)
from facebook_agent.operations.catalogs.product_feeds.create_and_upload_feed import create_and_upload_feed
from facebook_agent.operations.catalogs.product_feeds.delete_product_feed import delete_product_feed
from facebook_agent.operations.catalogs.product_feeds.list_product_feeds import list_product_feeds
from facebook_agent.operations.catalogs.product_feeds.reupload_product_feed import reupload_product_feed
from facebook_agent.operations.catalogs.product_sets.create_product_set import create_product_set
from facebook_agent.operations.catalogs.product_sets.delete_product_set import delete_product_set
from facebook_agent.operations.catalogs.product_sets.list_product_sets import list_product_sets
from facebook_agent.operations.catalogs.product_sets.update_product_set import update_product_set
from facebook_agent.operations.catalogs.products.create_product import create_product
from facebook_agent.operations.catalogs.products.delete_product import delete_product
from facebook_agent.operations.catalogs.products.search_products import search_products
from facebook_agent.operations.catalogs.products.update_product import update_product
from facebook_agent.operations.pages.comments.create_comment import create_comment
from facebook_agent.operations.pages.comments.delete_comment import delete_comment
from facebook_agent.operations.pages.comments.hide_comment import hide_comment
from facebook_agent.operations.pages.comments.list_comments import list_comments
from facebook_agent.operations.pages.comments.reply_to_comment import reply_to_comment
from facebook_agent.operations.pages.conversations.list_conversation_messages import list_conversation_messages
from facebook_agent.operations.pages.conversations.list_conversations import list_conversations
from facebook_agent.operations.pages.comments.unhide_comment import unhide_comment
from facebook_agent.operations.pages.conversations.mark_conversation_read import mark_conversation_read
from facebook_agent.operations.pages.conversations.send_attachment_from_conversation import (
    send_attachment_from_conversation,
)
from facebook_agent.operations.pages.conversations.send_quick_replies import send_quick_replies
from facebook_agent.operations.pages.conversations.send_text_message import send_text_message
from facebook_agent.agent import policy
from facebook_agent.agent.tools import AD_OPERATIONS
from facebook_agent.graph import call_graph
from facebook_agent.operations.ads.ad_sets.create_ad_set import create_ad_set
from facebook_agent.operations.ads.ad_sets.delete_ad_set import delete_ad_set
from facebook_agent.operations.ads.ad_sets.list_ad_sets import list_ad_sets
from facebook_agent.operations.ads.ad_sets.update_ad_set import update_ad_set
from facebook_agent.operations.ads.ads.create_ad import create_ad
from facebook_agent.operations.ads.ads.delete_ad import delete_ad
from facebook_agent.operations.ads.ads.list_ads import list_ads
from facebook_agent.operations.ads.ads.update_ad import update_ad
from facebook_agent.operations.ads.campaigns.create_campaign import create_campaign
from facebook_agent.operations.ads.campaigns.delete_campaign import delete_campaign
from facebook_agent.operations.ads.campaigns.list_campaigns import list_campaigns
from facebook_agent.operations.ads.campaigns.update_campaign import update_campaign
from facebook_agent.lead_safety import protected_form_problem
from facebook_agent.operations.pages.leads.archive_lead_form import archive_lead_form
from facebook_agent.operations.pages.leads.create_lead_form import create_lead_form
from facebook_agent.operations.pages.leads.create_test_lead import create_test_lead
from facebook_agent.operations.pages.leads.delete_test_lead import delete_test_lead
from facebook_agent.operations.pages.leads.list_form_leads import list_form_leads
from facebook_agent.operations.pages.leads.list_lead_forms import list_lead_forms
from facebook_agent.operations.pages.leads.list_test_leads import list_test_leads
from facebook_agent.operations.pages.page_info.get_page_info import get_page_info
from facebook_agent.operations.pages.photos.delete_photo import delete_photo
from facebook_agent.operations.pages.photos.list_albums import list_albums
from facebook_agent.operations.pages.photos.list_photos import list_photos
from facebook_agent.operations.pages.photos.update_cover_photo import update_cover_photo
from facebook_agent.operations.pages.photos.update_profile_picture import update_profile_picture
from facebook_agent.operations.pages.photos.upload_photo import upload_photo
from facebook_agent.operations.pages.photos.upload_photo_to_album import upload_photo_to_album
from facebook_agent.operations.pages.posts.create_post import create_post
from facebook_agent.operations.pages.posts.create_scheduled_photos_post import create_scheduled_photos_post
from facebook_agent.operations.pages.posts.delete_post import delete_post
from facebook_agent.operations.pages.posts.get_post import get_post
from facebook_agent.operations.pages.posts.get_post_reactions import get_post_reactions
from facebook_agent.operations.pages.posts.like_post import like_post
from facebook_agent.operations.pages.posts.list_posts import list_posts
from facebook_agent.operations.pages.posts.list_scheduled_posts import list_scheduled_posts
from facebook_agent.operations.pages.posts.unlike_post import unlike_post
from facebook_agent.operations.pages.posts.update_post import update_post
from facebook_agent.operations.pages.users.ban_user import ban_user
from facebook_agent.operations.pages.users.unban_user import unban_user
from facebook_agent.operations.pages.videos.delete_video import delete_video
from facebook_agent.operations.pages.videos.list_videos import list_videos
from facebook_agent.operations.pages.videos.upload_video import upload_video


def _update_product(access_token: str, page_id: str, page_token: str) -> dict:
    """Ask the product and its new fields, then call update_product."""
    product_id = get_product_id()
    data = get_update_data(product_id, access_token)
    notice = "Traitement du catalogue en cours… (retrait de la promotion, jusqu'à 30 s)" \
        if data.get("sale_price") == "-" else None
    # page_id / page_token servent seulement si la nouvelle image est un fichier local ;
    # catalog_id, seulement pour retirer la promotion (sale_price "-", Catalog Batch API).
    return _confirmed("update_product", update_product, notice=notice, product_id=product_id,
                      access_token=access_token, data=data,
                      page_id=page_id, page_token=page_token, catalog_id=config.CATALOG_ID)


def _update_product_set(access_token: str) -> dict:
    """Ask the product set and the changes, then call update_product_set."""
    product_set_id = get_product_set_id()
    name = get_new_set_name()
    return _confirmed("update_product_set", update_product_set, product_set_id=product_set_id,
                      access_token=access_token, name=name if name else None,
                      add_product_ids=get_retailer_ids_to_add(), remove_product_ids=get_retailer_ids_to_remove())


CANCELLED = {"status": "cancelled", "message": "Action annulée : rien n'a été envoyé à Facebook."}
HIDDEN_ARGUMENTS = ("token", "secret")  # jamais affichés dans une confirmation
PREVIEW_MAX = 200


def _shown(value) -> str:
    """Readable value of an argument or of a field read, long texts shortened."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= PREVIEW_MAX else text[:PREVIEW_MAX] + "…"


def _already_done(operation: str, fields: dict) -> dict | None:
    """Result for an object already deleted (or a form already archived), as the agent does; else None.

    Args:
        operation: Name of the deletion or archiving.
        fields: Fields of the object read before it.

    Returns:
        {"status": "refused", "message": "Cette campagne est déjà supprimée."}, or None.
    """
    statuses, sentence = policy.ALREADY_DONE.get(operation, ((), ""))
    if str(fields.get("status", "")).upper() in statuses:
        return {"status": "refused", "message": sentence}
    return None


def _confirmed(operation: str, func, /, notice: str | None = None, **arguments) -> dict:
    """Describe a write (action, arguments, consequence), read the object before a deletion, then ask o/n.

    The same descriptions and levels as the agent (agent/policy.py): IRRÉVERSIBLE, PUBLIC or
    MODIFICATION. Tokens are never shown. The first two parameters are positional only, so that an
    argument of the operation may be called "name" (create_campaign, create_ad...).

    Args:
        operation: Name of the operation.
        func: The operation, called with the arguments only after "o".
        notice: Message shown after "o", just before the call (e.g. a wait of the catalog).
        **arguments: Its arguments (already typed by the user).

    Returns:
        The result of the operation, the error of the reading of the object to delete, or CANCELLED.
    """
    level, action, consequence = policy.describe(operation)
    lines = [f"Action demandée : {action} ({operation})"]
    if operation in AD_OPERATIONS:  # campagnes : le mode du compte, avant tout le reste (comme l'agent)
        lines.insert(0, policy.ADS_BANNERS.get(config.AD_ACCOUNT_MODE, policy.ADS_BANNERS["sandbox"]))
    # un objet ou une liste en clair, jamais en JSON brut (comme l'agent)
    lines += [f"  {key} : {_shown(policy.argument_value(value) if isinstance(value, (dict, list)) else value)}"
              for key, value in arguments.items()
              if value not in (None, "", [], {}) and not any(word in key for word in HIDDEN_ARGUMENTS)]
    if operation in policy.PREVIEW_FIELDS:  # suppression : l'objet est relu et montré avant de demander
        id_param, fields = policy.PREVIEW_FIELDS[operation]
        token = arguments.get("page_token") or arguments.get("access_token")
        if arguments.get(id_param):
            read = call_graph("GET", str(arguments[id_param]), token, params={"fields": fields},
                              error_message="Lecture de l'objet à supprimer impossible : suppression non proposée.")
            if read["status"] != "success":
                return read
            if already := _already_done(operation, read["data"]):
                return already  # déjà supprimé : ni confirmation ni envoi
            # « Auteur : <nom> », jamais l'objet JSON d'une personne ni son ID
            lines += [f"  {_shown(policy.preview_line(key, value))}" for key, value in read["data"].items() if key != "id"]
    lines.append(f"{level} : {consequence}")
    if not confirm_lead_action("\n".join(lines)):
        return CANCELLED
    if notice:
        print(notice)
    return func(**arguments)


def _create_lead_form(page_id: str, page_token: str) -> dict:
    """Ask the form, show it, and create it after confirmation (o/n)."""
    name, questions = get_lead_form_name(), get_lead_questions()
    privacy_url = get_privacy_policy_url()
    link_text = get_optional_text("Texte du lien de confidentialité (vide = texte de Facebook) : ")
    follow_up = input("URL du bouton « Voir le site web » (http/https, obligatoire pour Meta) : ").strip()
    locale = get_optional_text("Langue des questions préremplies (vide = fr_FR) : ")
    text = (f"Action demandée : créer le formulaire Lead Ads « {name} » ({len(questions)} question(s), clés "
            f"{', '.join(str(q.get('key')) for q in questions)}).\n"
            "MODIFICATION : le formulaire sera ajouté à la page ; Meta ne permet pas de le supprimer ensuite "
            "(seulement de l'archiver).")
    if not confirm_lead_action(text):
        return CANCELLED
    return create_lead_form(page_id, name, questions, privacy_url, page_token, follow_up_action_url=follow_up,
                            privacy_policy_link_text=link_text, locale=locale)


def _archive_lead_form(page_token: str) -> dict:
    """Read the form (name, status), show it, and archive it after confirmation (o/n)."""
    form_id = get_lead_form_id()
    if not form_id:
        return archive_lead_form(form_id, page_token)  # erreur de validation, aucune requête
    if problem := protected_form_problem("archive_lead_form", {"form_id": form_id}, config.PROTECTED_LEAD_FORM_IDS):
        return {"status": "refused", "message": problem}  # formulaire protégé : rien n'est lu ni envoyé
    read = call_graph("GET", form_id, page_token, params={"fields": "name,status,leads_count"},
                      error_message="Lecture du formulaire impossible.")
    if read["status"] != "success":
        return read
    form = read["data"]
    if already := _already_done("archive_lead_form", form):
        return already  # déjà archivé : ni confirmation ni envoi
    level, _, consequence = policy.describe("archive_lead_form")  # même texte que l'agent
    text = (f"Action demandée : archiver le formulaire Lead Ads « {form.get('name')} » ({form_id}, statut "
            f"{form.get('status')}, {form.get('leads_count', 0)} lead(s)).\n{level} : {consequence}")
    if not confirm_lead_action(text):
        return CANCELLED
    return archive_lead_form(form_id, page_token)


def _create_test_lead(page_token: str) -> dict:
    """Ask the form and fictitious answers, and create the test lead after confirmation (o/n)."""
    form_id, answers = get_lead_form_id(), get_test_lead_answers()
    keys = ", ".join(answer["name"] for answer in answers) if answers else "générées par Facebook"
    text = (f"Action demandée : créer un lead de test sur le formulaire {form_id} (réponses : {keys}).\n"
            "MODIFICATION : un seul lead de test par formulaire ; supprime-le avant d'en créer un autre.")
    if not confirm_lead_action(text):
        return CANCELLED
    return create_test_lead(form_id, page_token, answers)


def _delete_test_lead(page_token: str) -> dict:
    """Delete a test lead after confirmation (o/n)."""
    lead_id = get_lead_id()
    text = (f"Action demandée : supprimer le lead de test {lead_id}.\n"
            "IRRÉVERSIBLE : le lead de test sera supprimé définitivement (jamais le lead d'une vraie personne).")
    if not confirm_lead_action(text):
        return CANCELLED
    return delete_test_lead(lead_id, page_token)


def build_menu() -> dict:
    """Build the menu of the operations, by category.

    Page operations use the page token; catalog operations use the user token
    (FB_USER_TOKEN), because a page token cannot delete a product feed.

    Returns:
        {category: [(label, action(page_id, page_token)), ...]}.
    """
    def catalog_id() -> str:
        return config.require("CATALOG_ID")

    def user() -> str:
        return config.require("FB_USER_TOKEN")

    def account() -> str:
        """AD_ACCOUNT_ID, only with a valid AD_ACCOUNT_MODE (otherwise the Campagnes section is disabled)."""
        problem = mode_problem(config.AD_ACCOUNT_MODE)
        if problem or not config.AD_ACCOUNT_ID:
            raise RuntimeError(f"rubrique Campagnes désactivée : {problem or 'AD_ACCOUNT_ID vide dans le .env'}.")
        return config.AD_ACCOUNT_ID

    def ads_token() -> str:
        return config.ADS_ACCESS_TOKEN or config.require("FB_USER_TOKEN")

    return {
        "Posts": [
            ("Lister les posts", lambda pid, tok: list_posts(tok)),
            ("Créer un post", lambda pid, tok: _confirmed("create_post", create_post, message=get_post_message(),
                                                     page_token=tok)),
            ("Modifier un post", lambda pid, tok: _confirmed("update_post", update_post, post_id=get_post_id(),
                                                         new_message=get_new_message(), page_token=tok)),
            ("Supprimer un post", lambda pid, tok: _confirmed("delete_post", delete_post, post_id=get_post_id(),
                                                          page_token=tok)),
            ("Liker un post", lambda pid, tok: _confirmed("like_post", like_post, post_id=get_post_id(), page_token=tok)),
            ("Retirer le like d'un post", lambda pid, tok: _confirmed("unlike_post", unlike_post, post_id=get_post_id(),
                                                                  page_token=tok)),
            ("Réactions d'un post", lambda pid, tok: get_post_reactions(get_post_id(), tok)),
            ("Lire un post", lambda pid, tok: get_post(get_post_id(), tok)),
            ("Lister les posts programmés", lambda pid, tok: list_scheduled_posts(pid, tok)),
            ("Créer un post photo programmé", lambda pid, tok: _confirmed(
                "create_scheduled_photos_post", create_scheduled_photos_post, page_id=pid, message=get_message(),
                publish_at=get_publish_at(), page_token=tok, file_paths_or_urls=get_file_paths_or_urls())),
        ],
        "Commentaires": [
            ("Lister les commentaires d'un post", lambda pid, tok: list_comments(get_post_id(), tok)),
            ("Créer un commentaire", lambda pid, tok: _confirmed("create_comment", create_comment, post_id=get_post_id(),
                                                             message=get_comment_message(), page_token=tok)),
            ("Répondre à un commentaire",
             lambda pid, tok: _confirmed("reply_to_comment", reply_to_comment, comment_id=get_comment_id(),
                                         message=get_comment_message(), page_token=tok)),
            ("Supprimer un commentaire", lambda pid, tok: _confirmed("delete_comment", delete_comment,
                                                                 comment_id=get_comment_id(), page_token=tok)),
            ("Masquer un commentaire", lambda pid, tok: _confirmed("hide_comment", hide_comment,
                                                               comment_id=get_comment_id(), page_token=tok)),
            ("Afficher un commentaire masqué", lambda pid, tok: _confirmed("unhide_comment", unhide_comment,
                                                                       comment_id=get_comment_id(), page_token=tok)),
        ],
        "Conversations (Messenger)": [
            ("Lister les conversations", lambda pid, tok: list_conversations(pid, tok)),
            ("Lire les messages d'une conversation",
             lambda pid, tok: list_conversation_messages(get_conversation_id(), tok)),
            ("Marquer une conversation comme lue",
             lambda pid, tok: _confirmed("mark_conversation_read", mark_conversation_read,
                                         conversation_id=get_conversation_id(), page_token=tok, page_id=pid)),
            ("Envoyer un message texte",
             lambda pid, tok: _confirmed("send_text_message", send_text_message,
                                         conversation_id=get_conversation_id(), text=get_text(), page_token=tok,
                                         page_id=pid)),
            ("Envoyer des réponses rapides",
             lambda pid, tok: _confirmed("send_quick_replies", send_quick_replies,
                                         conversation_id=get_conversation_id(), text=get_text(), options=get_options(),
                                         page_token=tok, page_id=pid)),
            ("Envoyer une pièce jointe",
             lambda pid, tok: _confirmed("send_attachment_from_conversation", send_attachment_from_conversation,
                                         page_id=pid, conversation_id=get_conversation_id(),
                                         file_path=get_file_path(), page_token=tok)),
        ],
        "Page": [
            ("Informations de la page", lambda pid, tok: get_page_info(pid, tok)),
        ],
        # Lead Ads : chaque écriture est montrée puis confirmée (o/n) avant l'envoi
        "Lead Ads": [
            ("Lister les formulaires", lambda pid, tok: list_lead_forms(pid, tok)),
            ("Créer un formulaire", lambda pid, tok: _create_lead_form(pid, tok)),
            ("Archiver un formulaire", lambda pid, tok: _archive_lead_form(tok)),
            ("Créer un lead de test", lambda pid, tok: _create_test_lead(tok)),
            ("Lister les leads de test d'un formulaire", lambda pid, tok: list_test_leads(get_lead_form_id(), tok)),
            ("Supprimer un lead de test", lambda pid, tok: _delete_test_lead(tok)),
            ("Lister les leads d'un formulaire", lambda pid, tok: list_form_leads(get_lead_form_id(), tok)),
        ],
        # Campagnes : compte AD_ACCOUNT_ID (sandbox ou sans moyen de paiement), tout en PAUSED, budget minimal ;
        # token ADS_ACCESS_TOKEN, sinon FB_USER_TOKEN ; chaque écriture est montrée puis confirmée (o/n)
        "Campagnes": [
            ("Lister les campagnes", lambda pid, tok: list_campaigns(account(), ads_token())),
            ("Créer une campagne", lambda pid, tok: _confirmed(
                "create_campaign", create_campaign, ad_account_id=account(), name=get_name("de la campagne"),
                objective=get_objective(), access_token=ads_token())),
            ("Modifier une campagne (nom, pause)", lambda pid, tok: _confirmed(
                "update_campaign", update_campaign, campaign_id=get_object_id("de la campagne"),
                ad_account_id=account(), access_token=ads_token(), name=get_new_name(), pause=get_pause())),
            ("Supprimer une campagne", lambda pid, tok: _confirmed(
                "delete_campaign", delete_campaign, campaign_id=get_object_id("de la campagne"),
                ad_account_id=account(), access_token=ads_token())),
            ("Lister les ensembles de publicités", lambda pid, tok: list_ad_sets(
                account(), ads_token(), campaign_id=get_object_id("de la campagne (vide = toutes)") or None)),
            ("Créer un ensemble de publicités", lambda pid, tok: _confirmed(
                "create_ad_set", create_ad_set, ad_account_id=account(), campaign_id=get_object_id("de la campagne"),
                name=get_name("de l'ensemble"), access_token=ads_token(), countries=get_countries(), page_id=pid)),
            ("Modifier un ensemble (nom, pays, pause)", lambda pid, tok: _confirmed(
                "update_ad_set", update_ad_set, ad_set_id=get_object_id("de l'ensemble"), ad_account_id=account(),
                access_token=ads_token(), name=get_new_name(), countries=get_countries(), pause=get_pause())),
            ("Supprimer un ensemble de publicités", lambda pid, tok: _confirmed(
                "delete_ad_set", delete_ad_set, ad_set_id=get_object_id("de l'ensemble"), ad_account_id=account(),
                access_token=ads_token())),
            ("Lister les publicités", lambda pid, tok: list_ads(
                account(), ads_token(), ad_set_id=get_object_id("de l'ensemble (vide = toutes)") or None)),
            ("Créer une publicité", lambda pid, tok: _confirmed(
                "create_ad", create_ad, ad_account_id=account(), ad_set_id=get_object_id("de l'ensemble"),
                name=get_name("de la publicité"), access_token=ads_token(), **get_ad_creative(), page_id=pid,
                page_token=tok)),
            ("Modifier une publicité (nom, pause)", lambda pid, tok: _confirmed(
                "update_ad", update_ad, ad_id=get_object_id("de la publicité"), ad_account_id=account(),
                access_token=ads_token(), name=get_new_name(), pause=get_pause())),
            ("Supprimer une publicité", lambda pid, tok: _confirmed(
                "delete_ad", delete_ad, ad_id=get_object_id("de la publicité"), ad_account_id=account(),
                access_token=ads_token())),
        ],
        "Photos": [
            ("Lister les photos", lambda pid, tok: list_photos(pid, tok)),
            ("Lister les albums", lambda pid, tok: list_albums(pid, tok)),
            ("Publier une photo",
             lambda pid, tok: _confirmed("upload_photo", upload_photo, page_id=pid,
                                         image_path_or_url=get_photo_url(), page_token=tok,
                                         caption=get_photo_caption())),
            ("Ajouter une photo à un album",
             lambda pid, tok: _confirmed("upload_photo_to_album", upload_photo_to_album, album_id=get_album_id(),
                                         file_path=get_photo_file_path(), page_token=tok)),
            ("Supprimer une photo", lambda pid, tok: _confirmed("delete_photo", delete_photo, photo_id=get_photo_id(),
                                                            page_token=tok)),
            ("Changer la photo de couverture", lambda pid, tok: _confirmed("update_cover_photo", update_cover_photo,
                                                                       page_id=pid, page_token=tok,
                                                                       image_path_or_url=get_photo_url())),
            ("Changer la photo de profil", lambda pid, tok: _confirmed("update_profile_picture", update_profile_picture,
                                                                       page_id=pid, page_token=tok,
                                                                       image_path_or_url=get_photo_url())),
        ],
        "Utilisateurs": [
            ("Bannir un utilisateur", lambda pid, tok: _confirmed("ban_user", ban_user, page_id=pid, user_id=get_user_id(),
                                                              page_token=tok)),
            ("Débannir un utilisateur", lambda pid, tok: _confirmed("unban_user", unban_user, page_id=pid,
                                                                user_id=get_user_id(), page_token=tok)),
        ],
        "Vidéos": [
            ("Lister les vidéos", lambda pid, tok: list_videos(pid, tok)),
            ("Publier une vidéo", lambda pid, tok: _confirmed(
                "upload_video", upload_video, page_id=pid, video_source=get_video_url(), page_token=tok,
                title=get_video_title(), description=get_video_description())),
            ("Programmer une vidéo", lambda pid, tok: _confirmed(
                "upload_video", upload_video, page_id=pid, video_source=get_video_url(), page_token=tok,
                title=get_video_title(), description=get_video_description(), publish_at=get_publish_at())),
            ("Supprimer une vidéo", lambda pid, tok: _confirmed("delete_video", delete_video, video_id=get_video_id(),
                                                                page_token=tok)),
        ],
        # Catalogue : token utilisateur (FB_USER_TOKEN), pas le token de la page.
        "Catalogue : produits": [
            # La page et son token servent seulement à héberger une image locale.
            ("Créer un produit",
             lambda pid, tok: _confirmed("create_product", create_product, catalog_id=catalog_id(),
                                         access_token=user(), data=get_create_product_data(), page_id=pid,
                                         page_token=tok)),
            ("Modifier un produit", lambda pid, tok: _update_product(user(), pid, tok)),
            ("Supprimer un produit", lambda pid, tok: _confirmed("delete_product", delete_product,
                                                             product_id=get_product_id(), access_token=user())),
            ("Rechercher des produits",
             lambda pid, tok: search_products(catalog_id(), get_name_partial_match(), user())),
        ],
        "Catalogue : product sets": [
            ("Lister les product sets", lambda pid, tok: list_product_sets(catalog_id(), user())),
            ("Créer un product set",
             lambda pid, tok: _confirmed("create_product_set", create_product_set, catalog_id=catalog_id(),
                                         name=get_set_name(), product_filter=get_retailer_ids(),
                                         access_token=user())),
            ("Modifier un product set", lambda pid, tok: _update_product_set(user())),
            ("Supprimer un product set", lambda pid, tok: _confirmed("delete_product_set", delete_product_set,
                                                                 product_set_id=get_product_set_id(),
                                                                 access_token=user())),
        ],
        "Catalogue : product feeds": [
            ("Lister les feeds", lambda pid, tok: list_product_feeds(catalog_id(), user())),
            ("Créer un feed et importer un fichier",
             lambda pid, tok: _confirmed("create_and_upload_feed", create_and_upload_feed, catalog_id=catalog_id(),
                                         name=get_feed_name(), feed_url=get_feed_url(), access_token=user())),
            ("Réimporter un feed",
             lambda pid, tok: _confirmed("reupload_product_feed", reupload_product_feed, feed_id=get_feed_id(),
                                         access_token=user(), feed_url=get_new_feed_url())),
            ("Supprimer un feed", lambda pid, tok: _confirmed("delete_product_feed", delete_product_feed,
                                                          feed_id=get_feed_id(), access_token=user())),
        ],
    }


def choose(options: list[str], title: str) -> int | None:
    """Print numbered options and ask the user to choose one (asked again if invalid).

    Args:
        options: Labels of the options.
        title: Title of the menu ("Menu principal" shows "Quitter" instead of "Retour").

    Returns:
        The index of the chosen option, or None for 0 (back or quit).
    """
    print(f"\n=== {title} ===")
    for i, label in enumerate(options, start=1):
        print(f"{i}. {label}")
    print("0. Retour" if title != "Menu principal" else "0. Quitter")
    answer = input("Ton choix : ").strip()
    if answer == "0":
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(options):
        return int(answer) - 1
    print("Choix invalide.")
    return choose(options, title)


def main() -> None:
    """Run the interactive menu; Ctrl+C or the end of the input quits cleanly with "Au revoir."."""
    try:
        _run_menu()
    except (KeyboardInterrupt, EOFError):
        print()
        print("Au revoir.")


def _run_menu() -> None:
    """Run the interactive menu: authenticate, choose a page, then run the chosen operations until the user quits."""
    auth_result = authenticate(config.FB_USER_TOKEN, get_auth_choice(), config.FB_APP_ID, config.FB_APP_SECRET)
    result = select_page(auth_result)
    if not isinstance(result, tuple):
        print("Erreur :", json.dumps(result, ensure_ascii=False, indent=2))
        return
    page_id, page_token = result

    menu = build_menu()
    categories = list(menu)
    while True:
        cat_index = choose(categories, "Menu principal")
        if cat_index is None:
            print("Au revoir.")
            return
        actions = menu[categories[cat_index]]
        while True:
            action_index = choose([label for label, _ in actions], categories[cat_index])
            if action_index is None:
                break
            try:
                response = actions[action_index][1](page_id, page_token)
            except InvalidInputError as error:  # saisie invalide : retour au menu
                print("Saisie invalide :")
                for message in error.errors:
                    print(f"  - {message}")
                continue
            except RuntimeError as error:  # variable manquante dans le .env
                print("Erreur :", error)
                continue
            except Exception as error:  # ex. fichier local introuvable
                print("Erreur inattendue :", error)
                continue
            print(json.dumps(response, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
