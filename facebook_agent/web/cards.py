"""Visual cards of the web interface, built by the code from the full results of the read operations.

The model never receives these data (agent/views.py removes the display-only fields): the cards cost no
token. Each builder turns one successful result into a CardSet: the cards, the message of an empty list,
and whether more items exist ("Voir plus"). No Streamlit here (tested with plain pytest); app.py draws them.
"""
import re
from dataclasses import dataclass, field

from facebook_agent.agent.display import french_date

EXCERPT_CHARS = 180
SAFE_ID = re.compile(r"^[\w-]{1,80}$")
SAFE_URL = re.compile(r"^https://[^\s\"'<>]+$")


@dataclass
class Card:
    """One visual card (or one row of a table)."""

    title: str
    id: str | None = None
    subtitle: str = ""
    image: str | None = None
    link: str | None = None
    link_label: str = ""
    badges: list[tuple[str, str]] = field(default_factory=list)  # (libellé, couleur Streamlit)
    columns: dict[str, str] = field(default_factory=dict)  # tableaux : colonne -> valeur


@dataclass
class CardSet:
    """The cards of one result, how to draw them and what to say when the list is empty."""

    tool: str
    layout: str  # "list" (posts), "grid" (miniatures), "table" (campagnes…)
    cards: list[Card]
    empty: str
    more: bool = False
    more_request: str | None = None
    note: str | None = None
    noun: tuple[str, str] = ("élément", "éléments")  # singulier, pluriel (phrase de résumé du code)
    feminine: bool = False
    phrase: tuple[str, str] | None = None  # phrase propre : (une, plusieurs avec {n}), ex. posts
    page_size: int | None = None  # cartes montrées d'abord ; « Voir plus » montre les suivantes (formulaires)
    created: bool = False  # carte d'un objet que la demande vient de créer (relu après l'écriture)

    def summary(self) -> str:
        """Summary sentence built by the code, shown when the model's answer is not a short sentence.

        Returns:
            "1 produit trouvé.", "2 campagnes trouvées.", "3 derniers posts.", or the empty message.
        """
        count = len(self.cards)
        if not count:
            return self.empty
        if self.phrase:
            return self.phrase[0] if count == 1 else self.phrase[1].format(n=count)
        found = "trouvée" if self.feminine else "trouvé"
        return f"1 {self.noun[0]} {found}." if count == 1 else f"{count} {self.noun[1]} {found}s."


def safe_id(value) -> str | None:
    """An ID that may be written into HTML and JavaScript (digits, letters, "_" and "-").

    Args:
        value: Any value of a result.

    Returns:
        The ID as a string, or None if it has another form.
    """
    text = str(value) if value is not None else ""
    return text if SAFE_ID.match(text) else None


def safe_url(value) -> str | None:
    """An https URL that may be used as a link or an image (anything else is dropped).

    Args:
        value: Any value of a result.

    Returns:
        The URL, or None.
    """
    return value if isinstance(value, str) and SAFE_URL.match(value) else None


def excerpt(text, limit: int = EXCERPT_CHARS) -> str:
    """One-paragraph excerpt of a text.

    Args:
        text: Any text (or None).
        limit: Maximum characters.

    Returns:
        The text on one line, cut with "…" beyond limit.
    """
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def local_date(value) -> str:
    """Graph API date or Unix timestamp in local time, French format.

    Args:
        value: "2026-10-24T19:59:00+0000" or a number of seconds.

    Returns:
        "24 oct. 2026, 20:59", or "" if unreadable.
    """
    return french_date(value)


def plural(count: int, singular: str, plural_form: str) -> str:
    """ "1 réaction", "3 réactions", "0 réaction".

    Args:
        count: The number.
        singular: Singular noun.
        plural_form: Plural noun.

    Returns:
        The number and the right noun.
    """
    return f"{count} {singular if count <= 1 else plural_form}"


def items_of(data) -> tuple[list[dict], bool]:
    """Items of a list result and whether more exist.

    Args:
        data: The "data" of a result ({"data": [...], "paging": ...} or [...]).

    Returns:
        (items, more): more is True with a paging.next or a truncated list.
    """
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)], False
    if not isinstance(data, dict):
        return [], False
    items = [item for item in data.get("data") or [] if isinstance(item, dict)]
    more = bool((data.get("paging") or {}).get("next")) or bool(data.get("truncated"))
    return items, more


def summary_count(value) -> int:
    """total_count of an edge summary ({"summary": {"total_count": 3}}).

    Args:
        value: The edge object (or anything).

    Returns:
        The count, 0 when absent.
    """
    if isinstance(value, dict) and isinstance(value.get("summary"), dict):
        count = value["summary"].get("total_count")
        return count if isinstance(count, int) else 0
    return 0


# --- Posts ------------------------------------------------------------------------------------------------

def post_card(post: dict, scheduled: bool = False) -> Card:
    """Card of one post: picture, excerpt, date, reactions and comments, link to Facebook.

    Args:
        post: One post of list_posts, list_scheduled_posts or get_post.
        scheduled: True for a scheduled post (its planned date instead of the counts).

    Returns:
        The card.
    """
    text = excerpt(post.get("message") or post.get("story")) or "(sans texte)"
    if scheduled:
        when = local_date(post.get("scheduled_publish_time")) or local_date(post.get("created_time"))
        subtitle = f"Programmé pour le {when}" if when else "Programmé"
    else:
        parts = [local_date(post.get("created_time"))]
        if "reactions" in post or "comments" in post:
            parts.append(plural(summary_count(post.get("reactions")), "réaction", "réactions"))
            parts.append(plural(summary_count(post.get("comments")), "commentaire", "commentaires"))
        subtitle = " · ".join(part for part in parts if part)
    link = safe_url(post.get("permalink_url"))
    return Card(title=text, id=safe_id(post.get("id")), subtitle=subtitle, image=safe_url(post.get("full_picture")),
                link=link, link_label="Voir sur Facebook" if link else "")


def posts_cards(tool: str, data) -> CardSet:
    """Cards of list_posts and list_scheduled_posts.

    Args:
        tool: "list_posts" or "list_scheduled_posts".
        data: The "data" of the result.

    Returns:
        The card set ("Voir plus" asks for twice as many posts).
    """
    items, more = items_of(data)
    scheduled = tool == "list_scheduled_posts"
    cards = [post_card(post, scheduled) for post in items]
    request = ("Liste tous mes posts programmés" if scheduled
               else f"Liste mes {max(len(items) * 2, 10)} derniers posts")
    return CardSet(tool, "list", cards, "Aucun post programmé." if scheduled else "Aucun post trouvé.", more,
                   request if more else None, noun=("post programmé", "posts programmés") if scheduled
                   else ("post", "posts"),
                   phrase=("1 post programmé.", "{n} posts programmés.") if scheduled
                   else ("Dernier post.", "{n} derniers posts."))


def get_post_cards(tool: str, data) -> CardSet:
    """Card of get_post (one post).

    Args:
        tool: "get_post".
        data: The post.

    Returns:
        A card set with one card.
    """
    cards = [post_card(data)] if isinstance(data, dict) and data.get("id") else []
    return CardSet(tool, "list", cards, "Post introuvable.", noun=("post", "posts"), phrase=("Voici le post.",
                                                                                           "{n} posts."))


# --- Photos, albums, vidéos (grille de miniatures) ---------------------------------------------------------

THUMB_WIDTH = 320  # largeur visée d'une miniature (la plus petite image au moins aussi large, sinon la plus grande)


def photo_source(images) -> str | None:
    """URL of the stored size of a photo that suits a thumbnail.

    Args:
        images: The "images" field of a photo ([{"height", "width", "source"}]).

    Returns:
        The https URL, or None.
    """
    sizes = [image for image in images or [] if isinstance(image, dict) and safe_url(image.get("source"))]
    if not sizes:
        return None
    wide = sorted((image for image in sizes if (image.get("width") or 0) >= THUMB_WIDTH),
                  key=lambda image: image.get("width") or 0)
    chosen = wide[0] if wide else max(sizes, key=lambda image: image.get("width") or 0)
    return chosen["source"]


def photos_cards(tool: str, data) -> CardSet:
    """Grid of the photos: thumbnail, caption, date, link to the photo on Facebook.

    Args:
        tool: "list_photos".
        data: The "data" of the result.

    Returns:
        The card set.
    """
    items, more = items_of(data)
    cards = []
    for photo in items:
        link = safe_url(photo.get("link"))
        cards.append(Card(title=excerpt(photo.get("name"), 80), id=safe_id(photo.get("id")),
                          subtitle=local_date(photo.get("created_time")), image=photo_source(photo.get("images")),
                          link=link, link_label="Voir sur Facebook" if link else ""))
    return CardSet(tool, "grid", cards, "Aucune photo trouvée.", more,
                   f"Liste mes {max(len(items) * 2, 10)} dernières photos" if more else None,
                   noun=("photo", "photos"), feminine=True)


def albums_cards(tool: str, data) -> CardSet:
    """Grid of the albums: cover photo (grey frame when the album has none), name, number of photos, link to the
    album on Facebook.

    Args:
        tool: "list_albums".
        data: The "data" of the result.

    Returns:
        The card set.
    """
    items, more = items_of(data)
    cards = []
    for album in items:
        count = album.get("count")
        link = safe_url(album.get("link"))
        cover = album.get("cover_photo")
        cards.append(Card(title=excerpt(album.get("name"), 80) or "(album sans nom)", id=safe_id(album.get("id")),
                          subtitle=plural(count, "photo", "photos") if isinstance(count, int) else "",
                          image=photo_source(cover.get("images")) if isinstance(cover, dict) else None,
                          link=link, link_label="Voir l'album" if link else ""))
    return CardSet(tool, "grid", cards, "Aucun album trouvé.", more, "Liste tous mes albums photo" if more else None,
                   noun=("album", "albums"))


def videos_cards(tool: str, data) -> CardSet:
    """Grid of the videos: thumbnail, title, date (Meta documents no link to a video: none is shown).

    Args:
        tool: "list_videos".
        data: The "data" of the result.

    Returns:
        The card set.
    """
    items, more = items_of(data)
    cards = [Card(title=excerpt(video.get("title") or video.get("description"), 80) or "(vidéo sans titre)",
                  id=safe_id(video.get("id")), subtitle=local_date(video.get("created_time")),
                  image=safe_url(video.get("picture")))
             for video in items]
    return CardSet(tool, "grid", cards, "Aucune vidéo trouvée.", more,
                   f"Liste mes {max(len(items) * 2, 10)} dernières vidéos" if more else None,
                   noun=("vidéo", "vidéos"), feminine=True)


# --- Catalogue : produits, collections, flux ----------------------------------------------------------------

# Pages d'entrée stables du Gestionnaire de ventes (adresses de l'interface Meta, pas de l'API : voir README)
COMMERCE_PRODUCTS = "https://business.facebook.com/commerce/catalogs/{catalog}/products"
COMMERCE_CATALOG = "https://business.facebook.com/commerce/catalogs/{catalog}"
AVAILABILITY = {"in stock": ("En stock", "green"), "out of stock": ("Rupture de stock", "red"),
                "preorder": ("Précommande", "blue"), "available for order": ("Sur commande", "blue"),
                "discontinued": ("Arrêté", "gray")}


def commerce_link(template: str, links: dict) -> str | None:
    """Link to the Commerce Manager of the session's catalog.

    Args:
        template: COMMERCE_PRODUCTS or COMMERCE_CATALOG.
        links: IDs of the session ("catalog", "page", "ad_account", "ads_mode").

    Returns:
        The URL, or None without a valid catalog ID.
    """
    catalog = safe_id(links.get("catalog"))
    return template.format(catalog=catalog) if catalog else None


def products_cards(tool: str, data, links: dict) -> CardSet:
    """Cards of search_products: picture, name, price (struck out during a promotion), availability.

    Args:
        tool: "search_products".
        data: The "data" of the result.
        links: IDs of the session.

    Returns:
        The card set (the search reads the whole catalog: no "Voir plus").
    """
    items, _ = items_of(data)
    link = commerce_link(COMMERCE_PRODUCTS, links)
    cards = []
    for product in items:
        label, color = AVAILABILITY.get(str(product.get("availability") or "").lower(),
                                        (str(product.get("availability") or ""), "gray"))
        price = {"price": str(product.get("price") or "")}
        if product.get("sale_price"):
            price["sale_price"] = str(product["sale_price"])
        cards.append(Card(title=excerpt(product.get("name"), 80) or "(produit sans nom)", id=safe_id(product.get("id")),
                          image=safe_url(product.get("image_url")), link=link,
                          link_label="Gestionnaire de ventes" if link else "",
                          badges=[(label, color)] if label else [], columns=price))
    note = "Recherche incomplète : le catalogue dépasse la limite de lecture." if (
        isinstance(data, dict) and data.get("truncated")) else None
    return CardSet(tool, "grid", cards, "Aucun produit trouvé.", note=note, noun=("produit", "produits"))


def product_sets_cards(tool: str, data, links: dict) -> CardSet:
    """Cards of list_product_sets: name and number of products.

    Args:
        tool: "list_product_sets".
        data: The "data" of the result.
        links: IDs of the session.

    Returns:
        The card set.
    """
    items, more = items_of(data)
    link = commerce_link(COMMERCE_CATALOG, links)
    cards = [Card(title=excerpt(item.get("name"), 80) or "(collection sans nom)", id=safe_id(item.get("id")),
                  subtitle=plural(item["product_count"], "produit", "produits")
                  if isinstance(item.get("product_count"), int) else "",
                  link=link, link_label="Gestionnaire de ventes" if link else "")
             for item in items]
    return CardSet(tool, "list", cards, "Aucune collection trouvée.", more,
                   "Liste toutes mes collections de produits" if more else None, noun=("collection", "collections"),
                   feminine=True)


def product_feeds_cards(tool: str, data, links: dict) -> CardSet:
    """Cards of list_product_feeds: name, file, number of products, last import.

    Args:
        tool: "list_product_feeds".
        data: The "data" of the result.
        links: IDs of the session.

    Returns:
        The card set.
    """
    items, more = items_of(data)
    link = commerce_link(COMMERCE_CATALOG, links)
    cards = []
    for feed in items:
        upload = feed.get("latest_upload") if isinstance(feed.get("latest_upload"), dict) else {}
        when = local_date(upload.get("end_time") or upload.get("start_time"))
        parts = [str(feed.get("file_name") or ""),
                 plural(feed["product_count"], "produit", "produits") if isinstance(feed.get("product_count"), int)
                 else "", f"dernière importation le {when}" if when else ""]
        cards.append(Card(title=excerpt(feed.get("name"), 80) or "(flux sans nom)", id=safe_id(feed.get("id")),
                          subtitle=" · ".join(part for part in parts if part), link=link,
                          link_label="Gestionnaire de ventes" if link else ""))
    return CardSet(tool, "list", cards, "Aucun flux de produits.", more,
                   "Liste tous mes flux de produits" if more else None, noun=("flux", "flux"))


# --- Messenger : conversations et messages ---------------------------------------------------------------------

# Page d'entrée stable de la boîte de réception de Meta Business Suite (adresse de l'interface : voir README)
INBOX = "https://business.facebook.com/latest/inbox/all?asset_id={page}"


def inbox_link(links: dict) -> str | None:
    """Link to the inbox of the page in Meta Business Suite.

    Args:
        links: IDs of the session.

    Returns:
        The URL, or None without a valid page ID.
    """
    page = safe_id(links.get("page"))
    return INBOX.format(page=page) if page else None


def conversations_cards(tool: str, data, links: dict) -> CardSet:
    """Cards of list_conversations: name of the client, date, excerpt of the last message, link to the inbox.

    Args:
        tool: "list_conversations".
        data: The "data" of the result.
        links: IDs of the session (the page tells its own messages from the client's ones).

    Returns:
        The card set.
    """
    items, more = items_of(data)
    page = str(links.get("page") or "")
    link = inbox_link(links)
    cards = []
    for conversation in items:
        people = (conversation.get("participants") or {}).get("data") or []
        clients = [str(p.get("name")) for p in people if isinstance(p, dict) and str(p.get("id")) != page
                   and p.get("name")]
        last = ((conversation.get("messages") or {}).get("data") or [None])[0]
        excerpt_text = ""
        if isinstance(last, dict):
            author = last.get("from") if isinstance(last.get("from"), dict) else {}
            text = excerpt(last.get("message"), 90) or "(pièce jointe)"
            excerpt_text = f"Vous : {text}" if str(author.get("id")) == page else text
        parts = [local_date(conversation.get("updated_time")), excerpt_text]
        cards.append(Card(title=", ".join(clients) or "(client inconnu)", id=safe_id(conversation.get("id")),
                          subtitle=" · ".join(part for part in parts if part), link=link,
                          link_label="Boîte de réception" if link else ""))
    return CardSet(tool, "list", cards, "Aucune conversation.", more,
                   "Liste plus de conversations Messenger" if more else None,
                   noun=("conversation", "conversations"), feminine=True)


def messages_cards(tool: str, data, links: dict) -> CardSet:
    """Messages of a conversation as chat bubbles, oldest first: the client on the left, the page on the right.

    Args:
        tool: "list_conversation_messages".
        data: The "data" of the result (newest first, as sent by the API).
        links: IDs of the session.

    Returns:
        The card set (layout "chat"; columns["role"] is "page" or "client").
    """
    items, more = items_of(data)
    page = str(links.get("page") or "")
    cards = []
    for message in reversed(items):
        author = message.get("from") if isinstance(message.get("from"), dict) else {}
        role = "page" if str(author.get("id")) == page else "client"
        cards.append(Card(title=excerpt(message.get("message"), 600) or "(pièce jointe ou réaction)",
                          subtitle=" · ".join(part for part in (str(author.get("name") or ""),
                                                                local_date(message.get("created_time"))) if part),
                          columns={"role": role}))
    return CardSet(tool, "chat", cards, "Aucun message dans cette conversation.", more,
                   "Montre les messages plus anciens de cette conversation" if more else None,
                   noun=("message", "messages"))


# --- Lead Ads : formulaires ------------------------------------------------------------------------------------

# Page d'entrée stable des formulaires instantanés dans Meta Business Suite (adresse de l'interface : voir README)
INSTANT_FORMS = "https://business.facebook.com/latest/instant_forms?asset_id={page}"
FORM_STATUS = {"ACTIVE": ("Actif", "green"), "ARCHIVED": ("Archivé", "gray"), "DELETED": ("Supprimé", "red"),
               "DRAFT": ("Brouillon", "orange")}
FORMS_SHOWN = 5  # formulaires montrés d'abord, puis « Voir plus » (5 de plus à chaque clic)


def lead_forms_cards(tool: str, data, links: dict) -> CardSet:
    """Cards of list_lead_forms: name, status badge, number of leads, creation date, link to the form list.

    The leads themselves keep their folded block (full answers for the user only, never sent to the model).

    Args:
        tool: "list_lead_forms".
        data: The "data" of the result.
        links: IDs of the session.

    Returns:
        The card set.
    """
    items, more = items_of(data)
    page = safe_id(links.get("page"))
    link = INSTANT_FORMS.format(page=page) if page else None
    cards = []
    for form in items:
        status = str(form.get("status") or "").upper()
        badge = FORM_STATUS.get(status, (status.capitalize(), "gray")) if status else None
        count = form.get("leads_count")
        parts = [plural(count, "lead", "leads") if isinstance(count, int) else "",
                 f"créé le {local_date(form.get('created_time'))}" if local_date(form.get("created_time")) else ""]
        cards.append(Card(title=excerpt(form.get("name"), 80) or "(formulaire sans nom)", id=safe_id(form.get("id")),
                          subtitle=" · ".join(part for part in parts if part), link=link,
                          link_label="Formulaires dans Meta Business Suite" if link else "",
                          badges=[badge] if badge else []))
    return CardSet(tool, "list", cards, "Aucun formulaire Lead Ads.", more,
                   "Liste tous mes formulaires Lead Ads" if more else None, noun=("formulaire", "formulaires"),
                   page_size=FORMS_SHOWN)


# --- Publicités : campagnes, ensembles, publicités (tableaux) ------------------------------------------------

# Listes du Gestionnaire de publicités du compte (adresses de l'interface Meta : voir README) ; jamais en sandbox
ADS_MANAGER = "https://adsmanager.facebook.com/adsmanager/manage/{level}?act={account}"
SANDBOX_NOTE = "Compte sandbox, non visible chez Meta."
AD_STATUS = {"ACTIVE": ("Actif", "green"), "PAUSED": ("En pause", "orange"),
             "CAMPAIGN_PAUSED": ("En pause (campagne)", "orange"), "ADSET_PAUSED": ("En pause (ensemble)", "orange"),
             "DELETED": ("Supprimé", "red"), "ARCHIVED": ("Archivé", "gray"), "IN_PROCESS": ("En traitement", "blue"),
             "PENDING_REVIEW": ("En examen", "blue"), "DISAPPROVED": ("Refusé", "red"),
             "WITH_ISSUES": ("Problème", "red")}
OBJECTIVES = {"OUTCOME_TRAFFIC": "Trafic", "OUTCOME_ENGAGEMENT": "Interactions", "OUTCOME_AWARENESS": "Notoriété",
              "OUTCOME_LEADS": "Prospects", "OUTCOME_SALES": "Ventes", "OUTCOME_APP_PROMOTION": "Promotion d'app"}
AD_LEVELS = {"list_campaigns": ("campaigns", "Campagne", ("campagne", "campagnes"), "Aucune campagne."),
             "list_ad_sets": ("adsets", "Ensemble", ("ensemble de publicités", "ensembles de publicités"),
                              "Aucun ensemble de publicités."),
             "list_ads": ("ads", "Publicité", ("publicité", "publicités"), "Aucune publicité.")}


def ad_status_badge(item: dict) -> tuple[str, str] | None:
    """Badge of the effective status of a campaign, ad set or ad.

    Args:
        item: One item of list_campaigns, list_ad_sets or list_ads.

    Returns:
        (French label, colour), or None without status.
    """
    status = str(item.get("effective_status") or item.get("status") or "").upper()
    return AD_STATUS.get(status, (status.replace("_", " ").capitalize(), "gray")) if status else None


def daily_budget(value) -> str:
    """Daily budget of an ad set (the API gives it in the smallest unit of the currency, e.g. cents).

    Args:
        value: "100" or 100.

    Returns:
        "1,00 par jour", or "" if unreadable.
    """
    try:
        return f"{int(value) / 100:.2f}".replace(".", ",") + " par jour"
    except (TypeError, ValueError):
        return ""


def ads_cards(tool: str, data, links: dict) -> CardSet:
    """Table of the campaigns, ad sets or ads: name, status badge, objective or budget, creation date.

    The link to Ads Manager is never shown for a sandbox account (its objects are not visible at Meta).

    Args:
        tool: "list_campaigns", "list_ad_sets" or "list_ads".
        data: The "data" of the result.
        links: IDs of the session ("ad_account", "ads_mode").

    Returns:
        The card set (layout "table": each card's columns are the cells).
    """
    items, more = items_of(data)
    level, column, noun, empty = AD_LEVELS[tool]
    sandbox = links.get("ads_mode") == "sandbox"
    account = str(links.get("ad_account") or "").removeprefix("act_")
    link = ADS_MANAGER.format(level=level, account=account) if account.isdigit() and not sandbox else None
    cards = []
    for item in items:
        columns = {column: excerpt(item.get("name"), 60) or "(sans nom)"}
        if tool == "list_campaigns":
            columns["Objectif"] = OBJECTIVES.get(str(item.get("objective")), str(item.get("objective") or "—"))
        elif tool == "list_ad_sets":
            columns["Budget"] = daily_budget(item.get("daily_budget")) or "—"
        columns["Créé le"] = local_date(item.get("created_time")) or "—"
        badge = ad_status_badge(item)
        cards.append(Card(title=columns[column], id=safe_id(item.get("id")), columns=columns,
                          badges=[badge] if badge else [], link=link,
                          link_label="Gestionnaire de publicités" if link else ""))
    return CardSet(tool, "table", cards, empty, more, f"Liste tous mes {noun[1]}" if more else None,
                   note=SANDBOX_NOTE if sandbox and cards else None, noun=noun, feminine=tool != "list_ad_sets")


BUILDERS = {"list_posts": posts_cards, "list_scheduled_posts": posts_cards, "get_post": get_post_cards,
            "list_lead_forms": lead_forms_cards, "list_campaigns": ads_cards, "list_ad_sets": ads_cards,
            "list_ads": ads_cards,
            "list_photos": photos_cards, "list_albums": albums_cards, "list_videos": videos_cards,
            "search_products": products_cards, "list_product_sets": product_sets_cards,
            "list_product_feeds": product_feeds_cards, "list_conversations": conversations_cards,
            "list_conversation_messages": messages_cards}
NEEDS_LINKS = frozenset({"search_products", "list_product_sets", "list_product_feeds", "list_conversations",
                         "list_conversation_messages", "list_lead_forms", "list_campaigns", "list_ad_sets",
                         "list_ads"})
# Icône du cadre d'une miniature, par opération
THUMB_ICONS = {"list_photos": "image", "list_albums": "photo_library", "list_videos": "movie",
               "search_products": "shopping_bag"}


def build_cards(tool: str, output, links: dict | None = None) -> CardSet | None:
    """Card set of a successful result of a read operation.

    Args:
        tool: Operation name.
        output: Full result of the operation ({"status": "success", "data": ...}).
        links: IDs of the session for the links to the Meta interface ("catalog", "page", "ad_account",
            "ads_mode"); never shown as text.

    Returns:
        The card set, or None for an operation without cards or a failed result.
    """
    if tool not in BUILDERS or not isinstance(output, dict) or output.get("status") != "success":
        return None
    if tool in NEEDS_LINKS:
        return BUILDERS[tool](tool, output.get("data"), links or {})
    return BUILDERS[tool](tool, output.get("data"))


ID_LIKE = re.compile(r"\b(?:act_|t_|m_)?\d{8,}(?:_\d+)?\b|\bID\b")
SENTENCE_END = re.compile(r"[.!?…]+")


def summary_sentence(answer: str, fallback: str, ids=(), titles=()) -> str:
    """The answer shown above the cards: one short sentence of the model, or the code's sentence.

    The cards already show every item. The code's sentence replaces the answer when it is empty, has more
    than one line or sentence, cites an ID, repeats the title of a card, or announces a list (":").

    Args:
        answer: Answer of the model (or of the code).
        fallback: Sentence of the code (CardSet.summary).
        ids: IDs of the cards.
        titles: Titles of the cards (names, texts).

    Returns:
        The model's sentence when it is one short summary, else the fallback.
    """
    text = (answer or "").strip()
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) != 1 or re.match(r"^([-*•|]|\d+[.)])\s", text) or text.rstrip(".").endswith(":"):
        return fallback
    if ID_LIKE.search(text) or any(str(object_id) in text for object_id in ids if object_id):
        return fallback
    if any(len(title) >= 4 and title.lower() in text.lower() for title in titles if title):
        return fallback
    ends = SENTENCE_END.findall(text)
    if len(ends) > 1 or (ends and not SENTENCE_END.fullmatch(text[-1])):
        return fallback  # deux phrases, ou une phrase suivie d'un autre texte
    return text
