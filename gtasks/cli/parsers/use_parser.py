"""Use subcommand - set the active task list."""

import argparse
from typing import TYPE_CHECKING

from rich.text import Text

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option, prompt_index_choice
from gtasks.cli.completion import attach, complete_tasklists
from gtasks.cli.errors import Cancelled
from gtasks.cli.parsers.lists_parser import show_tasklists
from gtasks.cli.parsers.tasks_parser import DEFAULT_LIMIT, show_tasks
from gtasks.cli.title_id_resolution import TargetList, find_tasklist, set_active_tasklist
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider


def cmd_use(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'use' command to set the active task list, then show it."""
    client = get_client()
    if args.name is None:
        tasklists = show_tasklists(client, cfg, require_any=True)
        choice = prompt_index_choice(len(tasklists), "Make which list active?", input)
        if choice is None:
            raise Cancelled()
        tasklist = tasklists[choice]
    else:
        tasklist = find_tasklist(client, args.name)

    set_active_tasklist(cfg, tasklist)
    ui.success(Text.assemble("Active list: ", (tasklist.get("title", ""), "heading")))

    # Show the list as bare `gtasks` would (from the cache unless --refresh), and number it
    # for `done 3`.
    target = TargetList(tasklist["id"], tasklist.get("title", ""))
    show_tasks(client, target, limit=DEFAULT_LIMIT)


def add_subparser_use(subparsers) -> None:
    """Add the 'use' subcommand to set the active task list."""
    use_parser = subparsers.add_parser(
        "use",
        help="Set the active task list",
        description=(
            "Set the task list that commands act on when no -l/--list is given, then show "
            "its first tasks. Pick interactively if no name is given."
        ),
    )
    name_arg = use_parser.add_argument(
        "name",
        type=str,
        nargs="?",
        default=None,
        help="Name of the task list to make active",
    )
    attach(name_arg, complete_tasklists)
    add_refresh_option(use_parser)
    use_parser.set_defaults(func=cmd_use)
