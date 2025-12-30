#!/usr/bin/env python3
"""Command-line interface for Google Tasks."""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from gtasks.tasks_helper import TasksHelper


def cmd_list_tasks(args: argparse.Namespace) -> None:
    """Handle the 'list' command to display tasks."""
    helper = TasksHelper()
    helper.list_tasks(
        tasklist_id=args.tasklist_id,
        tasklist_title=args.tasklist_title,
        n=args.limit,
    )


def cmd_list_tasklists(args: argparse.Namespace) -> None:
    """Handle the 'lists' command to display task lists."""
    helper = TasksHelper()
    helper.list_tasklists(n=args.limit, show_ids=args.show_ids)


def cmd_set_default(args: argparse.Namespace) -> None:
    """Handle the 'set-default' command to set a default task list."""
    helper = TasksHelper()
    helper.set_default_tasklist()


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="gtasks",
        description="Command-line interface for Google Tasks",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
    )

    # 'list' subcommand - list tasks
    list_parser = subparsers.add_parser(
        "list",
        help="List tasks from a task list",
        description="Display tasks from the specified or default task list.",
    )
    tasklist_group = list_parser.add_mutually_exclusive_group()
    tasklist_group.add_argument(
        "-t", "--tasklist-id",
        type=str,
        default=None,
        help="ID of the task list to show tasks from (uses default if not specified)",
    )
    tasklist_group.add_argument(
        "-T", "--tasklist-title",
        type=str,
        default=None,
        help="Title of the task list to show tasks from (uses default if not specified)",
    )
    list_parser.add_argument(
        "-n", "--limit",
        type=int,
        default=None,
        help="Maximum number of tasks to display",
    )
    list_parser.set_defaults(func=cmd_list_tasks)

    # 'lists' subcommand - list task lists
    lists_parser = subparsers.add_parser(
        "lists",
        help="List all task lists",
        description="Display all available task lists for this account.",
    )
    lists_parser.add_argument(
        "-n", "--limit",
        type=int,
        default=None,
        help="Maximum number of task lists to display",
    )
    lists_parser.add_argument(
        "--show-ids",
        action="store_true",
        default=False,
        help="Include task list IDs in the output",
    )
    lists_parser.set_defaults(func=cmd_list_tasklists)

    # 'set-default' subcommand - set default task list
    set_default_parser = subparsers.add_parser(
        "set-default",
        help="Set the default task list",
        description="Interactively select and save a default task list.",
    )
    set_default_parser.set_defaults(func=cmd_set_default)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """Main entry point for the CLI.

    Args:
        argv: Command-line arguments. Uses sys.argv if None.

    Returns:
        Exit code (0 for success).
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        args.func(args)
        return 0
    except KeyboardInterrupt:
        print("\nOperation cancelled.")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
