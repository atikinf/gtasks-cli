"""Use subcommand - set the active task list."""

import argparse
from functools import partial

from gtasks.cli import cli_utils
from gtasks.cli.cli_utils import print_tasklists, prompt_choose_tasklist_id
from gtasks.client.api_client import ApiClient
from gtasks.client.client_utils import resolve_tasklist_id
from gtasks.utils.config import Config


def cmd_use(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'use' command to set the active task list."""
    tasklists = client.get_tasklists()

    if args.name is None:
        print_tasklists(tasklists, argparse.Namespace(show_ids=False))
        choice = cli_utils.prompt_index_choice(
            len(tasklists), "Select an active task list", input
        )
        if choice is None:
            return
        selected_title = tasklists[choice].get("title", "")
    else:
        ids = resolve_tasklist_id(args.name, tasklists)
        tasklist_id = prompt_choose_tasklist_id(ids, tasklists, args.name)
        if tasklist_id is None:
            return
        selected_title = args.name

    cfg.set_tasklist_title(selected_title)
    print(f"Active task list set to: {selected_title}")


def add_subparser_use(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'use' subcommand to set the active task list.

    Replaces set-default. Adds an optional positional name arg so
    `gtasks use "Work"` sets directly by name; omitting it falls back
    to the interactive picker.
    """
    use_parser = subparsers.add_parser(
        "use",
        help="Set the active task list",
        description="Set the active task list by name, or pick interactively if no name given.",
    )
    use_parser.add_argument(
        "name",
        type=str,
        nargs="?",
        default=None,
        help="Name of the task list to set as active",
    )
    use_parser.set_defaults(func=partial(cmd_use, client=client, cfg=cfg))
