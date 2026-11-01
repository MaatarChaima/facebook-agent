"""LLM settings of the agent, read from the configuration (.env) and checked."""
from dataclasses import dataclass

from facebook_agent import config

REASONING_EFFORTS = ("low", "medium", "high")  # valeurs acceptées par les modèles gpt-oss de Groq
MAX_COMPLETION_LIMIT = 65536                   # maximum de openai/gpt-oss-120b sur Groq
# Tokens de réponse comptés d'avance : réponses mesurées le 2026-10-19 (moyenne 61, maximum 101) + 50 %
COMPLETION_RESERVE = 150


@dataclass(frozen=True)
class LLMSettings:
    """Validated LLM settings."""

    base_url: str
    api_key: str | None
    model: str
    reasoning_effort: str
    max_completion_tokens: int
    history_exchanges: int = 1
    router_model: str | None = None  # modèle du 1er appel ; None = model

    @property
    def first_call_model(self) -> str:
        """Model of the first call of each request (choice of the domain).

        Returns:
            router_model, or model when no router model is set.
        """
        return self.router_model or self.model

    @property
    def completion_reserve(self) -> int:
        """Tokens reserved for the answer when estimating a request.

        Returns:
            max_completion_tokens, at most COMPLETION_RESERVE (low reasoning gives short answers).
        """
        return min(self.max_completion_tokens, COMPLETION_RESERVE)


def load_llm_settings(require_key: bool = True) -> LLMSettings:
    """Read and check the LLM_* variables of the configuration.

    Args:
        require_key: True to require LLM_API_KEY (the agent needs it; the tests do not).

    Returns:
        The validated settings.

    Raises:
        ValueError: A value is missing or invalid (message in French, without any secret).
    """
    errors = []
    if require_key and not config.LLM_API_KEY:
        errors.append("LLM_API_KEY est vide dans le .env (clé Groq : https://console.groq.com/keys).")
    effort = (config.LLM_REASONING_EFFORT or "low").strip().lower()
    if effort not in REASONING_EFFORTS:
        errors.append(f"LLM_REASONING_EFFORT doit valoir {', '.join(REASONING_EFFORTS)} (reçu : {effort!r}).")
    raw_max = str(config.LLM_MAX_COMPLETION_TOKENS or "1024").strip()
    max_tokens = int(raw_max) if raw_max.isdigit() else 0
    if not 1 <= max_tokens <= MAX_COMPLETION_LIMIT:
        errors.append(f"LLM_MAX_COMPLETION_TOKENS doit être un entier entre 1 et {MAX_COMPLETION_LIMIT} "
                      f"(reçu : {raw_max!r}).")
    raw_history = str(config.LLM_HISTORY_EXCHANGES or "1").strip()
    history = int(raw_history) if raw_history.isdigit() else 0
    if not 1 <= history <= 20:
        errors.append(f"LLM_HISTORY_EXCHANGES doit être un entier entre 1 et 20 (reçu : {raw_history!r}).")
    if errors:
        raise ValueError(" ".join(errors))
    return LLMSettings(config.LLM_BASE_URL, config.LLM_API_KEY, config.LLM_MODEL, effort, max_tokens, history,
                       config.LLM_ROUTER_MODEL)
