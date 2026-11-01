"""Project configuration loaded from the ``.env`` file at the project root.

Every secret or identifier used by the project must be read from here,
never written directly in the code. Copy ``.env.example`` to ``.env``
and fill in the values.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

from facebook_agent.ads_safety import AD_ACCOUNT_MODES, ad_account_path
from facebook_agent.lead_safety import protected_form_ids

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _get(name: str, default: str | None = None) -> str | None:
    """Return the variable value, or ``default`` when it is missing or empty."""
    value = os.getenv(name, "").strip()
    return value or default


# Facebook Graph API
BASE_URL = "https://graph.facebook.com/v23.0"
DEFAULT_TIMEOUT = 30  # secondes, requêtes simples
UPLOAD_TIMEOUT = 300  # secondes, envois de fichiers (photos, vidéos, feeds)

# Facebook
FB_USER_TOKEN = _get("FB_USER_TOKEN")
FB_APP_ID = _get("FB_APP_ID")
FB_APP_SECRET = _get("FB_APP_SECRET")
FB_PAGE_ID = _get("FB_PAGE_ID")
FB_LIVE_TESTS = _get("FB_LIVE_TESTS", "0")  # "1" pour autoriser les tests live
CATALOG_ID = _get("CATALOG_ID")

# Phase 3 : campagnes, uniquement sur un compte qui ne peut rien dépenser (règle : facebook_agent/ads_safety.py)
AD_ACCOUNT_ID = ad_account_path(_get("AD_ACCOUNT_ID"))  # "act_123…" ou "123…" dans le .env -> "act_123…"
# "sandbox" (compte sandbox de l'app) ou "no_payment" ; dans les deux cas, aucun moyen de paiement et rien
# dépensé, vérifié en direct avant chaque écriture ; vide = domaine Campagnes désactivé
AD_ACCOUNT_MODE = _get("AD_ACCOUNT_MODE")
AD_ACCOUNT_MODES = AD_ACCOUNT_MODES
ADS_ACCESS_TOKEN = _get("ADS_ACCESS_TOKEN")  # token généré dans Marketing API > Outils ; vide = FB_USER_TOKEN
# Formulaires Lead Ads protégés (ID séparés par des virgules) : jamais archivés ni utilisés dans une publicité
PROTECTED_LEAD_FORM_IDS = protected_form_ids(_get("PROTECTED_LEAD_FORM_IDS"))

# LLM (API compatible OpenAI, utilisée dans la phase agentique)
LLM_BASE_URL = _get("LLM_BASE_URL", "https://api.groq.com/openai/v1")
LLM_API_KEY = _get("LLM_API_KEY")
LLM_MODEL = _get("LLM_MODEL", "openai/gpt-oss-120b")  # secours : openai/gpt-oss-20b
LLM_REASONING_EFFORT = _get("LLM_REASONING_EFFORT", "low")  # low, medium ou high (modèles gpt-oss)
LLM_MAX_COMPLETION_TOKENS = _get("LLM_MAX_COMPLETION_TOKENS", "1024")  # converti et vérifié par l'agent
LLM_HISTORY_EXCHANGES = _get("LLM_HISTORY_EXCHANGES", "1")  # échanges précédents gardés en entier
LLM_ROUTER_MODEL = _get("LLM_ROUTER_MODEL", "openai/gpt-oss-20b")  # 1er appel (choix du domaine), quota séparé


def require(name: str) -> str:
    """Return a configuration value, or raise a clear error if it is not set.

    Args:
        name: Name of the variable (e.g. "CATALOG_ID").

    Returns:
        The value read from the .env file.

    Raises:
        RuntimeError: The variable is missing or empty in the .env file.
    """
    value = globals().get(name)
    if not value:
        raise RuntimeError(
            f"La variable {name} est absente ou vide dans le fichier .env "
            f"(voir .env.example)."
        )
    return value
