"""User-facing CLI errors."""


class CliError(Exception):
    """An error the user can act on.

    Handlers raise this instead of printing and calling sys.exit(); main() renders it
    via ui.error() and exits with `exit_code`.
    """

    def __init__(self, message: str, *, hint: str | None = None, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.exit_code = exit_code


class Cancelled(CliError):
    """The user backed out of an interactive prompt."""

    def __init__(self) -> None:
        super().__init__("Cancelled.", exit_code=130)
