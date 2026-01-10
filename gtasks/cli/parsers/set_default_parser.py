"""Set-default subcommand - set the default task list."""

import argparse
from functools import partial

from gtasks.cli import cli_utils
from gtasks.client.client_factory import build_cached_client
from gtasks.utils.config import Config


def cmd_set_default(args: argparse.Namespace, cfg: Config) -> None:
    """Handle the 'set-default' command to set a default task list."""
    client = build_cached_client()
    tasklists = client.get_tasklists()
    current_default = cfg.get_tasklist_title()
    choice = cli_utils.prompt_index_choice(
        tasklists,
        "Select a default task list",
        current_hint=current_default,
    )
    if choice is not None:
        selected_title = tasklists[choice].get("title", "")
        cfg.set_tasklist_title(selected_title)
        print(f"Default task list set to: {selected_title}")


def add_set_default_subparser(subparsers, cfg: Config) -> None:
    """Add the 'set-default' subcommand to set default task list."""
    set_default_parser = subparsers.add_parser(
        "set-default",
        help="Set the default task list",
        description="Interactively select and save a default task list.",
    )
    set_default_parser.set_defaults(func=partial(cmd_set_default, cfg=cfg))
