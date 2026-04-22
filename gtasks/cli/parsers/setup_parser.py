"""Setup subcommand - configure OAuth credentials."""

import argparse
import sys
from functools import partial

from gtasks.cli.cli_utils import prompt_setup_credentials
from gtasks.client.client_factory import auth
from gtasks.defaults import APP_CFG_PATH

TOKEN_PATH = APP_CFG_PATH / "token.pickle"


_SETUP_INSTRUCTIONS = """
To use gtasks, you need a Google OAuth client ID and secret.

To get them:
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create an OAuth 2.0 Client ID (application type: Desktop app)
  3. Copy the Client ID and Client Secret below

Enter 'q' at any prompt to cancel.
"""


def cmd_setup(args: argparse.Namespace) -> None:
    """Handle the 'setup' command to configure OAuth credentials."""
    print(_SETUP_INSTRUCTIONS)
    result = prompt_setup_credentials()
    if result is None:
        print("Setup cancelled.")
        sys.exit(1)

    client_id, client_secret = result
    auth(TOKEN_PATH, client_id, client_secret)
    print("Authentication successful. You're ready to use gtasks.")


def add_subparser_setup(subparsers) -> None:
    """Add the 'setup' subcommand to configure OAuth credentials."""
    setup_parser = subparsers.add_parser(
        "setup",
        help="Configure Google OAuth credentials",
        description="Interactively enter your Google OAuth client ID and secret to authenticate.",
    )
    setup_parser.set_defaults(func=cmd_setup)
