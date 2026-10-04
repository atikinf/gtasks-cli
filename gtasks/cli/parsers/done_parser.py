"""Done subcommand - mark a task as complete."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option
from gtasks.cli.completion import attach, complete_tasks
from gtasks.cli.title_id_resolution import (
    add_tasklist_option,
    resolve_target_tasklist,
    resolve_tasks_from_inputs,
)
from gtasks.utils.config import Config
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider


def cmd_done(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'done' command to mark one or more tasks complete."""
    # Fresh: stale data here could make the write hit the wrong task.
    client = get_client(fresh=True)
    target = resolve_target_tasklist(args, client, cfg)
    listing = ListingState.default()
    tasks = resolve_tasks_from_inputs(args.tasks, client, target.id, listing).tasks

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
    tasks_arg = done_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles (or a unique part of one), or numbers as shown by `gtasks`, to mark complete",
    )
    attach(tasks_arg, complete_tasks)
    add_tasklist_option(done_parser)
    add_refresh_option(done_parser)
    done_parser.set_defaults(func=cmd_done)
