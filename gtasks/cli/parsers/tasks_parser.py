"""Tasks subcommand - list tasks from a task list."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.tasklist_resolution import add_tasklist_option, resolve_target_tasklist
from gtasks.utils.config import Config
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from gtasks.client.protocol import TasksClient


def cmd_list_tasks(args: argparse.Namespace, client: "TasksClient", cfg: Config) -> None:
    """Handle the 'tasks' command (and bare `gtasks`) to display open tasks."""
    target = resolve_target_tasklist(args, client, cfg)

    # TODO: "show completed" mode — fetch needsAction tasks here, then read
    # recently completed tasks from a local cache (populated by `gtasks done`)
    # to append as strikethrough, avoiding a second API call. Configurable via `gtasks config`.
    # Fetch one extra row to learn whether the limit hid anything.
    fetch_limit = args.limit + 1 if args.limit is not None else None
    tasks = client.get_tasks(target.id, fetch_limit, show_completed=False)
    truncated = args.limit is not None and len(tasks) > args.limit
    tasks = tasks[: args.limit] if truncated else tasks

    ui.render_tasks(tasks, heading=target.title, show_ids=args.show_ids, truncated=truncated)
    ListingState.beside(cfg).save(target.id, tasks)


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
        help="Include task IDs in output",
    )
    tasks_parser.set_defaults(func=cmd_list_tasks)
