"""Add subcommand - add a new task."""

import argparse
import sys

from gtasks.client.client_factory import build_cached_client


def cmd_add_task(args: argparse.Namespace) -> None:
    """Handle the 'add' command to create a new task."""
    has_id = args.tasklist_id is not None
    has_title = args.tasklist_title is not None
    if has_id == has_title:
        print(
            "Error: You must specify exactly one of --tasklist-id (-t) or "
            "--tasklist-title (-T)"
        )
        sys.exit(1)

    client = build_cached_client()
    tasklist_id = args.tasklist_id or client._resolve_tasklist_id(args.tasklist_title)
    task = client.add_task(
        tasklist_id=tasklist_id,
        title=args.title,
        notes=args.notes,
        due=args.due,
    )
    print(f"Created task: {task.get('title', '<no title>')}")


def add_add_task_subparser(subparsers) -> None:
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
        "-t",
        "--tasklist-id",
        type=str,
        default=None,
        help="ID of the task list to add the task to",
    )
    tasklist_group.add_argument(
        "-T",
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
    add_parser.set_defaults(func=cmd_add_task)
