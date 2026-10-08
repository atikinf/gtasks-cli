"""Interactive prompts, input validation and shared argparse options."""

import argparse
import re
from collections.abc import Callable
from typing import Any

HINT = "Please choose a number between 1 and {num_options} or 'q' to cancel."


def prompt_setup_credentials(
    input_fn: Callable[[str], str] = input,
) -> None | tuple[str, str]:
    client_id: None | str
    client_secret: None | str
    while True:
        # Trimmed: values pasted from the Cloud console often carry stray whitespace.
        client_id = input_fn("Enter the client ID: ").strip()
        if client_id == "q":
            return None
        elif not validate_client_id(client_id):
            print("Invalid input. Double check that you entered the correct client ID.")
        else:
            break
    while True:
        client_secret = input_fn("Enter the client secret: ").strip()
        if client_secret == "q":
            return None
        elif not validate_client_secret(client_secret):
            print(
                "Invalid input. Double check that you entered the correct client secret."
            )
        else:
            break
    return client_id, client_secret


def validate_client_id(client_id: str) -> bool:
    """
    Expected format: {digits}-{alphanumeric}.apps.googleusercontent.com
    """
    pattern = r"\d{5,20}-[a-z0-9]{20,50}\.apps\.googleusercontent\.com"
    return re.fullmatch(pattern, client_id) is not None


def validate_client_secret(client_secret: str) -> bool:
    """
    Expected format: {alphanumeric with possible hyphens}
    """
    pattern = r"[A-Za-z0-9_-]{20,50}"
    return re.fullmatch(pattern, client_secret) is not None


def prompt_yes_no(question: str, input_fn: Callable[[str], str] | None = None) -> bool:
    """Ask a yes/no question; anything but y/yes (including just Enter) means no."""
    answer = (input_fn or input)(f"{question} [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def prompt_index_choice(
    num_options: int,
    prompt_prefix: str,
    input_fn: Callable[[str], str] = input,  # solely for testability
) -> int | None:
    assert num_options > 0

    if num_options == 1:
        return 0

    while True:
        choice_str: str = input_fn(
            f"{prompt_prefix} [1-{num_options}] (or 'q' to cancel): "
        ).strip()

        if choice_str.lower() == "q":
            return None

        if not choice_str.isdigit():
            print("Invalid input. " + HINT.format(num_options=num_options))
            continue

        choice = int(choice_str)
        if 1 <= choice <= num_options:
            return choice - 1  # Convert to 0-based index

        print("Out of range. " + HINT.format(num_options=num_options))


def add_shared_option(
    parser: argparse.ArgumentParser,
    *flags: str,
    top_level: bool,
    default: Any,
    **kwargs: Any,
) -> argparse.Action:
    """Register an option accepted both before and after the subcommand.

    Register it on the top-level parser (`top_level=True`, which owns `default`) and on each
    subparser. Subparser copies default to SUPPRESS: otherwise their default would overwrite
    a value given before the subcommand, as in `gtasks -l Work done 1`.
    """
    return parser.add_argument(
        *flags,
        default=default if top_level else argparse.SUPPRESS,
        **kwargs,
    )


def add_refresh_option(parser: argparse.ArgumentParser, *, top_level: bool = False) -> None:
    """Register --refresh: ignore cached data and fetch everything fresh."""
    add_shared_option(
        parser,
        "--refresh",
        top_level=top_level,
        default=False,
        action="store_true",
        help="Ignore cached data and fetch fresh from Google Tasks",
    )
