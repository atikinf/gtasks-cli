"""Auth subcommand - configure OAuth credentials."""

import argparse
from typing import TYPE_CHECKING

from gtasks import defaults
from gtasks.cli import ui
from gtasks.cli.cli_utils import prompt_setup_credentials
from gtasks.cli.errors import Cancelled
from gtasks.client.cache_store import clear_cache
from gtasks.client.client_factory import auth
from gtasks.defaults import APP_CFG_PATH
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider

TOKEN_PATH = APP_CFG_PATH / "token.pickle"


_SETUP_INSTRUCTIONS = """
To use gtasks, you need a Google OAuth client ID and secret.

To get them:
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create an OAuth 2.0 Client ID (application type: Desktop app)
  3. Copy the Client ID and Client Secret below

Enter 'q' at any prompt to cancel.
"""


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
    auth(TOKEN_PATH, client_id, client_secret)
    # Cached data is per account, so this is tidiness, not correctness: drop what a previous
    # sign-in left behind.
    clear_cache(defaults.CACHE_DIR)
    ui.success("Authenticated. You're ready to use gtasks.")


def add_subparser_auth(subparsers) -> None:
    """Add the 'auth' subcommand to configure OAuth credentials."""
    auth_parser = subparsers.add_parser(
        "auth",
        help="Setup Google OAuth credentials",
        description="Interactively enter your Google OAuth client ID and secret to authenticate.",
    )
    auth_parser.set_defaults(func=cmd_auth)
