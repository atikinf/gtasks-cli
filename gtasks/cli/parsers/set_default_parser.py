"""Set-default subcommand - set the default task list."""

import argparse
from functools import partial

from gtasks.cli import cli_utils
from gtasks.cli.cli_utils import print_tasklists
from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config


def cmd_set_default(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'set-default' command to set a default task list."""
    tasklists = client.get_tasklists()
    print_tasklists(tasklists, argparse.Namespace(show_ids=False))
    choice = cli_utils.prompt_index_choice(
        len(tasklists), "Select a default task list", input
    )
    if choice is not None:
        selected_title = tasklists[choice].get("title", "")
        cfg.set_tasklist_title(selected_title)
        print(f"Default task list set to: {selected_title}")


def add_subparser_set_default(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'set-default' subcommand to set default task list."""
    set_default_parser = subparsers.add_parser(
        "set-default",
        help="Set the default task list",
        description="Interactively select and save a default task list.",
    )
    set_default_parser.set_defaults(
        func=partial(cmd_set_default, client=client, cfg=cfg)
    )
