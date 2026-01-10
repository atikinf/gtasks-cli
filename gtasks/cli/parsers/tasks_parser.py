"""Tasks subcommand - list tasks from a task list."""

import argparse
import sys

from gtasks.client.client_factory import build_cached_client


def cmd_list_tasks(args: argparse.Namespace) -> None:
    """Handle the 'list' command to display tasks."""
    has_id = args.tasklist_id is not None
    has_title = args.tasklist_title is not None
    if has_id == has_title:
        print(
            "Error: You must specify exactly one of --tasklist-id (-t) or "
            "--tasklist-title (-T)"
        )
        sys.exit(1)

    client = build_cached_client()

    if has_id:
        tasks = client.get_tasks(args.tasklist_id, args.limit)
    else:
        tasks = client.get_tasks_by_title(args.tasklist_title, args.limit)
    for task in tasks:
        title: str = task.get("title", "<no title>")
        notes = task.get("notes")
        due = task.get("due")
        if args.show_ids:
            task_id = task.get("id", "<no id>")
            print(f"- [{task_id}] {title}", end="")
        else:
            print(f"- {title}", end="")
        if due:
            print(f" (Due: {due})", end="")
        print()
        if notes:
            print(f"    Notes: {notes}")


def add_tasks_subparser(subparsers) -> None:
    """Add the 'tasks' subcommand to list tasks."""
    tasks_parser = subparsers.add_parser(
        "tasks",
        help="List tasks from a task list",
        description="Display tasks from the specified or default task list.",
    )
    tasklist_group = tasks_parser.add_mutually_exclusive_group()
    tasklist_group.add_argument(
        "-t",
        "--tasklist-id",
        type=str,
        default=None,
        help="ID of the task list to show tasks from (uses default if not specified)",
    )
    tasklist_group.add_argument(
        "-T",
        "--tasklist-title",
        type=str,
        default=None,
        help="Title of the task list to show tasks from (uses default if not specified)",
    )
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
