"""Command line of the agent. Run by the user only (it calls the real Facebook and LLM APIs).

    .venv\\Scripts\\python.exe -m facebook_agent.agent [--dry-run]

Commands: /aide, /reset, /quitter.
"""
import argparse
import sys
from typing import Callable

from facebook_agent.agent.build import build_agent, help_text, session_registry  # noqa: F401 (help_text : /aide)
from facebook_agent.agent.display import for_terminal
from facebook_agent.agent.journal import SessionLog
from facebook_agent.agent.session import SessionError, open_session
from facebook_agent.agent.settings import load_llm_settings


def _ask_page(pages: list[dict]) -> dict:
    """Let the user choose a page (only when FB_PAGE_ID is empty and the account has several pages)."""
    for index, page in enumerate(pages):
        print(f"[{index}] {page.get('name')}")
    while True:
        answer = input("Choisis la page : ").strip()
        if answer.isdigit() and int(answer) < len(pages):
            return pages[int(answer)]
        print("Choix invalide.")


def main(argv: list[str] | None = None, input_fn: Callable[[str], str] = input, out: Callable[[str], None] = print,
         llm_factory=None, log_dir=None) -> int:
    """Run the agent until /quitter.

    Args:
        argv: Command line arguments (default: sys.argv).
        input_fn: Reads a line typed by the user (replaced in the tests).
        out: Shows a line (replaced in the tests).
        llm_factory: Builds the LLM client from the settings (a fake LLM in the tests).
        log_dir: Folder of the session log (default: logs/).

    Returns:
        The exit code (0 on success).
    """
    parser = argparse.ArgumentParser(description="Agent IA de gestion de la page Facebook.")
    parser.add_argument("--dry-run", action="store_true",
                        help="lectures réelles, mais aucune écriture envoyée à Facebook (actions simulées)")
    parser.add_argument("--verbose", action="store_true",
                        help="afficher le JSON complet de chaque résultat (il est toujours dans le journal)")
    args = parser.parse_args(argv)
    try:
        settings = load_llm_settings()
    except ValueError as exc:
        out(f"Configuration invalide : {exc}")
        return 1
    try:
        session = open_session(_ask_page, notify=out)
    except SessionError as exc:
        out(f"Impossible de démarrer : {exc}")
        return 1
    journal = SessionLog(secrets=session.secrets | {settings.api_key}, **({"log_dir": log_dir} if log_dir else {}))
    registry = session_registry()
    agent = build_agent(settings, session, journal, _confirm_with(input_fn, out), out, dry_run=args.dry_run,
                        verbose=args.verbose, llm=llm_factory(settings) if llm_factory else None, registry=registry)
    journal.write("start", page=session.page_name, model=settings.model, router_model=settings.first_call_model,
                  dry_run=args.dry_run,
                  verbose=args.verbose, long_lived=session.long_lived)
    mode = " [DRY-RUN : aucune écriture ne sera envoyée]" if args.dry_run else ""
    router = f", choix du domaine : {settings.first_call_model}" if settings.first_call_model != settings.model else ""
    out(f"Agent prêt sur la page « {session.page_name} » (modèle {settings.model}{router}){mode}. /aide pour l'aide.")
    try:
        while True:
            try:
                text = input_fn("Toi > ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            command = text.lower()
            if command in ("/quitter", "/quit", "/exit"):
                break
            if command == "/aide":
                out(help_text(registry))
                continue
            if command == "/reset":
                agent.reset()
                out("Historique vidé.")
                continue
            try:
                answer = agent.handle(text).strip() or "(aucune réponse : voir le journal de la session)"
            except KeyboardInterrupt:  # Ctrl+C pendant une demande (ex. longue attente Groq) : elle seule est annulée
                out("")
                out(f"Agent > {agent.cancel_request()}")
                continue
            out(f"Agent > {for_terminal(answer)}")
            out(agent.status_line())
    except KeyboardInterrupt:  # Ctrl+C ailleurs (commande) : on quitte proprement
        out("")
        journal.write("interrupted")
    finally:
        journal.write("end")
        session.close()
        out("Au revoir. Les tokens de la session sont oubliés.")
    return 0


def _confirm_with(input_fn: Callable[[str], str], out: Callable[[str], None]) -> Callable[[str], bool]:
    """Confirmation that uses the given input and output functions (tests)."""
    def confirm(text: str) -> bool:
        """Show the action and read o/n."""
        out(text)
        return input_fn("Confirmer ? (o/n) : ").strip().lower() == "o"
    return confirm


if __name__ == "__main__":
    sys.exit(main())
