"""Lists subcommand - list all task lists."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option
from gtasks.cli.errors import CliError
from gtasks.cli.title_id_resolution import set_active_tasklist
from gtasks.utils.config import Config, ConfigKey

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import TaskList

    from gtasks.client.protocol import ClientProvider, TasksClient


def cmd_lists(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'lists' command to display task lists, marking the active one."""
    show_tasklists(get_client(), cfg, limit=args.limit, show_ids=args.show_ids)


def show_tasklists(
    client: "TasksClient",
    cfg: Config,
    *,
    limit: int | None = None,
    show_ids: bool = False,
    require_any: bool = False,
) -> "list[TaskList]":
    """Fetch and print the task lists (marking the active one), and return the ones shown.

    Shared by `lists` and the `use` picker, so both keep the active list's stored title current.
    `require_any` makes having no lists an error (raised before printing anything) rather than
    an empty listing.
    """
    # All of them, so the title sync below sees the active list even past the limit. (The
    # cache fetches them all regardless.)
    tasklists = client.get_tasklists()
    if require_any and not tasklists:
        raise CliError(ui.NO_TASKLISTS, hint="Create one in Google Tasks first.")
    active_id = cfg.get(ConfigKey.ACTIVE_TASKLIST_ID)

    # The active list's title is stored for headings; refresh it if renamed elsewhere.
    for tasklist in tasklists:
        title = tasklist.get("title")
        if tasklist.get("id") == active_id and title and title != cfg.get(
            ConfigKey.ACTIVE_TASKLIST_TITLE
        ):
            set_active_tasklist(cfg, tasklist)

    truncated = limit is not None and len(tasklists) > limit
    tasklists = tasklists[:limit] if truncated else tasklists
    ui.render_tasklists(
        tasklists,
        heading="Task lists",
        active_id=active_id,
        show_ids=show_ids,
        truncated=truncated,
        cache=client.tasklists_cache_state(),
    )
    return tasklists


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
        help="Include task list IDs in the output",
    )
    add_refresh_option(lists_parser)
    lists_parser.set_defaults(func=cmd_lists)
