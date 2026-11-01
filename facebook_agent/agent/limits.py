"""Respect the Groq rate limits: wait BEFORE a request that would exceed them.

Groq sends these headers with every answer (https://console.groq.com/docs/rate-limits):
    x-ratelimit-remaining-tokens / x-ratelimit-reset-tokens      tokens per minute (TPM), e.g. "7.66s"
    x-ratelimit-remaining-requests / x-ratelimit-reset-requests  requests per DAY (RPD), e.g. "2m59.56s"
    x-ratelimit-limit-tokens / x-ratelimit-limit-requests        the limits themselves
    retry-after                                                  seconds, only with a 429 answer

Before each request, the limiter combines what the server said (remaining tokens, refilled
since then) with its own count of the last 60 seconds, and pauses with a clear message only for
the missing tokens: the quota is refilled continuously (8,000 tokens per minute = 133 per
second), so waiting for the full reset announced by Groq is not needed. A 429 answer is still handled, as a last resort (retry_after).
"""
import json
import math
import re
import time
from datetime import datetime, timedelta
from collections import deque
from typing import Callable

from facebook_agent.agent.cancel import CTRL_C_HINT

TOKENS_PER_MINUTE = 8000   # limites gratuites de openai/gpt-oss-120b (vérifiées le 2026-10-19)
REQUESTS_PER_MINUTE = 30
WINDOW = 60.0              # secondes
SAFETY_MARGIN = 0.5        # secondes ajoutées à chaque pause
LONG_WAIT = 60.0           # au-delà, l'heure de reprise est affichée (Ctrl+C annule la demande)
# Le message d'un 429 de Groq nomme la limite : "... on tokens per day (TPD): Limit 200000, Used 199135, ..."
GROQ_LIMIT = re.compile(r"\((TPD|TPM|RPD|RPM)\)")
GROQ_USAGE = re.compile(r"Limit (\d+), Used (\d+), Requested (\d+)")
LIMIT_NAMES = {"TPD": "tokens par jour", "TPM": "tokens par minute", "RPD": "requêtes par jour",
               "RPM": "requêtes par minute"}
DEDUCED_TPD = "tokens par jour (déduit des en-têtes)"
UNKNOWN_LIMIT = "non précisée par Groq"
CHARS_PER_TOKEN = 3.6
DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|h|m|s)")


class RateLimitError(Exception):
    """A request cannot be sent: too large for the per-minute limit, or daily limit reached."""


def parse_duration(text: str | None) -> float | None:
    """Convert a Groq duration ("7.66s", "2m59.56s", "1h2m", "250ms" or "2") to seconds.

    Args:
        text: Header value.

    Returns:
        The duration in seconds, or None if the value is missing or unreadable.
    """
    if text is None or not str(text).strip():
        return None
    text = str(text).strip()
    try:
        return float(text)  # retry-after : nombre de secondes
    except ValueError:
        pass
    parts = DURATION_PART.findall(text)
    if not parts or "".join(number + unit for number, unit in parts) != text:
        return None
    factors = {"h": 3600, "m": 60, "s": 1, "ms": 0.001}
    return sum(float(number) * factors[unit] for number, unit in parts)


def estimate_tokens(messages: list, tools: list | None, completion_reserve: int) -> int:
    """Rough token count of a request: messages + tools (about 3.6 characters per token) + answer.

    Args:
        messages: Messages of the request.
        tools: Tools of the request.
        completion_reserve: Tokens reserved for the answer of the model.

    Returns:
        The estimated number of tokens.
    """
    size = len(json.dumps(messages, ensure_ascii=False, default=str)) + len(json.dumps(tools or [], ensure_ascii=False))
    return math.ceil(size / CHARS_PER_TOKEN) + completion_reserve


def _header(headers, name: str) -> str | None:
    """Header value, whatever the case of its name."""
    if headers is None:
        return None
    for key, value in dict(headers).items():
        if key.lower() == name:
            return value
    return None


class RateLimiter:
    """Tracks the Groq limits of the session and pauses before a request when needed."""

    def __init__(self, tokens_per_minute: int = TOKENS_PER_MINUTE, requests_per_minute: int = REQUESTS_PER_MINUTE,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep,
                 notify: Callable[[str], None] = print, cancel_hint: str = CTRL_C_HINT) -> None:
        """Start with the known limits; the headers of each answer then refine them.

        cancel_hint ends the message of a long wait: how to cancel the request (Ctrl+C in the
        terminal, a button in the web interface).
        """
        self.tokens_per_minute = tokens_per_minute
        self.requests_per_minute = requests_per_minute
        self.clock, self.sleep, self.notify = clock, sleep, notify
        self.cancel_hint = cancel_hint
        self.remaining_tokens: int | None = None
        self.tokens_recorded_at = 0.0  # heure à laquelle Groq a annoncé remaining_tokens
        self.tokens_reset_at: float | None = None
        self.conservative = False  # True après un 429 : la recharge continue n'est plus supposée
        self.remaining_requests_today: int | None = None
        self.requests_reset_at: float | None = None
        self.recent: deque[tuple[float, int]] = deque()  # (heure, tokens) des requêtes des 60 dernières secondes

    def _forget_old(self, now: float) -> None:
        """Drop the requests older than the 60-second window."""
        while self.recent and self.recent[0][0] <= now - WINDOW:
            self.recent.popleft()

    def delay_before(self, estimated_tokens: int) -> tuple[float, str | None]:
        """Seconds to wait before sending a request of estimated_tokens, and the limit concerned.

        Args:
            estimated_tokens: Estimated tokens of the request (see estimate_tokens).

        Returns:
            (0, None) if it can be sent now, otherwise (seconds, name of the limit).

        Raises:
            RateLimitError: The request is larger than the per-minute limit, or no request is left today.
        """
        now = self.clock()
        if estimated_tokens > self.tokens_per_minute:
            raise RateLimitError(f"Requête trop grande pour la limite Groq ({estimated_tokens} tokens estimés, "
                                 f"{self.tokens_per_minute} par minute) : utilise /reset ou une demande plus courte.")
        if self.remaining_requests_today == 0 and self.requests_reset_at and self.requests_reset_at > now:
            wait = math.ceil(self.requests_reset_at - now)
            raise RateLimitError(f"Limite quotidienne de requêtes Groq atteinte : réessaie dans {wait} s.")
        self._forget_old(now)
        delays = []
        rate = self.tokens_per_minute / WINDOW  # tokens rendus par seconde (quota rechargé en continu)
        # 1. Ce que Groq a annoncé, rechargé depuis : attendre seulement les tokens qui manquent,
        #    jamais plus que le délai de renouvellement complet annoncé
        if self.remaining_tokens is not None and self.tokens_reset_at and self.tokens_reset_at > now:
            if self.conservative:  # après un 429 : pas de recharge supposée, renouvellement complet attendu
                if estimated_tokens > self.remaining_tokens:
                    delays.append((self.tokens_reset_at - now, "tokens par minute"))
            else:
                available = min(self.tokens_per_minute,
                                self.remaining_tokens + (now - self.tokens_recorded_at) * rate)
                if estimated_tokens > available:
                    missing_delay = (estimated_tokens - available) / rate
                    delays.append((min(missing_delay, self.tokens_reset_at - now), "tokens par minute"))
        # 2. Notre propre décompte : chaque requête « rend » ses tokens en 60 s
        level = sum(tokens * max(0.0, 1 - (now - sent_at) / WINDOW) for sent_at, tokens in self.recent)
        if level + estimated_tokens > self.tokens_per_minute:
            delays.append(((level + estimated_tokens - self.tokens_per_minute) / rate, "tokens par minute"))
        if len(self.recent) >= self.requests_per_minute:
            delays.append((self.recent[0][0] + WINDOW - now, "requêtes par minute"))
        if not delays:
            return 0.0, None
        return max(delays)

    def wait_before(self, estimated_tokens: int) -> float:
        """Pause, with a message, until a request of estimated_tokens respects the limits.

        Args:
            estimated_tokens: Estimated tokens of the request.

        Returns:
            The number of seconds waited (0 if none).

        Raises:
            RateLimitError: See delay_before.
        """
        delay, limit = self.delay_before(estimated_tokens)
        if delay <= 0:
            return 0.0
        self.notify(f"Pause de {math.ceil(delay)} s pour respecter la limite Groq ({limit}).")
        self.sleep(delay + SAFETY_MARGIN)
        return delay + SAFETY_MARGIN

    def record(self, headers, used_tokens: int) -> None:
        """Update the state after an answer: its rate-limit headers and the tokens it used.

        Args:
            headers: HTTP headers of the answer (any mapping).
            used_tokens: Tokens used by the request (usage.total_tokens, or the estimate).
        """
        now = self.clock()
        self.recent.append((now, max(int(used_tokens or 0), 0)))
        limit = _header(headers, "x-ratelimit-limit-tokens")
        if limit and str(limit).isdigit():
            self.tokens_per_minute = int(limit)
        remaining = _header(headers, "x-ratelimit-remaining-tokens")
        if remaining is not None and str(remaining).lstrip("-").isdigit():
            self.remaining_tokens = int(remaining)
            self.tokens_recorded_at = now
            reset = parse_duration(_header(headers, "x-ratelimit-reset-tokens"))
            self.tokens_reset_at = now + reset if reset is not None else None
        remaining = _header(headers, "x-ratelimit-remaining-requests")
        if remaining is not None and str(remaining).isdigit():
            self.remaining_requests_today = int(remaining)
            reset = parse_duration(_header(headers, "x-ratelimit-reset-requests"))
            self.requests_reset_at = now + reset if reset is not None else None

    @staticmethod
    def limit_reached(headers, delay: float | None = None, message: str | None = None) -> str:
        """Which Groq limit a 429 answer is about.

        The message of the answer names it ("(TPD)", "(TPM)", "(RPD)", "(RPM)"). Without it, the
        x-ratelimit-* headers only describe the requests per day and the tokens per minute: the
        tokens per day are then only deduced (a long wait that neither of them explains).

        Args:
            headers: HTTP headers of the 429 answer.
            delay: Announced wait in seconds (retry-after), if known.
            message: Error message of the answer, if known.

        Returns:
            "tokens par jour", "tokens par minute", "requêtes par jour", "requêtes par minute",
            DEDUCED_TPD, or UNKNOWN_LIMIT.
        """
        found = GROQ_LIMIT.search(message or "")
        if found:
            return LIMIT_NAMES[found.group(1)]
        if delay is None:
            delay = parse_duration(_header(headers, "retry-after"))
        remaining_requests = _header(headers, "x-ratelimit-remaining-requests")
        if remaining_requests is not None and str(remaining_requests).strip() == "0":
            return "requêtes par jour"
        try:
            remaining_tokens = float(_header(headers, "x-ratelimit-remaining-tokens"))
        except (TypeError, ValueError):
            remaining_tokens = None
        try:
            limit_tokens = float(_header(headers, "x-ratelimit-limit-tokens") or TOKENS_PER_MINUTE)
        except ValueError:
            limit_tokens = TOKENS_PER_MINUTE
        reset_tokens = parse_duration(_header(headers, "x-ratelimit-reset-tokens"))
        minute_full = remaining_tokens is not None and remaining_tokens >= limit_tokens
        # La minute explique l'attente : jetons pas tous disponibles, et attente de l'ordre de leur recharge
        explained = delay is None or delay <= (reset_tokens + 5 if reset_tokens is not None else WINDOW)
        if not minute_full and explained:
            return "tokens par minute"
        if delay is not None and delay > 2 * WINDOW:
            return DEDUCED_TPD
        return UNKNOWN_LIMIT

    def wait_after_429(self, headers, message: str | None = None) -> float:
        """Last resort after a 429 answer: wait retry-after seconds (or the token reset, or 60 s).

        From then on, the limiter of this model is conservative: it waits for the full reset
        announced by Groq instead of assuming a continuous refill.

        Args:
            headers: HTTP headers of the 429 answer.
            message: Error message of the answer (it names the limit reached).

        Returns:
            The number of seconds waited.
        """
        delay = parse_duration(_header(headers, "retry-after"))
        if delay is None:
            delay = parse_duration(_header(headers, "x-ratelimit-reset-tokens"))
        delay = WINDOW if delay is None else delay
        limit = self.limit_reached(headers, delay, message)
        which = f"Limite Groq ({limit})" if limit == UNKNOWN_LIMIT else f"Limite Groq de {limit}"
        if delay > LONG_WAIT:
            resume = (datetime.now() + timedelta(seconds=delay)).strftime("%H:%M")
            self.notify(f"{which} atteinte : reprise vers {resume} (dans {math.ceil(delay / 60)} min). "
                        f"{self.cancel_hint}")
        else:
            self.notify(f"Limite Groq atteinte (429, {limit}) : nouvel essai dans {math.ceil(delay)} s.")
        self.sleep(delay + SAFETY_MARGIN)
        self.remaining_tokens = None  # l'état du serveur sera relu sur la prochaine réponse
        self.conservative = True  # le quota ne se recharge pas comme supposé : prudence jusqu'à la fin
        return delay + SAFETY_MARGIN
