"""Call the LLM (OpenAI-compatible API, Groq by default) with native function calling.

Each request: the rate limiter pauses first if needed, then the request is sent with the
tools, reasoning_effort, max_completion_tokens and include_reasoning=false (the reasoning of
the model is never received, so it never enters the history). The rate-limit headers of the
answer update the limiter; a 429 answer is retried once after the announced delay, a 400
"Parsing failed." once at once, a 400 "Tool choice is required, but model did not call a tool" once
without a forced tool_choice ("auto"), and a network error once after NETWORK_RETRY_DELAY seconds (the
message gives the precise cause).
"""
import re
import time
from dataclasses import dataclass, field
from typing import Callable

from facebook_agent.agent.cancel import CTRL_C_HINT
from facebook_agent.agent.limits import GROQ_USAGE, RateLimiter, RateLimitError, estimate_tokens
from facebook_agent.agent.settings import LLMSettings
from facebook_agent.graph import NETWORK_RETRY_DELAY, network_cause

REQUEST_TIMEOUT = 60  # secondes par requête au LLM
# Le modèle a appelé un outil qui n'était pas proposé (Groq refuse la requête avec une erreur 400)
TOOL_NOT_OFFERED = re.compile(r"attempted to call tool '([^']+)' which was not in request\.tools")
TOOL_CHOICE_REFUSED = re.compile(r"tool[_ ]choice", re.IGNORECASE)
ORGANIZATION = re.compile(r"organization `[^`]*`")  # identifiant de l'organisation Groq : pas dans le journal
# « parameters for tool update_product did not match schema: errors: [missing properties: 'data', ...] »
TOOL_ARGUMENTS_INVALID = re.compile(r"parameters for tool ([\w-]+) did not match schema: errors: \[(.*)\]",
                                    re.IGNORECASE | re.DOTALL)
TOOL_CHOICE_NONE = re.compile(r"tool choice is none, but model called a tool", re.IGNORECASE)
PARSING_FAILED = re.compile(r"^\s*Parsing failed\.?\s*$", re.IGNORECASE)  # 400 de Groq : un nouvel essai


class LLMError(Exception):
    """The LLM could not answer (network, API error, rate limit); the message is in French."""


class ToolsNeededError(LLMError):
    """The model called a tool in a request sent without tools ("Tool choice is none, but model called a tool")."""


class ToolChoiceRefusedError(LLMError):
    """The model called no tool although one was required, even after a retry in "auto" (HTTP 400 twice)."""


class ToolArgumentsError(LLMError):
    """Groq checked the arguments of a tool call against its schema and refused them (HTTP 400)."""

    def __init__(self, tool_name: str, errors: str) -> None:
        """Keep the tool and the errors of the schema check, so that the agent can send them back to the model."""
        super().__init__(f"arguments de l'outil {tool_name} refusés par le contrôle du schéma : {errors}")
        self.tool_name = tool_name
        self.errors = errors


class ToolNotOfferedError(LLMError):
    """The model called a tool that was not offered in the request (rejected by the provider)."""

    def __init__(self, tool_name: str, message: str) -> None:
        """Keep the name of the tool, so that the agent can select its domain and try again."""
        super().__init__(message)
        self.tool_name = tool_name


@dataclass
class ToolCall:
    """One tool call requested by the LLM."""

    id: str
    name: str
    arguments: str  # JSON tel qu'envoyé par le LLM, vérifié par l'exécuteur


@dataclass
class LLMReply:
    """Answer of the LLM: a text, or tool calls, and the tokens used."""

    content: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    total_tokens: int = 0
    finish_reason: str | None = None  # "stop", "tool_calls" ou "length" (réponse coupée)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None  # partie des completion_tokens utilisée pour raisonner
    model: str | None = None
    estimated_tokens: int | None = None  # estimation faite avant l'envoi (pour recaler l'estimation)
    # True : l'outil exigé (« required » ou un outil précis) a été refusé par le modèle (400), la réponse vient
    # du nouvel essai en « auto »
    tool_choice_relaxed: bool = False

    def usage(self) -> dict:
        """Token usage reported by the provider, for the log.

        Returns:
            model, total, prompt, completion and reasoning tokens, and the finish reason.
        """
        return {"model": self.model, "estimated_tokens": self.estimated_tokens,
                "total_tokens": self.total_tokens, "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens, "reasoning_tokens": self.reasoning_tokens,
                "finish_reason": self.finish_reason}


class LLMClient:
    """Sends the requests of the agent to the LLM, within the rate limits."""

    def __init__(self, settings: LLMSettings, limiter: RateLimiter | None = None, client=None,
                 notify: Callable[[str], None] = print, sleep: Callable[[float], None] = time.sleep,
                 cancel_hint: str = CTRL_C_HINT) -> None:
        """Create the OpenAI client (or use the given one, for the tests) and the rate limiter.

        notify, sleep and cancel_hint are also those of the rate limiters (the web interface gives
        a sleep that stops when the request is cancelled).
        """
        if client is None:
            from openai import OpenAI  # import tardif : les tests n'en ont pas besoin
            # max_retries=0 : les nouveaux essais (réseau, 429) sont faits ici, avec un message clair
            client = OpenAI(api_key=settings.api_key, base_url=settings.base_url, max_retries=0,
                            timeout=REQUEST_TIMEOUT)
        self.client = client
        self.settings = settings
        self.notify = notify
        self.sleep = sleep
        self.on_event: Callable[..., None] | None = None  # journal de l'agent (ex. 429 et leurs en-têtes)
        # Un limiteur par modèle : chez Groq, chaque modèle a son propre quota
        self.limiters = {settings.model: limiter or RateLimiter(sleep=sleep, notify=notify, cancel_hint=cancel_hint)}

    @property
    def limiter(self) -> RateLimiter:
        """Rate limiter of the main model.

        Returns:
            The RateLimiter of LLM_MODEL.
        """
        return self.limiters[self.settings.model]

    def limiter_for(self, model: str) -> RateLimiter:
        """Rate limiter of a model, created on first use.

        Args:
            model: Model name.

        Returns:
            Its RateLimiter (same default limits, refined by the headers of its answers).
        """
        if model not in self.limiters:
            main = self.limiter
            self.limiters[model] = RateLimiter(clock=main.clock, sleep=main.sleep, notify=main.notify,
                                               cancel_hint=main.cancel_hint)
        return self.limiters[model]

    def chat(self, messages: list[dict], tools: list[dict], tool_choice: str | dict = "auto",
             model: str | None = None) -> LLMReply:
        """Send one request and return the answer of the model.

        Args:
            messages: System prompt and history, in the OpenAI format.
            tools: Tools offered for this request.
            tool_choice: "auto" (the model may answer with a text), "required" (it must call a tool), or
                {"type": "function", "function": {"name": ...}} (it must call this tool).
            model: Model of this request (default: LLM_MODEL); each model has its own rate limits.

        Returns:
            The answer (text or tool calls) and the tokens used.

        Raises:
            LLMError: The request could not be sent or answered (the message gives the cause).
            ToolsNeededError: The model called a tool although none was offered.
            ToolArgumentsError: Groq refused the arguments of a tool call (schema check).
        """
        import openai

        model = model or self.settings.model
        limiter = self.limiter_for(model)
        estimate = estimate_tokens(messages, tools, self.settings.completion_reserve)
        try:
            limiter.wait_before(estimate)
        except RateLimitError as exc:
            raise LLMError(str(exc)) from None
        request = {"model": model, "messages": messages,
                   "reasoning_effort": self.settings.reasoning_effort,
                   "max_completion_tokens": self.settings.max_completion_tokens,
                   "extra_body": {"include_reasoning": False}}  # le raisonnement n'est jamais renvoyé
        if tools:  # sans outil, les paramètres ne sont pas envoyés du tout (jamais null)
            request.update(tools=tools, tool_choice=tool_choice)
        retried_429 = retried_network = retried_choice = retried_parsing = False
        while True:
            try:
                raw = self.client.chat.completions.with_raw_response.create(**request)
                break
            except openai.RateLimitError as exc:
                headers, message = exc.response.headers, self._message(exc)
                usage = GROQ_USAGE.search(message)
                self._event("rate_limit", model=model, limit=limiter.limit_reached(headers, message=message),
                            message=ORGANIZATION.sub("organization `…`", message),
                            **({"groq_limit": int(usage.group(1)), "groq_used": int(usage.group(2)),
                                "groq_requested": int(usage.group(3))} if usage else {}),
                            headers={k: v for k, v in dict(headers).items()
                                     if k.lower().startswith("x-ratelimit") or k.lower() == "retry-after"})
                if retried_429:
                    raise LLMError("Limite Groq atteinte deux fois de suite : réessaie dans une minute.") from None
                retried_429 = True
                limiter.wait_after_429(headers, message)
            except openai.APIStatusError as exc:
                message = self._message(exc)
                if exc.status_code == 400 and TOOL_CHOICE_REFUSED.search(message) and not TOOL_CHOICE_NONE.search(message):
                    if retried_choice or request.get("tool_choice") in (None, "auto"):
                        # refusé aussi sans outil forcé : une erreur dédiée, jamais le message brut de Groq
                        raise ToolChoiceRefusedError("le modèle n'a proposé aucun outil") from None
                    # outil précis ou "required" refusé ("Tool choice is required, but model did not call a
                    # tool") : un seul nouvel essai, sans tool_choice forcé
                    retried_choice = True
                    self._event("tool_choice_retry", model=model, refused=str(request["tool_choice"])[:80])
                    request["tool_choice"] = "auto"
                    continue
                if exc.status_code == 400 and PARSING_FAILED.search(message) and not retried_parsing:
                    # « Parsing failed. » : réponse du modèle illisible côté Groq, souvent passagère : un nouvel essai
                    retried_parsing = True
                    self._event("parsing_failed_retry", model=model)
                    continue
                invalid_arguments = TOOL_ARGUMENTS_INVALID.search(message) if exc.status_code == 400 else None
                if invalid_arguments:
                    raise ToolArgumentsError(invalid_arguments.group(1), invalid_arguments.group(2)) from None
                if exc.status_code == 400 and TOOL_CHOICE_NONE.search(message):
                    raise ToolsNeededError("le modèle a appelé un outil alors qu'aucun n'était proposé") from None
                not_offered = TOOL_NOT_OFFERED.search(message) if exc.status_code == 400 else None
                if not_offered:
                    raise ToolNotOfferedError(not_offered.group(1),
                                              f"outil {not_offered.group(1)} appelé sans être proposé") from None
                raise LLMError(f"Erreur du LLM (HTTP {exc.status_code}) : {message}") from None
            except openai.APIConnectionError as exc:  # réseau, DNS, SSL, délai (APITimeoutError)
                cause = network_cause(exc)
                if retried_network:
                    raise LLMError(f"Impossible de contacter le LLM après 2 essais : {cause}.") from None
                retried_network = True
                self.notify(f"Réseau : {cause}. Nouvel essai dans {NETWORK_RETRY_DELAY} s.")
                self.sleep(NETWORK_RETRY_DELAY)
        completion = raw.parse()
        usage = getattr(completion, "usage", None)
        used = getattr(usage, "total_tokens", None) or estimate
        limiter.record(raw.headers, used)
        choice = completion.choices[0]
        message = choice.message
        calls = [ToolCall(call.id, call.function.name, call.function.arguments or "{}")
                 for call in (message.tool_calls or [])]
        details = getattr(usage, "completion_tokens_details", None)
        return LLMReply(message.content, calls, used, getattr(choice, "finish_reason", None),
                        getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None),
                        getattr(details, "reasoning_tokens", None), model, estimate, tool_choice_relaxed=retried_choice)

    def _event(self, event: str, **fields) -> None:
        """Report an event to the agent's log, if one is connected."""
        if self.on_event:
            self.on_event(event, **fields)

    @staticmethod
    def _message(exc) -> str:
        """Short error message of the API (the body never contains the key)."""
        body = exc.body if isinstance(exc.body, dict) else {}
        error = body.get("error", body) if isinstance(body, dict) else {}
        return str(error.get("message") if isinstance(error, dict) and error.get("message") else exc.message)[:300]
