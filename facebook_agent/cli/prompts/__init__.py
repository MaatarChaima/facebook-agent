class InvalidInputError(Exception):
    """Raised by a prompt when the user input is invalid.

    ``errors`` holds the list of messages to display. The menu catches this
    exception and returns to the menu instead of stopping the program.
    """

    def __init__(self, errors: list[str]):
        """Store the error messages to display."""
        super().__init__("; ".join(errors))
        self.errors = errors
