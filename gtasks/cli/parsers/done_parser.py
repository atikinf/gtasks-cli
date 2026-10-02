"""Done subcommand - mark a task as complete."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.task_resolution import resolve_tasks_from_inputs
from gtasks.cli.tasklist_resolution import add_tasklist_option, resolve_target_tasklist
from gtasks.utils.config import Config
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from gtasks.client.protocol import TasksClient


def cmd_done(args: argparse.Namespace, client: "TasksClient", cfg: Config) -> None:
    """Handle the 'done' command to mark one or more tasks complete."""
    target = resolve_target_tasklist(args, client, cfg)
    listing = ListingState.beside(cfg)
    tasks = resolve_tasks_from_inputs(args.tasks, client, target.id, listing)

    task_ids = [t["id"] for t in tasks]
    completed = client.complete_tasks(target.id, task_ids)
    listing.consume(target.id, task_ids)
    ui.report_mutation("Completed", [t.get("title", "?") for t in completed], target.title)


def add_subparser_done(subparsers) -> None:
    """Add the 'done' subcommand to mark one or more tasks as complete."""
    done_parser = subparsers.add_parser(
        "done",
        help="Mark one or more tasks as complete",
        description="Mark tasks complete by title or the number shown by `gtasks` (e.g. 'gtasks done 1 3' or 'gtasks done \"Buy milk\"').",  # noqa: E501
    )
    done_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles, or numbers as shown by `gtasks`, of tasks to mark complete",
    )
    add_tasklist_option(done_parser)
    done_parser.set_defaults(func=cmd_done)
