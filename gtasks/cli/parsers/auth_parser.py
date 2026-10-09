"""Auth subcommand - configure OAuth credentials."""

import argparse
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from rich.text import Text

from gtasks import defaults
from gtasks.cli import ui
from gtasks.cli.cli_utils import prompt_yes_no
from gtasks.cli.errors import Cancelled
from gtasks.client.cache_store import clear_cache
from gtasks.client.client_factory import (
    SignInRequiredError,
    read_creds_from_file,
    refresh_saved_sign_in,
    sign_in,
)
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider

_SETUP_INSTRUCTIONS = """
To use gtasks, you need your own Google OAuth client ID and secret.
Step-by-step guide:
  https://github.com/atikinf/gtasks-cli/blob/master/docs/setup.md

In short, in the Google Cloud console (https://console.cloud.google.com/):
  1. Enable the Google Tasks API for a project.
  2. Under Google Auth platform > Audience, add yourself as a test user
     (or publish the app, to avoid signing in again every 7 days).
  3. Under Google Auth platform > Clients, create a "Desktop app" client.
     Copy its ID and secret right away: the secret is shown only once.

Enter 'q' at any prompt to cancel.
"""


def prompt_setup_credentials(
    input_fn: Callable[[str], str] | None = None,
    current: tuple[str, str] | None = None,
) -> None | tuple[str, str]:
    """Ask for the client ID and secret; None if the user cancels ('q').

    With `current` (the saved sign-in's client), Enter keeps each value; the defaults are shown
    shortened and dimmed (`mask_client_id`, `mask_secret`). A new client ID gets no default
    secret, since a secret belongs to its client.
    """
    current_id, current_secret = current or (None, None)
    client_id = _prompt_value(
        input_fn,
        "client ID",
        validate_client_id,
        default=current_id,
        shown=mask_client_id(current_id) if current_id else None,
    )
    if client_id is None:
        return None
    default_secret = current_secret if client_id == current_id else None
    client_secret = _prompt_value(
        input_fn,
        "client secret",
        validate_client_secret,
        default=default_secret,
        shown=mask_secret(default_secret) if default_secret else None,
    )
    if client_secret is None:
        return None
    return client_id, client_secret


def _prompt_value(
    input_fn: Callable[[str], str] | None,
    label: str,
    validate: Callable[[str], bool],
    *,
    default: str | None,
    shown: str | None,
) -> str | None:
    # The default is dimmed, so it reads as a hint rather than part of the question.
    hint = Text(f" [{shown}]", style="muted") if shown else Text("")
    prompt = Text.assemble(f"Enter the {label}", hint, ": ")
    while True:
        # Trimmed: values pasted from the Cloud console often carry stray whitespace.
        value = ui.ask(prompt, input_fn).strip()
        if value == "q":
            return None
        if not value and default is not None:
            return default
        if validate(value):
            return value
        ui.info(f"Invalid input. Double check that you entered the correct {label}.")


def mask_client_id(client_id: str) -> str:
    """A client ID shortened to its distinguishing ends:
    `1234...-...abcd.apps.googleusercontent.com`."""
    match = re.fullmatch(r"(\d+)-([a-z0-9]+)(\.apps\.googleusercontent\.com)", client_id)
    if match is None:
        return client_id  # not the usual shape: show it as is
    number, name, domain = match.groups()
    return f"{number[:4]}...-...{name[-4:]}{domain}"


def mask_secret(secret: str) -> str:
    """How the Cloud console shows a client secret: only its last 4 characters."""
    return "****" + secret[-4:]


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


def cmd_auth(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'auth' command: sign in, or keep / replace the existing sign-in.

    Never calls `get_client`: building a client needs the credentials this
    command exists to create. Both params are unused; they match the uniform
    dispatch signature main() calls args.func with.
    """
    token_path = defaults.token_file()
    saved = read_creds_from_file(token_path)
    current = (
        (saved.client_id, saved.client_secret)
        if saved is not None and saved.client_id and saved.client_secret
        else None
    )
    if current is None:
        ui.info(_SETUP_INSTRUCTIONS)
    else:
        ui.info("You're signed in. Press Enter to keep each value ('q' cancels).")

    result = prompt_setup_credentials(current=current)
    if result is None:
        raise Cancelled()

    if result == current and not prompt_yes_no(
        "Sign in again (e.g. as a different Google account)?"
    ):
        try:
            refresh_saved_sign_in(token_path)
        except SignInRequiredError:
            ui.info("Your saved sign-in no longer works, so let's sign in again.")
        else:
            ui.success("Still signed in. Nothing changed.")
            return

    client_id, client_secret = result
    sign_in(token_path, client_id, client_secret)
    # Cached data is per account, so this is tidiness, not correctness: drop what a previous
    # sign-in left behind.
    clear_cache(defaults.CACHE_DIR)
    ui.success("Signed in. You're ready to use gtasks.")


def add_subparser_auth(subparsers) -> None:
    """Add the 'auth' subcommand to configure OAuth credentials."""
    auth_parser = subparsers.add_parser(
        "auth",
        help="Set up Google OAuth credentials",
        description="Interactively enter your Google OAuth client ID and secret to authenticate.",
    )
    auth_parser.set_defaults(func=cmd_auth)
