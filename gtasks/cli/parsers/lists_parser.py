"""Lists subcommand - list all task lists."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option
from gtasks.utils.config import Config, ConfigKey

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider


def cmd_list_tasklists(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'lists' command to display task lists, marking the active one."""
    client = get_client()
    tasklists = client.get_tasklists(args.limit)
    active_id = cfg.get(ConfigKey.ACTIVE_TASKLIST_ID)

    # The active list's title is cached for display; refresh it if renamed elsewhere.
    for tasklist in tasklists:
        title = tasklist.get("title")
        if tasklist.get("id") == active_id and title and title != cfg.get(
            ConfigKey.ACTIVE_TASKLIST_TITLE
        ):
            cfg.set(ConfigKey.ACTIVE_TASKLIST_TITLE, title)

    ui.render_tasklists(
        tasklists,
        heading="Task lists",
        active_id=active_id,
        show_ids=args.show_ids,
        cache=client.tasklists_cache_state(),
    )


def add_subparser_lists(subparsers) -> None:
    """Add the 'lists' subcommand to list task lists."""
    lists_parser = subparsers.add_parser(
        "lists",
        help="List all task lists",
        description="Display all task lists for this account; ● marks the active one.",
    )
    lists_parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Maximum number of task lists to display",
    )
    lists_parser.add_argument(
        "--show-ids",
        action="store_true",
        default=False,
        help="Include task list IDs in the output",
    )
    add_refresh_option(lists_parser)
    lists_parser.set_defaults(func=cmd_list_tasklists)
