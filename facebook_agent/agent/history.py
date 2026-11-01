"""Conversation history of the agent, kept small for the limit of 8,000 tokens per minute.

The history is a list of exchanges (one per user request: the request, the tool calls, the
tool results and the answer). The current request and the previous one (LLM_HISTORY_EXCHANGES)
are kept whole; an older exchange keeps only the request and the final answer (200 characters).
Beyond MAX_HISTORY_TOKENS, the oldest exchanges are removed. A failed request without any action
is removed (it must not wait for an answer). The reasoning of the model is never stored.
"""
import json

from facebook_agent.agent.limits import CHARS_PER_TOKEN

KEEP_EXCHANGES = 1        # échanges précédents gardés en entier (LLM_HISTORY_EXCHANGES)
MAX_HISTORY_TOKENS = 2500  # au-delà (prompt système + historique, estimation), les plus anciens sont retirés
MAX_OLD_ANSWER_CHARS = 200


def _compact_exchange(exchange: list[dict]) -> list[dict]:
    """An old exchange reduced to the request and the final answer (tool calls and results removed).

    The IDs needed later are kept by the executor (provenance), not by the history.
    """
    request = exchange[0]
    answers = [m for m in exchange[1:] if m.get("role") == "assistant" and not m.get("tool_calls")
               and isinstance(m.get("content"), str) and m["content"].strip()]
    if not answers:
        return [request]
    answer = answers[-1]["content"]
    if len(answer) > MAX_OLD_ANSWER_CHARS:
        answer = answer[:MAX_OLD_ANSWER_CHARS] + "…"
    return [request, {"role": "assistant", "content": answer}]


class History:
    """Exchanges of the conversation: the last ones whole, the old ones reduced, the total bounded."""

    def __init__(self, keep_exchanges: int = KEEP_EXCHANGES, max_tokens: int = MAX_HISTORY_TOKENS) -> None:
        """Start an empty history that keeps keep_exchanges exchanges whole, within max_tokens."""
        self.keep_exchanges = max(1, keep_exchanges)
        self.max_tokens = max_tokens
        self.exchanges: list[list[dict]] = []
        self.compacted = 0  # nombre d'échanges déjà réduits

    def start(self, user_text: str) -> None:
        """Start the exchange of a new request, and reduce the exchanges that became old.

        Args:
            user_text: The request typed by the user.
        """
        self.exchanges.append([{"role": "user", "content": user_text}])
        # Échanges complets gardés en plus de la demande en cours
        old = len(self.exchanges) - 1 - self.keep_exchanges
        while self.compacted < old:
            self.exchanges[self.compacted] = _compact_exchange(self.exchanges[self.compacted])
            self.compacted += 1

    def add(self, message: dict) -> None:
        """Add a message (assistant or tool) to the current exchange.

        Args:
            message: Message in the OpenAI format, without any reasoning field.
        """
        message = {key: value for key, value in message.items() if key != "reasoning"}
        self.exchanges[-1].append(message)

    def last_answer(self) -> str | None:
        """Text of the last final answer before the current request.

        Returns:
            The text, or None if no earlier request got a final answer.
        """
        for exchange in reversed(self.exchanges[:-1]):
            for message in reversed(exchange):
                if (message.get("role") == "assistant" and not message.get("tool_calls")
                        and isinstance(message.get("content"), str) and message["content"].strip()):
                    return message["content"]
        return None

    def close_cancelled(self, note: str) -> None:
        """Close the current exchange after a cancellation: every tool call gets a result, then a final note.

        Groq refuses a history where a tool call has no result; the exchange is kept (actions were done).

        Args:
            note: Final assistant text of the exchange (e.g. "Demande annulée par l'utilisatrice.").
        """
        if not self.exchanges:
            return
        exchange = self.exchanges[-1]
        answered = {m.get("tool_call_id") for m in exchange if m.get("role") == "tool"}
        for message in list(exchange):
            for call in message.get("tool_calls") or []:
                if call["id"] not in answered:
                    exchange.append({"role": "tool", "tool_call_id": call["id"],
                                     "content": json.dumps({"status": "cancelled"})})
        exchange.append({"role": "assistant", "content": note})

    def drop_current(self) -> None:
        """Remove the current exchange (a failed request must not wait for an answer in the history)."""
        if self.exchanges:
            self.exchanges.pop()
            self.compacted = min(self.compacted, len(self.exchanges))

    def messages(self, system_prompt: str) -> list[dict]:
        """Messages to send: the system prompt, then the exchanges, within max_tokens.

        When the estimate goes over max_tokens, the oldest exchanges are removed (never the current
        one), until it fits.

        Args:
            system_prompt: The system prompt.

        Returns:
            The list of messages.
        """
        system = [{"role": "system", "content": system_prompt}]
        while len(self.exchanges) > 1 and self._estimate(system, self.exchanges) > self.max_tokens:
            self.exchanges.pop(0)
            self.compacted = max(self.compacted - 1, 0)
        return system + [m for exchange in self.exchanges for m in exchange]

    @staticmethod
    def _estimate(system: list[dict], exchanges: list[list[dict]]) -> int:
        """Estimated tokens of the system prompt and the exchanges."""
        messages = system + [m for exchange in exchanges for m in exchange]
        return round(len(json.dumps(messages, ensure_ascii=False)) / CHARS_PER_TOKEN)

    def estimate_tokens(self, system_prompt: str = "") -> int:
        """Estimated tokens of the messages that the next request will send.

        Args:
            system_prompt: The system prompt.

        Returns:
            The estimate (about 3.6 characters per token).
        """
        return self._estimate([{"role": "system", "content": system_prompt}], self.exchanges)

    def reset(self) -> None:
        """Empty the history (/reset)."""
        self.exchanges.clear()
        self.compacted = 0
