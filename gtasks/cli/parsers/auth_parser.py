"""Auth subcommand - configure OAuth credentials."""

import argparse
import sys

from gtasks.cli.cli_utils import prompt_setup_credentials
from gtasks.client.api_client import ApiClient
from gtasks.client.client_factory import auth
from gtasks.defaults import APP_CFG_PATH
from gtasks.utils.config import Config

TOKEN_PATH = APP_CFG_PATH / "token.pickle"


_SETUP_INSTRUCTIONS = """
To use gtasks, you need a Google OAuth client ID and secret.

To get them:
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create an OAuth 2.0 Client ID (application type: Desktop app)
  3. Copy the Client ID and Client Secret below

Enter 'q' at any prompt to cancel.
"""


def cmd_auth(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'auth' command to configure OAuth credentials.

    Unlike every other command, 'auth' doesn't need an API client or config -
    it exists to create the credentials those other commands depend on. It
    still takes both params to match the uniform dispatch signature main()
    calls args.func with; they're unused here.
    """
    print(_SETUP_INSTRUCTIONS)
    result = prompt_setup_credentials()
    if result is None:
        print("Setup cancelled.")
        sys.exit(1)

    client_id, client_secret = result
    auth(TOKEN_PATH, client_id, client_secret)
    print("Authentication successful. You're ready to use gtasks.")


def add_subparser_auth(subparsers) -> None:
    """Add the 'auth' subcommand to configure OAuth credentials."""
    auth_parser = subparsers.add_parser(
        "auth",
        help="Configure Google OAuth credentials",
        description="Interactively enter your Google OAuth client ID and secret to authenticate.",
    )
    auth_parser.set_defaults(func=cmd_auth)
