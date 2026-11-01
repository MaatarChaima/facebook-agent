"""Generate the LLM tools (OpenAI "tools" format, JSON Schema) from the operation docstrings.

Nothing is written by hand: every operation tool comes from extract_function_doc_info().
The parameters injected by the code (page_id, page_token, access_token, catalog_id) never
appear in a tool: the LLM cannot see or choose them.

Strategy (rate limit of 8,000 tokens per minute): the LLM first chooses one or more domains
with select_domains, then only receives the tools of those domains, plus change_domain and
the tools needed in every domain.
"""
import inspect
import json
import re
from typing import Callable

from facebook_agent.ads_safety import AD_ACCOUNT_MODES
from facebook_agent.extract_function_doc_info import discover_operations, extract_function_doc_info

# Paramètres fournis par le code (contexte de session), jamais par le LLM
INJECTED_PARAMS = ("page_id", "page_token", "access_token", "catalog_id", "ad_account_id")
LEAD_OPERATIONS = ("list_lead_forms", "create_lead_form", "archive_lead_form", "create_test_lead", "list_test_leads",
                   "delete_test_lead", "list_form_leads")
# Campagnes : outils seulement avec un AD_ACCOUNT_MODE valide (sandbox ou no_payment) ; create_ad retirée en
# no_payment, où Meta refuse toute publicité
AD_OPERATIONS = ("list_campaigns", "create_campaign", "update_campaign", "delete_campaign", "list_ad_sets",
                 "create_ad_set", "update_ad_set", "delete_ad_set", "list_ads", "create_ad", "update_ad", "delete_ad")
NO_PAYMENT_EXCLUDED = ("create_ad",)
# Opérations jamais exposées : l'authentification est faite par le code au démarrage
EXCLUDED_OPERATIONS = ("authenticate",)
# Paramètres présentés au LLM sous une autre forme, convertis par l'exécuteur
DATETIME_FORMAT = "YYYY-MM-DD HH:MM"
DATETIME_PARAMS = ("publish_at",)

JSON_TYPES = {"str": "string", "int": "integer", "float": "number", "bool": "boolean",
              "list": "array", "dict": "object"}

# Domaines : nom donné au LLM -> (libellé affiché, sous-paquets d'opérations)
DOMAINS = {
    "posts": ("Posts", ("posts",)),
    "comments": ("Commentaires et modération", ("comments", "users")),
    "photos": ("Photos et couverture", ("photos",)),
    "videos": ("Vidéos", ("videos",)),
    "messenger": ("Messenger", ("conversations",)),
    "products": ("Catalogue : produits", ("products",)),
    "product_sets": ("Catalogue : product sets", ("product_sets",)),
    "product_feeds": ("Catalogue : feeds", ("product_feeds",)),
    "leads": ("Lead Ads", ("leads",)),
    "campaigns": ("Campagnes et ensembles", ("campaigns", "ad_sets")),
    "ads": ("Publicités", ("ads",)),
    "boost": ("Booster un post", ()),  # jeu réduit : ses outils sont BOOST_TOOLS (aucun sous-paquet propre)
}
AD_DOMAINS = ("campaigns", "ads")  # proposés seulement avec un AD_ACCOUNT_MODE valide
BOOST = "boost"
# Booster un post : campagne, ensemble puis publicité (3 écritures, la limite par demande), et le post à lire
BOOST_WRITES = ("create_campaign", "create_ad_set", "create_ad")
BOOST_TOOLS = (*BOOST_WRITES, "list_posts")
ALWAYS_AVAILABLE = ("get_page_info",)  # petits outils utiles dans tous les domaines
# Lectures ajoutées à un domaine pour retrouver l'objet visé (« les commentaires de mon post de test »)
DOMAIN_READ_HELPERS = {"comments": ("list_posts", "get_post"), "product_sets": ("search_products",),
                       "ads": ("list_ad_sets", "list_posts")}  # l'ensemble parent, le post à mettre en publicité
MAX_DOMAIN_TOKENS = 2500  # taille maximale des outils d'un domaine (limite Groq de 8 000 tokens par minute)
SELECT_DOMAINS = "select_domains"
CHANGE_DOMAIN = "change_domain"
CHAT_ONLY = "chat_only"  # 1er appel : seule échappatoire à l'appel obligatoire d'un outil
CHAT_KINDS = ("greeting", "question_about_agent", "out_of_scope", "impossible_action")
TOOL_NAME = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _summary(description: str) -> str:
    """First sentence of an operation description (the details stay in the docstring)."""
    first_paragraph = description.strip().split("\n\n")[0].replace("\n", " ")
    match = re.match(r"(.+?\.)(\s|$)", first_paragraph)
    return match.group(1) if match else first_paragraph


def _property(name: str, info: dict) -> dict:
    """JSON Schema of one documented parameter or sub-key."""
    if name in DATETIME_PARAMS:
        return {"type": "string",
                "description": f"Local date and time, format {DATETIME_FORMAT} (e.g. 2026-12-31 14:30).",
                "pattern": r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$"}
    base_type = info["type"].split("[")[0]
    schema = {"type": JSON_TYPES.get(base_type, "string"), "description": info["desc"]}
    if info.get("example") and schema["type"] in ("array", "object"):
        schema["description"] += f" Example: {info['example']}"  # forme attendue d'une liste ou d'un dict
    if info.get("choices"):
        schema["enum"] = list(info["choices"])
    if schema["type"] == "array":
        if info["type"].replace(" ", "") == "list[dict]":  # liste d'objets : leurs sous-clés Key- décrivent un élément
            schema["items"] = _object_schema(info.get("keys") or {})
            return schema
        schema["items"] = {"type": "string"}
    if info.get("keys"):
        schema.update(_object_schema(info["keys"]))
    return schema


def _object_schema(keys: dict) -> dict:
    """JSON Schema of an object described by Key- sub-keys (a dict parameter, or an item of a list[dict])."""
    if not keys:
        return {"type": "object"}
    schema = {"type": "object", "properties": {key: _property(key, sub) for key, sub in keys.items()}}
    required = [key for key, sub in keys.items() if sub["required"]]
    if required:
        schema["required"] = required
    schema["additionalProperties"] = False  # les clés inconnues sont refusées par le code
    return schema


def operation_tool(name: str, entry: dict) -> dict:
    """OpenAI tool of one operation, from its extracted docstring, without the injected parameters.

    Args:
        name: Operation name.
        entry: Its entry in extract_function_doc_info().

    Returns:
        {"type": "function", "function": {"name", "description", "parameters"}}.
    """
    params = {param: info for param, info in entry["params"].items() if param not in INJECTED_PARAMS}
    parameters = {"type": "object",
                  "properties": {param: _property(param, info) for param, info in params.items()},
                  "required": [param for param, info in params.items() if info["required"]],
                  "additionalProperties": False}
    return {"type": "function",
            "function": {"name": name, "description": _summary(entry["description"]), "parameters": parameters}}


def operation_domain(func: Callable) -> str:
    """Domain of an operation, from the sub-package of its module (e.g. ...operations.pages.posts -> posts).

    Args:
        func: Operation function.

    Returns:
        The domain name (a key of DOMAINS), or "page" for the operations outside every domain.
    """
    package = func.__module__.split(".")[-2]
    return next((domain for domain, (_, packages) in DOMAINS.items() if package in packages), "page")


class ToolRegistry:
    """The operations available to the agent, with their tools and domains."""

    def __init__(self, operations: dict[str, Callable] | None = None, ads_mode: str | None = None) -> None:
        """Build the tools of the given operations (default: every operation of the project).

        ads_mode is AD_ACCOUNT_MODE ("sandbox" or "no_payment"; anything else, or None, leaves the
        campaigns out). In no_payment, create_ad is left out: Meta refuses any ad without a payment method.
        """
        operations = dict(operations or discover_operations())
        excluded = list(EXCLUDED_OPERATIONS)
        if ads_mode not in AD_ACCOUNT_MODES:
            excluded += AD_OPERATIONS
        elif ads_mode == "no_payment":
            excluded += NO_PAYMENT_EXCLUDED
        for name in excluded:
            operations.pop(name, None)
        self.ads_mode = ads_mode if ads_mode in AD_ACCOUNT_MODES else None
        self.operations = operations
        self.docs = extract_function_doc_info(operations)
        self.tools = {name: operation_tool(name, self.docs[name]) for name in operations}
        self.domains = {name: operation_domain(func) for name, func in operations.items()}
        # domaines qui ont au moins un outil (les Campagnes manquent sans mode valide)
        self.available_domains = [domain for domain in DOMAINS if self.domain_operations(domain)]

    def signature(self, name: str) -> inspect.Signature:
        """Real signature of an operation (used by the executor).

        Args:
            name: Operation name.

        Returns:
            Its inspect.Signature.
        """
        return inspect.signature(self.operations[name])

    def domain_operations(self, domain: str) -> list[str]:
        """Names of the operations of a domain.

        Args:
            domain: Domain name.

        Returns:
            The sorted operation names (for "boost": BOOST_TOOLS, only when all of them are tools).
        """
        if domain == BOOST:
            return sorted(BOOST_TOOLS) if set(BOOST_TOOLS) <= set(self.tools) else []
        return sorted(name for name, op_domain in self.domains.items() if op_domain == domain)

    def selection_tool(self, name: str = SELECT_DOMAINS, short: bool = False) -> dict:
        """Tool used to choose the domains (select_domains first, change_domain later).

        Args:
            name: SELECT_DOMAINS or CHANGE_DOMAIN.
            short: True for the short description (select_domains offered again after the first call,
                as an alias of change_domain).

        Returns:
            The tool, whose only parameter is the list of domains (enum of DOMAINS).
        """
        if name == SELECT_DOMAINS and not short:  # 1er appel : la liste des opérations aide à choisir
            lines = [f"{domain}: {', '.join(self.domain_operations(domain))}" for domain in self.available_domains]
            description = ("Choose the domain(s) needed for the request, before any other action. "
                           "Operations of each domain: " + "; ".join(lines) + ".")
        else:  # change_domain, envoyé à chaque appel : court (le LLM connaît déjà les domaines)
            description = "Add the domain(s) whose operations the request also needs (the current ones are kept)."
        return {"type": "function", "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object",
                           "properties": {"domains": {"type": "array", "minItems": 1,
                                                      "items": {"type": "string",
                                                                "enum": list(self.available_domains)},
                                                      "description": "One or more domains."}},
                           "required": ["domains"], "additionalProperties": False}}}

    def chat_only_tool(self) -> dict:
        """Tool used when a request needs no page data: a greeting, or a question about the agent itself.

        Returns:
            The tool, whose only parameter is the kind of message (enum of CHAT_KINDS).
        """
        return {"type": "function", "function": {
            "name": CHAT_ONLY,
            "description": ("Use ONLY for a simple greeting, a question about you (the assistant), a request "
                            "outside the page and its catalog (out_of_scope), or an action no tool can do "
                            "(impossible_action, e.g. delete the whole catalog). Any question about the page, its "
                            "posts, comments, messages, photos, videos or catalog, and any request to do something "
                            "on them, needs select_domains or get_page_info instead."),
            "parameters": {"type": "object",
                           "properties": {"kind": {"type": "string", "enum": list(CHAT_KINDS),
                                                   "description": "Kind of message."}},
                           "required": ["kind"], "additionalProperties": False}}}

    def first_tools(self) -> list[dict]:
        """Tools of the first call of a request, where calling one of them is required.

        Returns:
            select_domains, the tools always available (get_page_info) and chat_only.
        """
        common = [self.tools[name] for name in ALWAYS_AVAILABLE if name in self.tools]
        return [self.selection_tool(), *common, self.chat_only_tool()]

    def tools_for(self, domains: list[str]) -> list[dict]:
        """Tools sent to the LLM for the chosen domains.

        Args:
            domains: Domain names chosen by the LLM.

        Returns:
            The tools of their operations, of their DOMAIN_READ_HELPERS and of ALWAYS_AVAILABLE
            (sorted by name), then select_domains (short alias) and change_domain.
        """
        helpers = {name for domain in domains for name in DOMAIN_READ_HELPERS.get(domain, ())}
        names = sorted({name for domain in domains for name in self.domain_operations(domain)}
                       | (set(ALWAYS_AVAILABLE) | helpers) & set(self.tools))
        # select_domains reste proposé (alias court de change_domain) : le modèle l'appelle parfois au 2e tour
        return [self.tools[name] for name in names] + [self.selection_tool(SELECT_DOMAINS, short=True),
                                                       self.selection_tool(CHANGE_DOMAIN)]


def estimate_tokens(tools: list[dict]) -> int:
    """Rough token count of tools as sent to the API (about 3.6 characters per token).

    Args:
        tools: Tools in the OpenAI format.

    Returns:
        The estimated number of tokens.
    """
    return round(len(json.dumps(tools, ensure_ascii=False)) / 3.6)
