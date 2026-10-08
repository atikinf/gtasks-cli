"""Interactive prompts and shared argparse options."""

import argparse
from collections.abc import Callable
from typing import Any

HINT = "Please choose a number between 1 and {num_options} or 'q' to cancel."


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
