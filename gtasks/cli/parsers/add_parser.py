"""Add subcommand - add a new task."""

import argparse
import sys
from functools import partial

from gtasks.cli.cli_utils import prompt_choose_tasklist_id
from gtasks.client.api_client import ApiClient
from gtasks.client.client_utils import resolve_tasklist_id
from gtasks.utils.config import Config


def cmd_add_task(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'add' command to create a new task."""
    tasklist_title: None | str = args.tasklist_title or cfg.get_tasklist_title()
    if tasklist_title is None:
        print(
            "Error: You must specify a --tasklist-title (-t) or set a default tasklist"
        )
        sys.exit(1)

    tasklists: list = client.get_tasklists()
    ids: list[str] = resolve_tasklist_id(args.tasklist_title, tasklists)

    tasklist_id = prompt_choose_tasklist_id(ids, tasklists, args.tasklist_title)

    if tasklist_id is not None:
        task = client.add_task(
            tasklist_id=tasklist_id,
            title=args.title,
            notes=args.notes,
            due=args.due,
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
    tasklist_group = add_parser.add_mutually_exclusive_group()
    tasklist_group.add_argument(
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
        help="Due date for the task (RFC 3339 format)",
    )
    add_parser.set_defaults(func=partial(cmd_add_task, client=client, cfg=cfg))
