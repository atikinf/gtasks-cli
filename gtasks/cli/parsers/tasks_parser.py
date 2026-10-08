"""Tasks subcommand - list tasks from a task list."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option
from gtasks.cli.task_order import display_order
from gtasks.cli.title_id_resolution import (
    TargetList,
    add_tasklist_option,
    resolve_target_tasklist,
)
from gtasks.utils.config import Config
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider, TasksClient

# How many tasks the at-a-glance view shows: bare `gtasks`, and `use` after switching.
DEFAULT_LIMIT = 10


def cmd_tasks(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'tasks' command (and bare `gtasks`) to display open tasks."""
    client = get_client()
    target = resolve_target_tasklist(args, client, cfg)
    show_tasks(client, target, limit=args.limit, show_ids=args.show_ids)


def show_tasks(
    client: "TasksClient", target: TargetList, *, limit: int | None, show_ids: bool = False
) -> None:
    """Fetch and print a list's open tasks in the app's order (subtasks under their parent),
    and record the listing so `done 3` / `delete 3` hit what was shown."""
    # TODO: "show completed" mode — fetch needsAction tasks here, then read
    # recently completed tasks from a local cache (populated by `gtasks done`)
    # to append as strikethrough, avoiding a second API call. Configurable via `gtasks config`.
    # The whole list: the API's order (most recently updated first) isn't the displayed one,
    # so the limit can only apply after ordering. (The cache fetches it all regardless.)
    tasks = display_order(client.get_tasks(target.id, show_completed=False))
    truncated = limit is not None and len(tasks) > limit
    tasks = tasks[:limit] if truncated else tasks

    ui.render_tasks(
        tasks,
        heading=target.title,
        show_ids=show_ids,
        truncated=truncated,
        cache=client.tasks_cache_state(target.id),
    )
    ListingState.default().save(target.id, tasks)


def add_subparser_tasks(subparsers) -> None:
    """Add the 'tasks' subcommand to list tasks."""
    tasks_parser = subparsers.add_parser(
        "tasks",
        help="List open tasks",
        description="Display open tasks from the active (or given) task list.",
    )
    add_tasklist_option(tasks_parser)
    tasks_parser.add_argument(
        "-n",
        "--limit",
        type=int,
        default=None,
        help="Maximum number of tasks to display",
    )
    tasks_parser.add_argument(
        "--show-ids",
        action="store_true",
        help="Include task IDs in the output",
    )
    add_refresh_option(tasks_parser)
    tasks_parser.set_defaults(func=cmd_tasks)
