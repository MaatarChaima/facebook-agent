"""Logic of the web interface, without Streamlit (tested with plain pytest).

The page (app.py) only shows a WebSession. The WebSession builds the same agent as the terminal
(agent/build.py) and replaces three functions:
- confirm: the request waits for the "Confirmer" / "Refuser" buttons, at most CONFIRM_TIMEOUT seconds
  (then it is a refusal, shown as TIMEOUT_MESSAGE);
- out / notify: the technical lines go to the "Détails" of the current exchange, not to the chat;
- sleep: the Groq waits stop at once when the "Annuler la demande" button is clicked.

Streamlit runs the page again on every click, while a request cannot stop in the middle: each
request therefore runs in a separate thread, and the page reads its progress.
"""
import math
import re
import threading
import time
from dataclasses import dataclass, field

from facebook_agent import config
from facebook_agent.auth.authentication import authenticate
from facebook_agent.graph import call_graph
from facebook_agent.agent.build import (active_domain_labels, build_agent, disabled_domain_notes, help_text,
                                        session_registry)
from facebook_agent.agent.cancel import BUTTON_HINT, Cancellation, RequestCancelled
from facebook_agent.agent.display import lead_line
from facebook_agent.agent.journal import SessionLog
from facebook_agent.agent.lead_privacy import LEAD_TOOLS
from facebook_agent.agent.loop import CANCELLED_BY_BUTTON
from facebook_agent.agent.policy import DONE_LABELS, WRITE_OPERATIONS
from facebook_agent.operations.ads.ad_sets.list_ad_sets import AD_SET_FIELDS
from facebook_agent.operations.ads.ads.list_ads import AD_FIELDS
from facebook_agent.operations.ads.campaigns.list_campaigns import CAMPAIGN_FIELDS
from facebook_agent.operations.catalogs.product_sets.list_product_sets import PRODUCT_SET_FIELDS
from facebook_agent.operations.catalogs.products.search_products import PRODUCT_FIELDS
from facebook_agent.operations.pages.leads.list_lead_forms import FORM_FIELDS
from facebook_agent.operations.pages.photos.list_photos import PHOTO_FIELDS
from facebook_agent.operations.pages.posts.list_posts import POST_LIST_FIELDS
from facebook_agent.operations.pages.posts.list_scheduled_posts import SCHEDULED_FIELDS
from facebook_agent.agent.session import SessionError, open_session  # noqa: F401 (SessionError : app.py)
from facebook_agent.agent.settings import load_llm_settings
from facebook_agent.agent.tools import AD_DOMAINS, DOMAINS
from facebook_agent.web.cards import build_cards, safe_id, summary_sentence

CONFIRM_TIMEOUT = 600.0  # 10 minutes sans réponse : refus
POLL = 0.2  # secondes entre deux vérifications pendant l'attente d'une confirmation
TIMEOUT_MESSAGE = "Délai dépassé : rien n'a été fait."
EMPTY_ANSWER = "(aucune réponse : voir le journal de la session)"
LLM_FAILED = "Je n'ai pas pu joindre le LLM"  # début de la réponse de l'agent quand le LLM a échoué
OUTCOME_LABELS = {"accepted": "Confirmé.", "refused": "Refusé : rien n'a été fait.", "timeout": TIMEOUT_MESSAGE,
                  "cancelled": "Annulé : rien n'a été fait."}  # « Annuler la demande » pendant la confirmation
WEB_HELP_HEAD = """Menu ⋮ en haut à droite : Aide, Oublier l'historique, Terminer la session (les tokens
sont oubliés). /aide et /reset fonctionnent aussi dans la zone de saisie.

Écris une demande en français, par exemple :
  « liste mes 3 derniers posts »
  « publie un post qui annonce les soldes »
  « cherche le produit T-shirt et baisse son prix à 15 € »
"""
HOW_TO_CONFIRM = "(boutons « Confirmer » / « Refuser »)"
# Type d'objet d'après le nom de l'outil (le premier motif trouvé l'emporte)
KINDS = (("ad_set", "Ensemble de publicités"), ("campaign", "Campagne"), ("lead_form", "Formulaire"),
         ("form_lead", "Lead"), ("test_lead", "Lead"), ("product_set", "Ensemble de produits"),
         ("product_feed", "Flux de produits"), ("product", "Produit"), ("comment", "Commentaire"),
         ("photo", "Photo"), ("video", "Vidéo"), ("post", "Post"), ("_ads", "Publicité"), ("_ad", "Publicité"))
COPY_KINDS = {"Post", "Produit", "Formulaire", "Campagne", "Ensemble de publicités", "Publicité"}
PANEL_KINDS = ("Post", "Photo", "Vidéo", "Couverture", "Photo de profil", "Commentaire", "Réponse", "Message", "Pièce jointe",
               "Produit", "Formulaire", "Campagne", "Ensemble de publicités", "Publicité")
ADS_MODE_LABELS = {"sandbox": "Campagnes : compte sandbox (aucune dépense possible)",
                   "no_payment": "Campagnes : compte sans moyen de paiement (publicités refusées par Meta)"}
ID_TOKEN = re.compile(r"[\w]+")
ADS_MODE_BADGES = {"sandbox": "SANDBOX", "no_payment": "SANS PAIEMENT"}
# Suggestions par domaine : groupe -> (libellé court, demande envoyée, domaine de l'agent nécessaire).
# Une lecture envoie la demande complète ; une écriture envoie une demande qui fait demander les détails
# par l'agent, puis passe par la confirmation habituelle.
SUGGESTIONS = {
    "Page": (("Mes 3 derniers posts", "Liste mes 3 derniers posts", "posts"),
             ("Mes posts programmés", "Liste mes posts programmés", "posts"),
             ("Réactions du dernier post", "Montre les réactions de mon dernier post", "posts"),
             ("Commentaires du dernier post", "Montre les commentaires de mon dernier post", "comments"),
             ("Mes 5 dernières photos", "Liste mes 5 dernières photos", "photos"),
             ("Mes albums", "Liste mes albums photo", "photos"),
             ("Mes vidéos", "Liste mes vidéos", "videos"),
             ("Changer la photo de couverture", "Je veux changer la photo de couverture de la page : demande-moi "
                                                "l'image à utiliser", "photos")),
    "Messenger": (("Mes conversations", "Liste mes conversations Messenger", "messenger"),
                  ("Derniers messages reçus", "Montre les derniers messages reçus sur Messenger", "messenger"),
                  ("Résumer une conversation", "Résume ma dernière conversation Messenger", "messenger"),
                  ("Répondre à un client", "Je veux répondre à un client sur Messenger : demande-moi le client et "
                                           "le message", "messenger")),
    "Catalogue": (("Chercher un produit", "Je veux chercher un produit du catalogue : demande-moi son nom",
                   "products"),
                  ("Mes collections", "Liste mes collections de produits (product sets)", "product_sets"),
                  ("Mes flux de produits", "Liste mes flux de produits", "product_feeds"),
                  ("Mettre un produit en promotion", "Je veux mettre un produit en promotion : demande-moi le "
                                                     "produit et le prix promotionnel", "products")),
    "Lead Ads": (("Mes formulaires", "Liste mes formulaires Lead Ads", "leads"),
                 ("Leads d'un formulaire", "Montre les leads de mon dernier formulaire Lead Ads", "leads"),
                 ("Créer un formulaire de contact", "Je veux créer un formulaire Lead Ads de contact : demande-moi "
                                                    "les détails", "leads")),
    "Publicités": (("Mes campagnes", "Liste mes campagnes", "campaigns"),
                   ("Mes ensembles de publicités", "Liste mes ensembles de publicités", "campaigns"),
                   ("Mes publicités", "Liste mes publicités", "ads"),
                   ("Booster mon dernier post", "Je veux booster mon dernier post : demande-moi les détails avant de "
                                                "créer quoi que ce soit", "boost")),
}
# Carte de chaque suggestion : libellé -> (icône Material, une ligne de description)
SUGGESTION_CARDS = {
    "Mes 3 derniers posts": (":material/article:", "Texte, date et réactions des derniers posts"),
    "Mes posts programmés": (":material/schedule:", "Publications prévues et leur date"),
    "Réactions du dernier post": (":material/thumb_up:", "J'aime et autres réactions"),
    "Commentaires du dernier post": (":material/chat_bubble:", "Les commentaires et leurs auteurs"),
    "Mes 5 dernières photos": (":material/photo_library:", "Les photos récentes de la page"),
    "Mes albums": (":material/collections:", "Les albums photo de la page"),
    "Mes vidéos": (":material/movie:", "Les vidéos publiées sur la page"),
    "Changer la photo de couverture": (":material/wallpaper:", "Nouvelle image de couverture, confirmée"),
    "Mes conversations": (":material/forum:", "Les dernières conversations avec les clients"),
    "Derniers messages reçus": (":material/mark_chat_unread:", "Les messages récents des clients"),
    "Résumer une conversation": (":material/summarize:", "Un résumé de la dernière conversation"),
    "Répondre à un client": (":material/reply:", "Un message à envoyer, confirmé"),
    "Chercher un produit": (":material/search:", "Prix, promotion et disponibilité"),
    "Mes collections": (":material/category:", "Les ensembles de produits du catalogue"),
    "Mes flux de produits": (":material/sync:", "Les flux et leur dernière importation"),
    "Mettre un produit en promotion": (":material/sell:", "Un prix promotionnel, confirmé"),
    "Mes formulaires": (":material/assignment:", "Les formulaires et leur nombre de leads"),
    "Leads d'un formulaire": (":material/contacts:", "Les réponses reçues, visibles par toi seule"),
    "Créer un formulaire de contact": (":material/add_circle:", "Un nouveau formulaire, confirmé"),
    "Mes campagnes": (":material/campaign:", "Statut et objectif des campagnes"),
    "Mes ensembles de publicités": (":material/view_list:", "Budget et statut des ensembles"),
    "Mes publicités": (":material/ads_click:", "Les publicités et leur statut"),
    "Booster mon dernier post": (":material/rocket_launch:", "Une publicité en pause, confirmée"),
}
# Domaines regroupés comme sur l'écran de démarrage : (titre, icône Material, domaines de l'agent)
DOMAIN_GROUPS = (("Page", ":material/article:", ("posts", "comments", "photos", "videos")),
                 ("Messenger", ":material/forum:", ("messenger",)),
                 ("Catalogue", ":material/shopping_bag:", ("products", "product_sets", "product_feeds")),
                 ("Lead Ads", ":material/assignment:", ("leads",)),
                 ("Publicités", ":material/campaign:", ("campaigns", "ads", "boost")))
HELP_COMMANDS = (("Aide", "/aide", "cette aide"),
                 ("Oublier l'historique", "/reset", "la conversation repart de zéro (les objets créés restent listés)"),
                 ("Terminer la session", None, "les tokens sont oubliés ; pour changer le mode dry-run"))
# Confirmation : lignes produites par Executor.confirmation_text
ACTION_LINE = re.compile(r"^Action demandée : (?P<action>.+) \((?P<tool>[a-z_]+)\)$")
LEVEL_LINE = re.compile(r"^(?P<level>IRRÉVERSIBLE|PUBLIC|MODIFICATION) : (?P<consequence>.*)$")
ROW_LINE = re.compile(r"^\s+(?P<key>[^:]+?) : (?P<value>.*)$")
# Pauses annoncées par le limiteur Groq et le client LLM (temps restant affiché pendant la demande)
PAUSE_SECONDS = re.compile(r"(?:Pause de|nouvel essai dans) (\d+) s")
PAUSE_MINUTES = re.compile(r"\(dans (\d+) min\)")
STEP_LINE = re.compile(r"^\s{2}(?:\[[a-z_]+\] |Domaines : |Attention : )")
# Étape en cours, en clair, dans le bloc de progression (mise à jour en direct)
PHASE_START = "Demande envoyée…"
PHASE_ROUTING = "Choix du domaine…"
PHASE_THINKING = "Analyse de la demande…"
PHASE_WRITING = "Réponse en cours de rédaction…"
PHASE_CONFIRM = "En attente de ta confirmation"
READ_PHASES = {
    "get_page_info": "Lecture des informations de la page…", "get_post": "Lecture du post…",
    "get_post_reactions": "Lecture des réactions…", "list_albums": "Lecture des albums…",
    "list_comments": "Lecture des commentaires…", "list_conversation_messages": "Lecture des messages…",
    "list_conversations": "Lecture des conversations…", "list_photos": "Lecture des photos…",
    "list_posts": "Lecture des posts…", "list_product_feeds": "Lecture des flux de produits…",
    "list_product_sets": "Lecture des collections…", "list_scheduled_posts": "Lecture des posts programmés…",
    "list_videos": "Lecture des vidéos…", "search_products": "Recherche des produits…",
    "list_lead_forms": "Lecture des formulaires Lead Ads…", "list_test_leads": "Lecture des leads de test…",
    "list_form_leads": "Lecture des leads…", "list_campaigns": "Lecture des campagnes…",
    "list_ad_sets": "Lecture des ensembles de publicités…", "list_ads": "Lecture des publicités…",
}
PAUSE_LIMITS = (("par minute", "limite par minute"), ("par jour", "limite par jour"))
# Création réussie -> (lecture dont la carte est réutilisée, champs relus sur l'objet créé)
CREATED_CARDS = {"create_post": ("list_posts", POST_LIST_FIELDS),
                 "create_scheduled_photos_post": ("list_scheduled_posts", SCHEDULED_FIELDS),
                 "upload_photo": ("list_photos", PHOTO_FIELDS), "upload_photo_to_album": ("list_photos", PHOTO_FIELDS),
                 "create_product": ("search_products", PRODUCT_FIELDS),
                 "create_product_set": ("list_product_sets", PRODUCT_SET_FIELDS),
                 "create_lead_form": ("list_lead_forms", FORM_FIELDS),
                 "create_campaign": ("list_campaigns", CAMPAIGN_FIELDS),
                 "create_ad_set": ("list_ad_sets", AD_SET_FIELDS), "create_ad": ("list_ads", AD_FIELDS)}


def tool_phase(name: str) -> str:
    """Step shown while a tool runs, in plain French ("Lecture des conversations…").

    Args:
        name: Operation name.

    Returns:
        The phrase of a read, "Préparation : <action>…" for a write, or a generic phrase.
    """
    if name in READ_PHASES:
        return READ_PHASES[name]
    if name in WRITE_OPERATIONS:
        return f"Préparation : {WRITE_OPERATIONS[name][1]}…"
    return f"Appel de l'outil {name}…"


def pause_reason(line: str) -> str:
    """Limit named by a Groq pause line ("limite par minute", "limite par jour" or "limite").

    Args:
        line: Line of the limiter or of the LLM client.

    Returns:
        The words shown in "Pause Groq (…)".
    """
    return next((reason for words, reason in PAUSE_LIMITS if words in line), "limite")


def duration(seconds: float) -> str:
    """Short duration: "12 s", "1 min 05 s".

    Args:
        seconds: Seconds (rounded down, never negative).

    Returns:
        The duration in French.
    """
    seconds = max(int(seconds), 0)
    return f"{seconds} s" if seconds < 60 else f"{seconds // 60} min {seconds % 60:02d} s"


@dataclass
class ConfirmationView:
    """A confirmation text cut into the parts of its card (the full text stays available as is)."""

    level: str | None  # "IRRÉVERSIBLE", "PUBLIC" ou "MODIFICATION"
    consequence: str
    action: str
    tool: str | None
    banners: list[str]  # bandeau du compte publicitaire (SANDBOX…), avant l'action
    rows: list[tuple[str, str]]  # paramètres et valeurs lues avant l'écriture
    notes: list[str]  # autres lignes (ex. PROMOTION RETIRÉE)


def parse_confirmation(text: str) -> ConfirmationView:
    """Cut a confirmation text (Executor.confirmation_text) into title, level, banners and key / value rows.

    Args:
        text: The full text, as shown in the terminal.

    Returns:
        Its parts; a line that matches no pattern is kept in notes, so that nothing is lost.
    """
    level = action = tool = None
    consequence = ""
    banners, rows, notes = [], [], []
    for line in text.splitlines():
        if not line.strip():
            continue
        if found := ACTION_LINE.match(line):
            action, tool = found["action"], found["tool"]
        elif found := LEVEL_LINE.match(line):
            level, consequence = found["level"], found["consequence"]
        elif found := ROW_LINE.match(line):
            rows.append((found["key"].strip(), found["value"]))
        elif action is None:
            banners.append(line.strip())
        else:
            notes.append(line.strip())
    return ConfirmationView(level, consequence, action or "action", tool, banners, rows, notes)


@dataclass
class AccountPreview:
    """Names read in the background for the start screen (never an ID shown, never a token kept)."""

    done: bool = False
    failed: bool = False
    user_name: str | None = None
    pages: list[tuple[str, str]] = field(default_factory=list)  # (ID, nom) : l'ID ne sert qu'au choix

    @property
    def needs_choice(self) -> bool:
        """Whether the start screen must offer a choice of page.

        Returns:
            True only with several pages and an empty FB_PAGE_ID.
        """
        return not config.FB_PAGE_ID and len(self.pages) > 1

    def page_name(self) -> str | None:
        """Name of the page the session will use, when it is known without asking.

        Returns:
            The page of FB_PAGE_ID, or the only page of the account, else None.
        """
        if config.FB_PAGE_ID:
            return next((name for page_id, name in self.pages if page_id == str(config.FB_PAGE_ID)), None)
        return self.pages[0][1] if len(self.pages) == 1 else None


def read_account(preview: AccountPreview) -> None:
    """Read the user name (GET me?fields=name) and the page names (GET me/accounts): read-only, FB_USER_TOKEN.

    Runs in a background thread after the first screen; any failure only keeps "Page configurée" (the
    start button then shows the detailed error). The page tokens returned by Facebook are not kept.

    Args:
        preview: Filled in place; done is set last.
    """
    try:
        token = config.FB_USER_TOKEN
        if not token:
            preview.failed = True
            return
        me = call_graph("GET", "me", token, params={"fields": "name"}, error_message="Lecture du profil impossible.")
        if me.get("status") == "success" and isinstance(me.get("data"), dict):
            preview.user_name = me["data"].get("name") or None
        pages = authenticate(token, "1")
        if pages.get("status") == "success":
            preview.pages = [(str(p.get("id")), str(p.get("name") or "Page sans nom"))
                             for p in (pages["data"] or {}).get("data", []) if isinstance(p, dict)]
        else:
            preview.failed = True
    except Exception:  # aperçu seulement : jamais de détail ici (il pourrait citer une valeur de session)
        preview.failed = True
    finally:
        preview.done = True


def start_account_preview() -> AccountPreview:
    """Start reading the account names in a background thread.

    Returns:
        The preview, filled when the thread ends (done=True).
    """
    preview = AccountPreview()
    threading.Thread(target=read_account, args=(preview,), daemon=True, name="account-preview").start()
    return preview


def ads_configured(registry=None) -> bool:
    """Whether the ad domains are active (start screen: the "Publicités" card is greyed otherwise).

    Args:
        registry: Tools to look at (the page gives a cached one); default: session_registry().

    Returns:
        True with AD_ACCOUNT_ID and a valid AD_ACCOUNT_MODE (no request is sent).
    """
    return bool(set(AD_DOMAINS) & set((registry or session_registry()).available_domains))


def page_hint(known_name: str | None = None) -> str:
    """Text of the "Page" field of the start screen, shown at once (no request, never a value of the .env).

    Args:
        known_name: Name of the page if already known in this tab (previous session), else None.

    Returns:
        The page name, or "Page configurée".
    """
    return known_name or "Page configurée"


def split_error(message: str) -> tuple[str, str]:
    """Short message for the screen, and the technical detail for a folded block.

    Args:
        message: Message of a SessionError or of a configuration error.

    Returns:
        (short sentence, detail) ; the detail is "" when there is none.
    """
    index = message.find("Facebook :")
    if index < 0:
        return message, ""
    short = message[:index].rstrip(" (").strip()
    detail = message[index:].strip()
    if message[:index].rstrip().endswith("(") and detail.endswith(")"):
        detail = detail[:-1]
    return short, detail


def without_card_ids(answer: str, ids) -> str:
    """The answer without the IDs that already have their « ID » button on a card of the exchange.

    A line that only gives the ID (« - ID : 699…_122… ») is removed; « (ID 123…) » and « ID : 123… » in a
    sentence are removed; any other copy of the ID too. Other IDs (an object without a card) stay, with
    their copy button under the answer.

    Args:
        answer: Answer shown above the cards.
        ids: IDs of the cards of the exchange.

    Returns:
        The answer, with tidy spaces.
    """
    text = answer or ""
    for object_id in sorted({str(i) for i in ids if i}, key=len, reverse=True):
        found = re.escape(object_id).replace("_", r"\\?_")  # aussi « 699\_122 » (Markdown)
        mark = r"[`*]*"
        text = re.sub(rf"^[ \t]*(?:[-*•][ \t]*)?{mark}ID{mark}[ \t]*:?[ \t]*{mark}{found}{mark}[ \t]*\n?", "", text,
                      flags=re.M)
        text = re.sub(rf"[ \t]*\({mark}(?:ID[ \t]*:?[ \t]*)?{mark}{found}{mark}\)", "", text)
        text = re.sub(rf"(?:\bID[ \t]*:?[ \t]*)?{mark}{found}{mark}", "", text)
    if text == (answer or ""):
        return text
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"[ \t]+([.,])", r"\1", text)  # jamais devant « : » ni « ? » (espace du français)
    return text.strip()


def object_kind(tool: str) -> str:
    """Kind of the objects returned by a tool, from its name.

    Args:
        tool: Operation name (e.g. "create_ad_set").

    Returns:
        A French label ("Ensemble de publicités"), or "Objet".
    """
    return next((label for key, label in KINDS if key in tool), "Objet")


def ask_page_from(page_id: str | None):
    """Page choice for open_session: the page already chosen, or PageChoiceNeeded.

    Args:
        page_id: ID of the page chosen on the start screen, or None.

    Returns:
        A function of the pages that returns the chosen one.
    """
    def ask(pages: list[dict]) -> dict:
        """Return the chosen page, or ask the start screen to show the choice."""
        chosen = next((p for p in pages if page_id and str(p.get("id")) == str(page_id)), None)
        if chosen is None:
            raise PageChoiceNeeded(pages)
        return chosen
    return ask


def make_llm(settings):
    """LLM client of the web session (replaced by a fake one in the tests).

    Args:
        settings: LLM settings.

    Returns:
        None: build_agent then creates the real LLMClient.
    """
    return None


class PageChoiceNeeded(Exception):
    """Several pages and FB_PAGE_ID is empty: the start screen must let the user choose one."""

    def __init__(self, pages: list[dict]) -> None:
        """Keep only the ID and the name of each page (never its token)."""
        super().__init__("choix de la page nécessaire")
        self.pages = [(str(p.get("id")), str(p.get("name") or p.get("id"))) for p in pages]


@dataclass
class Confirmation:
    """A write waiting for the buttons, then its outcome."""

    text: str
    outcome: str | None = None  # "accepted", "refused", "timeout" ou "cancelled"
    dry_run: bool = False  # mode de la session quand la carte est affichée (rappelé sur la carte)
    event: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def label(self) -> str:
        """Text shown once answered.

        Returns:
            "Confirmé.", "Refusé : rien n'a été fait.", TIMEOUT_MESSAGE, or "" while waiting.
        """
        return OUTCOME_LABELS.get(self.outcome or "", "")

    @property
    def view(self) -> ConfirmationView:
        """The parts of the card (level, title, banners, rows).

        Returns:
            parse_confirmation(self.text).
        """
        return parse_confirmation(self.text)


@dataclass
class Turn:
    """One exchange of the chat: the request, its confirmations, its answer and its technical lines."""

    request: str
    answer: str | None = None
    details: list[str] = field(default_factory=list)
    confirmations: list[Confirmation] = field(default_factory=list)
    leads: list[str] = field(default_factory=list)
    ids: dict[str, str] = field(default_factory=dict)  # ID -> type d'objet, lus dans les résultats
    status_line: str = ""
    cardsets: list = field(default_factory=list)  # cartes visuelles des lectures (web/cards.py)
    kind: str = "request"  # "request", ou "help" / "reset" : notification du système, pas un message de l'utilisatrice
    notified: bool = False  # la notification (toast) de /reset ou /aide a été affichée
    hidden: bool = False  # aide fermée par son bouton « Fermer l'aide »
    pause_until: float | None = None  # fin de la pause Groq en cours (horloge monotone)
    pause_total: int | None = None  # durée annoncée de cette pause (barre de progression)
    pause_reason: str = ""  # "limite par minute", "limite par jour" ou "limite"
    phase: str = PHASE_START  # étape en cours, en clair
    started: float | None = None  # début et fin de la demande (horloge monotone de la session)
    ended: float | None = None
    failed: bool = False  # erreur (LLM injoignable, erreur inattendue) : croix au lieu de la coche

    @property
    def command(self) -> bool:
        """Whether this exchange is a command (/aide, /reset) answered by the code.

        Returns:
            True for "help" and "reset".
        """
        return self.kind != "request"

    def steps(self) -> list[str]:
        """Steps of the request for the progress block: domains, tools called, warnings (not the items received).

        Returns:
            The step lines, stripped.
        """
        return [line.strip() for line in self.details if STEP_LINE.match(line)]

    @property
    def done(self) -> bool:
        """Whether the answer is there.

        Returns:
            True once the request is finished (answered, cancelled or failed).
        """
        return self.answer is not None

    def copyable_ids(self) -> list[tuple[str, str]]:
        """IDs cited in the answer, with a copy button (posts, products, forms, campaigns, ad sets, ads).

        Returns:
            (kind, ID) pairs, in the order of the answer, without duplicates.
        """
        cited = dict.fromkeys(ID_TOKEN.findall(self.answer or ""))
        return [(self.ids[token], token) for token in cited if self.ids.get(token) in COPY_KINDS]


class WebSession:
    """The agent of one web session, and the exchanges shown by the page."""

    def __init__(self, dry_run: bool = False, page_id: str | None = None, log_dir=None,
                 confirm_timeout: float = CONFIRM_TIMEOUT, clock=time.monotonic, user_name: str | None = None) -> None:
        """Open the session (2 or 3 Graph API requests) and build the agent.

        user_name is only shown in the header ("Connecté en tant que …"), read by the start screen.

        Raises:
            ValueError: Invalid LLM settings.
            SessionError: The session could not start (message in French).
            PageChoiceNeeded: Several pages, none chosen yet.
        """
        self.lock = threading.Lock()
        self.cancellation = Cancellation()
        self.confirm_timeout, self.clock = confirm_timeout, clock
        self.turns: list[Turn] = []
        self.notices: list[str] = []  # messages de l'ouverture de la session
        self.pending: Confirmation | None = None
        self.thread: threading.Thread | None = None
        self.current: Turn | None = None
        self.dry_run = dry_run
        self.user_name = user_name
        settings = load_llm_settings()
        self.settings = settings
        self.session = open_session(ask_page_from(page_id), notify=self.notices.append)
        self.page_name = self.session.page_name
        self.journal = SessionLog(secrets=self.session.secrets | {settings.api_key},
                                  **({"log_dir": log_dir} if log_dir else {}))
        self.registry = session_registry()
        self.agent = build_agent(settings, self.session, self.journal, self._confirm, self._out, dry_run=dry_run,
                                 llm=make_llm(settings), sleep=self.cancellation.sleep, cancel_hint=BUTTON_HINT,
                                 registry=self.registry)
        self.agent.full_leads = False  # réponses des leads dans leur bloc replié, pas dans les détails
        self.agent.cards_mode = True  # consigne du prompt : une phrase de résumé au-dessus des cartes
        self.agent.on_tool_result = self._on_result
        chat = self.agent.llm.chat

        def cancellable_chat(*args, **kwargs):
            """Stop between two steps of the request when it was cancelled (before calling the LLM)."""
            self.cancellation.check()
            routing = kwargs.get("tool_choice") == "required"  # routage : seul appel en « required »
            self._set_phase(PHASE_ROUTING if routing else PHASE_WRITING if self.agent.request_tool_calls
                            else PHASE_THINKING)
            return chat(*args, **kwargs)

        self.agent.llm.chat = cancellable_chat
        execute = self.agent.executor.execute

        def tracked_execute(name, *args, **kwargs):
            """Show the tool running, in plain French, in the progress block."""
            self._set_phase(tool_phase(name))
            return execute(name, *args, **kwargs)

        self.agent.executor.execute = tracked_execute
        self.journal.write("start", interface="web", page=self.page_name, model=settings.model,
                           router_model=settings.first_call_model, dry_run=dry_run, verbose=False,
                           long_lived=self.session.long_lived)
        self.closed = False

    # --- État lu par la page ------------------------------------------------------------------------
    @property
    def busy(self) -> bool:
        """Whether a request is running.

        Returns:
            True while the thread of a request is alive.
        """
        return self.thread is not None and self.thread.is_alive()

    @property
    def ready_line(self) -> str:
        """First line of the chat (the models are in the quota panel and in the log).

        Returns:
            "Agent prêt sur la page « … »."
        """
        return f"Agent prêt sur la page « {self.page_name} »."

    def objects_by_kind(self) -> dict[str, list[dict]]:
        """Panel "Activité de la session": every kind, even without object.

        Returns:
            {kind: objects} in the order of PANEL_KINDS; each object has kind, id (None when
            simulated), text, time, simulated and state (None for a creation, "publiée", "envoyé",
            "changée", "modifié"…, then "supprimé" or "archivé").
        """
        objects = list(self.agent.session_objects)
        return {kind: [o for o in objects if o["kind"] == kind] for kind in PANEL_KINDS}

    def recent_objects(self) -> list[dict]:
        """Panel "Activité de la session", most recent first (one line per write, deletions included).

        Returns:
            The objects of objects_by_kind, newest first; a deleted object of the session stays at the place of
            its creation, with its new state.
        """
        return [o for o in reversed(self.agent.session_objects) if o["kind"] in PANEL_KINDS]

    def quota(self) -> list[tuple[str, int, int, str | None]]:
        """Panel "Quota Groq": tokens left today, per model, and the daily quota (progress bars).

        The local estimate (logs since midnight), replaced by Groq's own count once a 429 on the tokens per day
        gave it ("Used 199135", minus the tokens used since).

        Returns:
            (short model name, tokens left, tokens per day, "HH:MM" of Groq's count or None for the estimate).
        """
        reported = self.agent.groq_quota()
        lines = []
        for model, left in self.agent.quota_left().items():
            if model in reported:
                groq_left, limit, at = reported[model]
                lines.append((model.split("/")[-1] or "modèle", groq_left, limit, at))
            else:
                lines.append((model.split("/")[-1] or "modèle", left, self.agent.tokens_per_day, None))
        return lines

    @property
    def ads_badge(self) -> str | None:
        """Badge of the ad account mode in the header.

        Returns:
            "SANDBOX", "SANS PAIEMENT", or None when the campaigns are disabled.
        """
        mode = self.registry.ads_mode
        return ADS_MODE_BADGES.get(mode) if mode and set(AD_DOMAINS) & set(self.registry.available_domains) else None

    def suggestions(self) -> dict[str, list[tuple[str, str]]]:
        """Suggestions grouped by domain, only the groups and requests whose domain is active.

        Returns:
            {group: [(short label, full request sent)]}, in the order Page, Messenger, Catalogue, Lead Ads,
            Publicités; a group without any active request is left out.
        """
        active = set(self.registry.available_domains)
        groups = {group: [(label, text) for label, text, domain in items if domain in active]
                  for group, items in SUGGESTIONS.items()}
        return {group: items for group, items in groups.items() if items}

    @staticmethod
    def suggestion_card(label: str) -> tuple[str, str]:
        """Icon and one-line description of a suggestion card.

        Args:
            label: Short label of the suggestion.

        Returns:
            (":material/…:" icon, description in French).
        """
        return SUGGESTION_CARDS[label]

    def group_icon(self, group: str) -> str:
        """Material icon of a domain group (same as the start screen and the sidebar).

        Args:
            group: "Page", "Messenger", "Catalogue", "Lead Ads" or "Publicités".

        Returns:
            The ":material/…:" icon.
        """
        return next(icon for title, icon, _ in DOMAIN_GROUPS if title == group)

    def domain_groups(self) -> list[tuple[str, str, list[str]]]:
        """Panel "Domaines actifs": the five groups of the start screen, with their active domains.

        Returns:
            (title, Material icon, labels of its active domains) triples; an empty list means not configured.
        """
        active = set(self.registry.available_domains)
        return [(title, icon, [DOMAINS[d][0] for d in domains if d in active])
                for title, icon, domains in DOMAIN_GROUPS]

    def help_sections(self) -> dict:
        """Help of the page, in short sections (commands and buttons, examples, active domains).

        Returns:
            {"commands": [(button, command, effect)], "suggestions": {group: [(label, text)]}, "domains": [...],
             "disabled": [...], "confirm": str, "limits": str}.
        """
        labels, notes, mode = self.domains()
        return {"commands": list(HELP_COMMANDS), "suggestions": self.suggestions(), "domains": labels,
                "disabled": notes + ([mode] if mode else []),
                "confirm": f"Toute action qui modifie la page, le catalogue ou les campagnes est affichée et attend "
                           f"ta confirmation {HOW_TO_CONFIRM}. Sans réponse en {int(CONFIRM_TIMEOUT // 60)} min : refus.",
                "limits": f"Au plus {self.agent.max_turns} étapes et 3 actions par demande ; une demande à la fois."}

    def pause_left(self) -> int | None:
        """Seconds left in the Groq pause of the running request (progress block).

        Returns:
            The seconds, or None when no pause is running.
        """
        turn = self.current
        if turn is None or turn.done or turn.pause_until is None:
            return None
        left = math.ceil(turn.pause_until - self.clock())
        return left if left > 0 else None

    def pause(self) -> tuple[int, int, str] | None:
        """Groq pause of the running request, for the countdown and its progress bar.

        Returns:
            (seconds left, seconds announced, "limite par minute" / "limite par jour" / "limite"), or None.
        """
        left = self.pause_left()
        turn = self.current
        if left is None or turn is None:
            return None
        return left, max(turn.pause_total or left, left), turn.pause_reason or "limite"

    def elapsed(self, turn: Turn) -> str:
        """Time taken by a request: still running, or until its answer.

        Args:
            turn: The exchange.

        Returns:
            "12 s", "1 min 05 s", or "" when the request has no start time (command, old exchange).
        """
        if turn.started is None:
            return ""
        return duration((turn.ended if turn.ended is not None else self.clock()) - turn.started)

    def phase(self, turn: Turn) -> str:
        """Step of the running request shown as the title of the progress block.

        Args:
            turn: The running exchange.

        Returns:
            PHASE_CONFIRM while a confirmation waits, otherwise the step in plain French.
        """
        return PHASE_CONFIRM if self.pending is not None and turn is self.current else turn.phase

    def domains(self) -> tuple[list[str], list[str], str | None]:
        """Panel "Domaines actifs".

        Returns:
            (labels of the active domains, lines for the disabled ones, label of the ad account mode or None).
        """
        mode = self.registry.ads_mode
        return (active_domain_labels(self.registry), disabled_domain_notes(self.registry),
                ADS_MODE_LABELS.get(mode) if mode and set(AD_DOMAINS) & set(self.registry.available_domains)
                else None)

    def help(self) -> str:
        """Text of the "Aide" button and of /aide.

        Returns:
            The help of the terminal, with the buttons instead of the commands and of (o/n).
        """
        return help_text(self.registry, head=WEB_HELP_HEAD, how_to_confirm=HOW_TO_CONFIRM)

    # --- Actions de la page -------------------------------------------------------------------------
    def submit(self, text: str) -> bool:
        """Start a request (in its thread) or run a command.

        Args:
            text: Text typed in the chat input.

        Returns:
            True if something was added to the chat (False: empty text, or a request already running).
        """
        text = text.strip()
        if not text or self.busy or self.closed:
            return False
        command = text.lower()
        if command == "/aide":
            self.turns.append(Turn(text, answer=self.help(), kind="help"))
            return True
        if command == "/reset":
            self.reset()
            return True
        turn = Turn(text, started=self.clock())
        self.turns.append(turn)
        self.current = turn
        self.cancellation.clear()
        self.thread = threading.Thread(target=self._run, args=(turn,), daemon=True, name="agent-request")
        self.thread.start()
        return True

    def answer(self, accepted: bool) -> bool:
        """Answer the confirmation shown (button "Confirmer" or "Refuser").

        Args:
            accepted: True for "Confirmer".

        Returns:
            True if a confirmation was waiting (False: already answered, timed out or cancelled).
        """
        with self.lock:
            pending = self.pending
            if pending is None or pending.outcome is not None or self.cancellation.cancelled:
                return False  # déjà répondu, ou demande annulée : l'annulation l'emporte
            pending.outcome = "accepted" if accepted else "refused"
        pending.event.set()
        return True

    def cancel(self) -> None:
        """Button "Annuler la demande": the request stops at its next wait, confirmation or step.

        A confirmation shown at that moment is closed at once as "cancelled" (never as a refusal): the
        request then ends with "Demande annulée : rien n'a été modifié." and the model is not called again.
        """
        if not self.busy:
            return
        self.cancellation.cancel()
        with self.lock:
            pending = self.pending
            if pending is not None and pending.outcome is None:
                pending.outcome = "cancelled"
        if pending is not None:
            pending.event.set()

    def set_dry_run(self, dry_run: bool) -> bool:
        """Switch "Mode dry-run" of the ⋮ menu: change the mode without ending the session.

        Refused while a request runs (a confirmation can only wait inside a request): the mode of a
        write shown on a card never changes under it. The next request gets the matching system prompt.

        Args:
            dry_run: True for dry-run (no write sent), False for the real mode.

        Returns:
            True if the mode is now the one asked (False: a request is running, nothing changed).
        """
        with self.lock:
            if self.busy or self.pending is not None or self.closed:
                return dry_run == self.dry_run
            if dry_run != self.dry_run:
                self.dry_run = self.agent.dry_run = self.agent.executor.dry_run = dry_run
                self.journal.write("mode", dry_run=dry_run)
        return True

    def reset(self) -> None:
        """Button "Vider l'historique" (/reset)."""
        if self.busy:
            return
        self.agent.reset()
        self.turns.append(Turn("/reset", answer="Historique vidé.", kind="reset"))

    def close(self, wait: float = 5.0) -> None:
        """Button "Terminer la session": cancel the request, close the log, forget the tokens.

        Args:
            wait: Seconds given to a running request to stop.
        """
        if self.closed:
            return
        self.cancel()
        if self.thread is not None:
            self.thread.join(wait)
        self.journal.write("end")
        self.session.close()
        self.closed = True

    def wait(self, timeout: float = 10.0) -> None:
        """Wait for the end of the running request (tests).

        Args:
            timeout: Maximum seconds.
        """
        if self.thread is not None:
            self.thread.join(timeout)

    # --- Fonctions données à l'agent (fil de la demande) -------------------------------------------
    def _run(self, turn: Turn) -> None:
        """Handle one request; a cancellation or an unexpected error ends it with a message."""
        failed = False
        try:
            answer = self.agent.handle(turn.request).strip() or EMPTY_ANSWER
        except RequestCancelled:
            answer = self.agent.cancel_request(CANCELLED_BY_BUTTON)
        except Exception as exc:  # jamais le détail à l'écran : il peut citer une valeur de la session
            self.journal.write("error", where="web", error=type(exc).__name__, message=str(exc)[:300])
            answer = f"Erreur inattendue ({type(exc).__name__}) : voir le journal de la session."
            if self._action_not_proposed():
                answer += " Rien n'a été fait."
            failed = True
        try:
            turn.status_line = self.agent.status_line()
        except Exception:  # la ligne d'état ne doit jamais cacher la réponse
            turn.status_line = ""
        answer = self._card_answer(turn, answer)
        # un ID qui a son bouton « ID » sur une carte n'est jamais écrit dans la réponse
        answer = without_card_ids(answer, {card.id for cardset in turn.cardsets for card in cardset.cards if card.id})
        # cartes d'une lecture affichées après l'échec : pas une erreur ; demande d'action arrêtée : une erreur
        turn.failed = failed or answer.startswith(LLM_FAILED) or bool(getattr(self.agent, "request_stopped", None))
        turn.ended = self.clock()
        turn.answer = answer  # en dernier : la page lit « done » sur la réponse

    def _action_not_proposed(self) -> bool:
        """Whether the request asked for an action and ended before any confirmation (nothing done).

        Returns:
            Agent._stopped_before_proposal(), False for an agent without it.
        """
        check = getattr(self.agent, "_stopped_before_proposal", None)
        return bool(check()) if callable(check) else False

    def _set_phase(self, phase: str) -> None:
        """Step of the running request (thread of the request)."""
        if self.current is not None and not self.current.done:
            self.current.phase = phase

    def _card_answer(self, turn: Turn, answer: str) -> str:
        """With cards, the answer is one summary sentence: the cards show the items, never a list in text.

        Kept whole when a write was confirmed or refused (its outcome matters), or when a text looked like
        an instruction to the agent (the warning must stay). Hidden ("") when every list is empty: the empty
        card already says so ("Aucun flux de produits."), never twice.

        Args:
            turn: The request just answered.
            answer: Answer of the agent.

        Returns:
            The answer to show above the cards ("" : nothing above them).
        """
        if turn.confirmations:
            return self._write_answer(turn, answer)
        if not turn.cardsets:
            return answer
        if getattr(self.agent, "request_stopped", None) or self._action_not_proposed():
            # demande d'action sans proposition (limite Groq, erreur, question de l'agent) : sa réponse entière,
            # jamais le résumé d'une lecture faite en chemin ; les cartes restent dessous
            return answer
        empty = not any(cardset.cards for cardset in turn.cardsets)
        summary = turn.cardsets[-1].summary()
        if answer.startswith(LLM_FAILED):  # l'outil a réussi : les cartes et une phrase du code, jamais l'échec
            return "" if empty else summary
        if getattr(self.agent, "request_suspicious", None):
            return answer
        if empty:
            return ""
        cards_shown = [card for cardset in turn.cardsets for card in cardset.cards]
        return summary_sentence(answer, summary, ids=[card.id for card in cards_shown],
                                titles=[card.title for card in cards_shown])

    def _out(self, line: str) -> None:
        """Technical line of the agent (tools, items received, pauses): in the "Détails" of the exchange."""
        turn = self.current
        if turn is None or turn.done:
            self.notices.append(str(line))
            return
        turn.details.append(str(line))
        seconds = PAUSE_SECONDS.search(str(line))
        minutes = PAUSE_MINUTES.search(str(line))
        if seconds or minutes:  # pause Groq : compte à rebours et barre dans le bloc de progression
            turn.pause_total = int(seconds[1]) if seconds else int(minutes[1]) * 60
            turn.pause_until = self.clock() + turn.pause_total
            turn.pause_reason = pause_reason(str(line))
        else:
            turn.pause_until = turn.pause_total = None

    def _confirm(self, text: str) -> bool:
        """Show the confirmation and wait for a button, a cancellation or the timeout.

        Raises:
            RequestCancelled: The request was cancelled before or during the wait.
        """
        self.cancellation.check()
        confirmation = Confirmation(text, dry_run=self.dry_run)
        with self.lock:
            if self.current is not None:
                self.current.confirmations.append(confirmation)
            self.pending = confirmation
        deadline = self.clock() + self.confirm_timeout
        try:
            while not confirmation.event.wait(POLL):
                with self.lock:
                    if confirmation.outcome is not None:
                        break
                    if self.cancellation.cancelled:
                        confirmation.outcome = "cancelled"
                        raise RequestCancelled()
                    if self.clock() >= deadline:
                        confirmation.outcome = "timeout"
                        return False
            if confirmation.outcome == "cancelled" or self.cancellation.cancelled:
                confirmation.outcome = "cancelled"  # « Annuler la demande » : jamais lu comme un refus
                raise RequestCancelled()
            return confirmation.outcome == "accepted"
        finally:
            with self.lock:
                self.pending = None

    def links(self) -> dict:
        """IDs of the session used by the links of the cards to the Meta interface (never shown as text).

        Returns:
            {"catalog", "page", "ad_account", "ads_mode"}.
        """
        context = self.session.context
        return {"catalog": context.catalog_id, "page": context.page_id, "ad_account": context.ad_account_id,
                "ads_mode": self.registry.ads_mode}

    def _created_card(self, name: str, data):
        """Card of an object just created (post, product, form, campaign…), read again with the fields of its list.

        Args:
            name: Write operation executed.
            data: Its "data" (the new ID in "id").

        Returns:
            A CardSet with one card, or None (not a creation, no ID, or the object could not be read).
        """
        if name not in CREATED_CARDS or not isinstance(data, dict) or not isinstance(data.get("id"), (str, int)):
            return None
        list_tool, fields = CREATED_CARDS[name]
        read = call_graph("GET", str(data["id"]), self.agent.executor._token_for(name), params={"fields": fields},
                          error_message="Lecture de l'objet créé impossible.")
        found = read.get("data") if read.get("status") == "success" else None
        if not isinstance(found, dict) or not found.get("id"):
            return None
        cardset = build_cards(list_tool, {"status": "success", "data": {"data": [found]}}, self.links())
        if cardset is not None:
            cardset.created = True
        return cardset

    def _modified_product_card(self, turn: Turn, arguments: dict, output: dict) -> None:
        """After update_product: the product card shows the product read again on Facebook, not the search made
        before the change (on a promotion, it showed the old price without the struck-out price).

        The card of the product in this request is replaced; without one (search in an earlier request), the
        card is added. When the product cannot be read again, the prices read by the executor are used.

        Args:
            turn: The request running.
            arguments: Arguments really sent (product_id, data).
            output: Output of update_product, with the prices read again in "reread".
        """
        product_id = safe_id(arguments.get("product_id"))
        if not product_id:
            return
        read = call_graph("GET", product_id, self.agent.executor._token_for("update_product"),
                          params={"fields": PRODUCT_FIELDS}, error_message="Relecture du produit impossible.")
        found = read.get("data") if read.get("status") == "success" else None
        fresh = build_cards("search_products", {"status": "success", "data": {"data": [found]}}, self.links()) \
            if isinstance(found, dict) and found.get("id") else None
        stale = [(cardset, index) for cardset in turn.cardsets for index, card in enumerate(cardset.cards)
                 if card.id == product_id and cardset.tool == "search_products"]
        if fresh is not None and fresh.cards:
            for cardset, index in stale:
                cardset.cards[index] = fresh.cards[0]
            if not stale:
                fresh.created = True  # carte relue après l'écriture, comme pour une création
                turn.cardsets.append(fresh)
            return
        reread = output.get("reread")
        if not isinstance(reread, dict) or "error" in reread:
            return
        for cardset, index in stale:  # relecture complète impossible : les prix relus par l'exécuteur
            columns = {"price": str(reread.get("price") or cardset.cards[index].columns.get("price") or "")}
            if reread.get("sale_price"):
                columns["sale_price"] = str(reread["sale_price"])
            cardset.cards[index].columns = columns

    def _write_answer(self, turn: Turn, answer: str) -> str:
        """After confirmed writes: one sentence of the code ("Post publié.", "Post supprimé.") when the answer
        cites an ID or is longer than a sentence. The whole sentence is replaced, an ID is never cut.

        An object created without a card (not read again) keeps its full ID in the sentence.

        Args:
            turn: The request just answered.
            answer: Answer of the agent.

        Returns:
            The answer to show.
        """
        actions = list(getattr(self.agent, "request_actions", None) or [])
        if not actions or getattr(self.agent, "request_failed_writes", None) \
                or getattr(self.agent, "request_suspicious", None):
            return answer  # refus, erreur ou texte suspect : la réponse détaillée de l'agent reste
        carded = {card.id for cardset in turn.cardsets for card in cardset.cards if card.id}
        sentences, ids = [], set(carded)
        for name, arguments, output, status in actions:
            data = (output or {}).get("data") if isinstance(output, dict) else None
            new_id = str(data["id"]) if isinstance(data, dict) and isinstance(data.get("id"), (str, int)) else None
            ids |= {new_id} if new_id else set()
            ids |= {str(v) for k, v in arguments.items() if k.endswith("_id") and isinstance(v, (str, int))}
            label = DONE_LABELS.get(name, f"Action faite : {WRITE_OPERATIONS.get(name, ('', name))[1]}")
            simulated = " (simulé, dry-run)" if status == "simulated" else ""
            shown = f" (ID {new_id})" if new_id and new_id not in carded and name in CREATED_CARDS else ""
            sentences.append(f"{label}{simulated}{shown}.")
        sentence = " ".join(dict.fromkeys(sentences))
        return summary_sentence(answer, sentence, ids=sorted(ids))

    def _on_result(self, name: str, result) -> None:
        """Keep the IDs of a result (copy buttons) and the full answers of the leads (folded block)."""
        turn = self.current
        output = getattr(result, "output", None)
        if turn is None or not isinstance(output, dict) or output.get("status") != "success":
            return
        data = output.get("data")
        items = data if isinstance(data, list) else data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            items = [data] if isinstance(data, dict) else []
        cardset = build_cards(name, output, self.links())
        if cardset is None and getattr(result, "status", None) == "executed":
            cardset = self._created_card(name, data)
        if cardset is not None:
            turn.cardsets.append(cardset)
        if name == "update_product" and getattr(result, "status", None) == "executed":
            self._modified_product_card(turn, getattr(result, "arguments", None) or {}, output)
        kind = object_kind(name)
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), (str, int)):
                turn.ids.setdefault(str(item["id"]), kind)
        if name in LEAD_TOOLS:
            turn.leads += [lead_line(item) for item in items
                           if isinstance(item, dict) and isinstance(item.get("field_data"), list)]
