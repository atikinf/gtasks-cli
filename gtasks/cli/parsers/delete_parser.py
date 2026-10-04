"""Delete subcommand - delete tasks by name or display index."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option, prompt_yes_no
from gtasks.cli.completion import attach, complete_tasks
from gtasks.cli.errors import Cancelled
from gtasks.cli.title_id_resolution import (
    add_tasklist_option,
    resolve_target_tasklist,
    resolve_tasks_from_inputs,
)
from gtasks.utils.config import Config
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider


def cmd_delete(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'delete' command to remove one or more tasks."""
    # Fresh: stale data here could make the write hit the wrong task.
    client = get_client(fresh=True)
    target = resolve_target_tasklist(args, client, cfg)
    listing = ListingState.default()
    resolved = resolve_tasks_from_inputs(args.tasks, client, target.id, listing)
    tasks = resolved.tasks
    # A fragment picked these titles, not the user: confirm before an irreversible delete.
    if resolved.partial and not args.yes:
        _confirm_delete(tasks, target.title)

    task_ids = [t["id"] for t in tasks]
    client.delete_tasks(target.id, task_ids)
    listing.consume(target.id, task_ids)
    ui.report_mutation("Deleted", [t.get("title", "?") for t in tasks], target.title)


def _confirm_delete(tasks: list, tasklist_title: str) -> None:
    titles = [t.get("title", "?") for t in tasks]
    what = f"'{titles[0]}'" if len(titles) == 1 else f"{len(titles)} tasks ({', '.join(titles)})"
    if not prompt_yes_no(f"Delete {what} from {tasklist_title}?"):
        raise Cancelled()


def add_subparser_delete(subparsers) -> None:
    """Add the 'delete' subcommand to remove one or more tasks."""
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete one or more tasks",
        description="Delete tasks by title or the number shown by `gtasks` (e.g. 'gtasks delete 1 3' or 'gtasks delete \"Buy milk\"').",  # noqa: E501
    )
    tasks_arg = delete_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles (or a unique part of one), or numbers as shown by `gtasks`, to delete",
    )
    attach(tasks_arg, complete_tasks)
    delete_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="don't ask before deleting tasks matched by part of their title",
    )
    add_tasklist_option(delete_parser)
    add_refresh_option(delete_parser)
    delete_parser.set_defaults(func=cmd_delete)
