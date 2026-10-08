"""Auth subcommand - configure OAuth credentials."""

import argparse
import re
from collections.abc import Callable
from typing import TYPE_CHECKING

from gtasks import defaults
from gtasks.cli import ui
from gtasks.cli.errors import Cancelled
from gtasks.client.cache_store import clear_cache
from gtasks.client.client_factory import auth
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider

_SETUP_INSTRUCTIONS = """
To use gtasks, you need a Google OAuth client ID and secret.

To get them:
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create an OAuth 2.0 Client ID (application type: Desktop app)
  3. Copy the Client ID and Client Secret below

Enter 'q' at any prompt to cancel.
"""


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
            ui.info("Invalid input. Double check that you entered the correct client ID.")
        else:
            break
    while True:
        client_secret = input_fn("Enter the client secret: ").strip()
        if client_secret == "q":
            return None
        elif not validate_client_secret(client_secret):
            ui.info("Invalid input. Double check that you entered the correct client secret.")
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


def cmd_auth(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'auth' command to configure OAuth credentials.

    Never calls `get_client`: building a client needs the credentials this
    command exists to create. Both params are unused; they match the uniform
    dispatch signature main() calls args.func with.
    """
    ui.info(_SETUP_INSTRUCTIONS)
    result = prompt_setup_credentials()
    if result is None:
        raise Cancelled()

    client_id, client_secret = result
    auth(defaults.token_file(), client_id, client_secret)
    # Cached data is per account, so this is tidiness, not correctness: drop what a previous
    # sign-in left behind.
    clear_cache(defaults.CACHE_DIR)
    ui.success("Authenticated. You're ready to use gtasks.")


def add_subparser_auth(subparsers) -> None:
    """Add the 'auth' subcommand to configure OAuth credentials."""
    auth_parser = subparsers.add_parser(
        "auth",
        help="Set up Google OAuth credentials",
        description="Interactively enter your Google OAuth client ID and secret to authenticate.",
    )
    auth_parser.set_defaults(func=cmd_auth)
