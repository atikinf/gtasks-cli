"""Add subcommand - add a new task."""

import argparse
from typing import TYPE_CHECKING

import dateparser

from gtasks.cli import ui
from gtasks.cli.errors import CliError
from gtasks.cli.tasklist_resolution import add_tasklist_option, resolve_target_tasklist
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import TasksClient


def parse_due_date(date_str: str) -> str:
    """Parse a human-readable date string and return an RFC 3339 timestamp.

    Uses dateparser with PREFER_DATES_FROM=future so relative expressions like
    "monday" or "next week" resolve to upcoming dates rather than past ones.
    Always normalises to midnight UTC since the Tasks API ignores the time component.
    """
    dt = dateparser.parse(
        date_str,
        settings={
            "PREFER_DATES_FROM": "future",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TO_TIMEZONE": "UTC",
        },
    )
    if dt is None:
        raise ValueError(f"Could not parse due date: {date_str!r}")
    return dt.strftime("%Y-%m-%dT00:00:00.000Z")


def cmd_add_task(args: argparse.Namespace, client: "TasksClient", cfg: Config) -> None:
    """Handle the 'add' command to create a new task."""
    # Parse the date before touching the API so a typo fails fast.
    try:
        due = parse_due_date(args.due) if args.due else None
    except ValueError as e:
        raise CliError(str(e), hint="Try 'tomorrow', 'next friday' or '2026-05-01'.") from e

    target = resolve_target_tasklist(args, client, cfg)
    task = client.add_task(
        tasklist_id=target.id,
        task_title=args.title,
        notes=args.notes,
        due=due,
    )
    ui.report_mutation("Added", [task.get("title", args.title)], target.title)


def add_subparser_add_task(subparsers) -> None:
    """Add the 'add' subcommand to create a new task."""
    add_parser = subparsers.add_parser(
        "add",
        help="Add a new task",
        description="Create a new task in the active (or given) task list.",
    )
    add_parser.add_argument(
        "title",
        type=str,
        help="Title of the task to create",
    )
    add_tasklist_option(add_parser)
    add_parser.add_argument(
        "-n",
        "--notes",
        type=str,
        default=None,
        help="Notes for the task",
    )
    add_parser.add_argument(
        "-d",
        "--due",
        type=str,
        default=None,
        help="Due date (natural language e.g. 'tomorrow', 'next friday', '2026-05-01')",
    )
    add_parser.set_defaults(func=cmd_add_task)
