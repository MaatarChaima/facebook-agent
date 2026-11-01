"""Assemble the agent of a session: the same objects for the terminal and the web interface.

Only the functions given here differ between them: confirm (o/n typed, or buttons), out (print,
or the chat zone) and sleep (time.sleep, or a wait that stops when the request is cancelled).
"""
import time
from typing import Callable

from facebook_agent import config
from facebook_agent.agent.cancel import CTRL_C_HINT
from facebook_agent.agent.executor import Executor
from facebook_agent.agent.history import History
from facebook_agent.agent.journal import SessionLog
from facebook_agent.agent.llm import LLMClient
from facebook_agent.agent.loop import MAX_TURNS, Agent
from facebook_agent.agent.settings import LLMSettings
from facebook_agent.agent.tools import AD_DOMAINS, BOOST, DOMAINS, ToolRegistry

HELP_HEAD = """Commandes :
  /aide      cette aide
  /reset     vider l'historique de la conversation
  /quitter   quitter (les tokens sont oubliés)

Écris une demande en français, par exemple :
  « liste mes 3 derniers posts »
  « publie un post qui annonce les soldes »
  « cherche le produit T-shirt et baisse son prix à 15 € »
"""
CAMPAIGNS_OFF = ("{labels} : désactivés (configurer AD_ACCOUNT_ID et AD_ACCOUNT_MODE=sandbox ou no_payment "
                 "dans le .env).")
BOOST_OFF = ("Booster un post : désactivé (AD_ACCOUNT_MODE=no_payment : Meta refuse toute publicité sans moyen de "
             "paiement ; utiliser un compte sandbox).")


def active_domain_labels(registry: ToolRegistry) -> list[str]:
    """Labels of the domains of the session (/aide and the panel of the web interface).

    Args:
        registry: Tools of the session.

    Returns:
        The French labels, in the order of the domains.
    """
    return [DOMAINS[d][0] for d in registry.available_domains]


def disabled_domain_notes(registry: ToolRegistry) -> list[str]:
    """One short line for the disabled ad domains: why, which variable (no value of the .env).

    Args:
        registry: Tools of the session.

    Returns:
        CAMPAIGNS_OFF or BOOST_OFF, or no line when everything is active.
    """
    off = [domain for domain in (*AD_DOMAINS, BOOST) if domain not in registry.available_domains]
    if set(AD_DOMAINS) & set(off):
        return [CAMPAIGNS_OFF.format(labels=", ".join(DOMAINS[d][0] for d in off))]
    return [BOOST_OFF] if BOOST in off else []


def help_text(registry: ToolRegistry, head: str = HELP_HEAD, how_to_confirm: str = "(o/n)") -> str:
    """Text of /aide: the active domains only, and one short line for each disabled one (why, which variable).

    Args:
        registry: Tools of the session (the campaigns depend on AD_ACCOUNT_ID and AD_ACCOUNT_MODE).
        head: Commands and examples (those of the terminal by default).
        how_to_confirm: How a write is confirmed ("(o/n)" typed in the terminal, buttons in the web interface).

    Returns:
        The help, in French (no value of the .env).
    """
    lines = [head, f"Domaines : {', '.join(active_domain_labels(registry))}.", *disabled_domain_notes(registry)]
    lines.append("Toute action qui modifie la page, le catalogue ou les campagnes est affichée et attend ta "
                 f"confirmation {how_to_confirm}.\nAu plus {MAX_TURNS} étapes et 3 actions par demande.")
    return "\n".join(lines)


def session_registry() -> ToolRegistry:
    """Tools of the session: the campaigns only with an ad account and a valid mode (sandbox, no_payment).

    Returns:
        The ToolRegistry built from AD_ACCOUNT_ID and AD_ACCOUNT_MODE.
    """
    return ToolRegistry(ads_mode=config.AD_ACCOUNT_MODE if config.AD_ACCOUNT_ID else None)


def build_agent(settings: LLMSettings, session, journal: SessionLog | None, confirm: Callable[[str], bool],
                out: Callable[[str], None], dry_run: bool = False, verbose: bool = False, llm=None,
                sleep: Callable[[float], None] = time.sleep, cancel_hint: str = CTRL_C_HINT,
                registry: ToolRegistry | None = None) -> Agent:
    """Create the registry, the executor, the LLM client and the agent of a session.

    Args:
        settings: LLM settings (load_llm_settings).
        session: Open session (open_session): its context holds the tokens, in memory only.
        journal: Log of the session.
        confirm: Shows the confirmation text of a write and returns True if the user accepts.
        out: Shows a line or a message (answers, pauses, notices).
        dry_run: True: the writes are simulated, nothing is sent to Facebook.
        verbose: True: the full JSON of each result is shown.
        llm: LLM client to use (a fake one in the tests); default: an LLMClient built from the settings.
        sleep: Wait of the LLM client and its rate limiters.
        cancel_hint: How to cancel a request, shown with a long Groq wait.
        registry: Tools of the session (default: session_registry()).

    Returns:
        The Agent (its executor and its LLM client are agent.executor and agent.llm).
    """
    registry = registry or session_registry()
    executor = Executor(registry, session.context, confirm=confirm, dry_run=dry_run, notify=out,
                        protected_forms=config.PROTECTED_LEAD_FORM_IDS)
    if llm is None:
        llm = LLMClient(settings, notify=out, sleep=sleep, cancel_hint=cancel_hint)
    return Agent(llm, registry, executor, History(settings.history_exchanges), journal, out=out, dry_run=dry_run,
                 verbose=verbose, model=settings.model, router_model=settings.first_call_model)
