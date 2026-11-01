"""Cancel a request from outside its thread (the "Annuler la demande" button of the web interface).

The terminal cancels with Ctrl+C (KeyboardInterrupt). The web interface runs each request in a
separate thread, where Ctrl+C cannot reach: it arms a Cancellation instead. The waits of the agent
(Groq pauses, network retries, confirmation) then raise RequestCancelled, a KeyboardInterrupt, so
that the request stops exactly as with Ctrl+C and Agent.cancel_request() applies unchanged.
"""
import threading

CTRL_C_HINT = "Ctrl+C annule la demande en cours et revient à « Toi > »."
BUTTON_HINT = "Le bouton « Annuler la demande » l'arrête."


class RequestCancelled(KeyboardInterrupt):
    """The user cancelled the current request (handled like Ctrl+C)."""


class Cancellation:
    """Cancellation flag of the current request, shared by the page and the thread of the request."""

    def __init__(self) -> None:
        """Start without cancellation."""
        self._event = threading.Event()

    @property
    def cancelled(self) -> bool:
        """Whether the current request was cancelled.

        Returns:
            True once cancel() was called (until clear()).
        """
        return self._event.is_set()

    def cancel(self) -> None:
        """Arm the flag: the next wait or check of the request raises RequestCancelled."""
        self._event.set()

    def clear(self) -> None:
        """Disarm the flag, before a new request."""
        self._event.clear()

    def check(self) -> None:
        """Raise RequestCancelled if the request was cancelled.

        Raises:
            RequestCancelled: cancel() was called.
        """
        if self._event.is_set():
            raise RequestCancelled()

    def sleep(self, seconds: float) -> None:
        """Wait like time.sleep, but stop at once when the request is cancelled.

        Args:
            seconds: Duration of the wait.

        Raises:
            RequestCancelled: cancel() was called before or during the wait.
        """
        if self._event.wait(max(seconds, 0.0)):
            raise RequestCancelled()
