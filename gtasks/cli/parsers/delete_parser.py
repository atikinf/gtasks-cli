"""Delete subcommand - delete tasks by name or display index."""

import argparse
from collections.abc import Callable
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.task_resolution import resolve_tasks_from_inputs
from gtasks.cli.tasklist_resolution import add_tasklist_option, resolve_target_tasklist
from gtasks.utils.config import Config
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from gtasks.client.protocol import TasksClient


def cmd_delete(
    args: argparse.Namespace, get_client: "Callable[[], TasksClient]", cfg: Config
) -> None:
    """Handle the 'delete' command to remove one or more tasks."""
    client = get_client()
    target = resolve_target_tasklist(args, client, cfg)
    listing = ListingState.beside(cfg)
    tasks = resolve_tasks_from_inputs(args.tasks, client, target.id, listing)

    task_ids = [t["id"] for t in tasks]
    client.delete_tasks(target.id, task_ids)
    listing.consume(target.id, task_ids)
    ui.report_mutation("Deleted", [t.get("title", "?") for t in tasks], target.title)


def add_subparser_delete(subparsers) -> None:
    """Add the 'delete' subcommand to remove one or more tasks."""
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete one or more tasks",
        description="Delete tasks by title or the number shown by `gtasks` (e.g. 'gtasks delete 1 3' or 'gtasks delete \"Buy milk\"').",  # noqa: E501
    )
    delete_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles, or numbers as shown by `gtasks`, of tasks to delete",
    )
    add_tasklist_option(delete_parser)
    delete_parser.set_defaults(func=cmd_delete)
