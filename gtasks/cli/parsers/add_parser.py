"""Add subcommand - add a new task."""

import argparse
import sys
from functools import partial

import dateparser

from gtasks.cli.cli_utils import prompt_choose_tasklist_id
from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config


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


def cmd_add_task(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'add' command to create a new task."""
    tasklist_title: None | str = args.tasklist_title or cfg.get_tasklist_title()
    if tasklist_title is None:
        print(
            "Error: You must specify a --tasklist-title (-t) or set a default tasklist"
        )
        sys.exit(1)

    matches = client.resolve_tasklist_from_title(tasklist_title)

    tasklist_id = prompt_choose_tasklist_id(matches, tasklist_title)

    if tasklist_id is not None:
        task = client.add_task(
            tasklist_id=tasklist_id,
            title=args.title,
            notes=args.notes,
            due=parse_due_date(args.due) if args.due else None,
        )
        print(f"Created task: {task.get('title', '<no title>')}")
    else:
        print(f"Couldn't find a tasklist named {tasklist_title}")


def add_subparser_add_task(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'add' subcommand to create a new task."""
    add_parser = subparsers.add_parser(
        "add",
        help="Add a new task",
        description="Create a new task in the specified task list.",
    )
    add_parser.add_argument(
        "title",
        type=str,
        help="Title of the task to create",
    )
    add_parser.add_argument(
        "-l",
        "--tasklist-title",
        type=str,
        default=None,
        help="Title of the task list to add the task to",
    )
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
        help="Due date for the task (natural language e.g. 'tomorrow', 'next friday', '2026-05-01')",
    )
    add_parser.set_defaults(func=partial(cmd_add_task, client=client, cfg=cfg))
