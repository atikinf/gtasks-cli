#!/usr/bin/env python3
"""Command-line interface for Google Tasks."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from gtasks.api_client import ApiClient
from gtasks.service import Service
from gtasks.silly_utils import build_tasks_service
from gtasks.utils.bidict_cache import BidictCache
from gtasks.utils.defaults import CACHE_PATH


def tasks_resource():
    return build_tasks_service()


def service() -> Service:
    api_client = ApiClient(tasks_resource())
    cache: BidictCache[str, str] = BidictCache(CACHE_PATH)
    return Service(api_client, cache)


def cmd_list_tasks(args: argparse.Namespace) -> None:
    """Handle the 'list' command to display tasks."""
    helper = service()
    helper.list_tasks(
        tasklist_id=args.tasklist_id,
        tasklist_title=args.tasklist_title,
        n=args.limit,
    )


def cmd_list_tasklists(args: argparse.Namespace) -> None:
    """Handle the 'lists' command to display task lists."""
    helper = service()
    helper.list_tasklists(n=args.limit, show_ids=args.show_ids)


def cmd_set_default(args: argparse.Namespace) -> None:
    """Handle the 'set-default' command to set a default task list."""
    helper = service()
    # helper.set_default_tasklist()


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

    # 'tasks' subcommand - list tasks
    list_parser = subparsers.add_parser(
        "tasks",
        help="List tasks from a task list",
        description="Display tasks from the specified or default task list.",
    )
    tasklist_group = list_parser.add_mutually_exclusive_group()
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
    list_parser.add_argument(
        "-n",
        "--limit",
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
        "-n",
        "--limit",
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

    # def _prompt_index_choice(
    #     self,
    #     items: list,
    #     prompt_prefix: str,
    #     current_hint: str | None = None,
    # ) -> int | None:
    #     """Prompt user to select an item from a numbered list.

    #     Args:
    #         items: List of items to choose from.
    #         prompt_prefix: e.g., "Select a default task list".
    #         current_hint: Optional hint to display about the current selection.

    #     Returns:
    #         0-based index of the selected item, or None if the user cancelled.
    #     """
    #     while True:
    #         hint_suffix = f" (current: {current_hint})" if current_hint else ""
    #         choice_str = input(
    #             f"{prompt_prefix} [1-{len(items)}]{hint_suffix} (or 'q' to cancel): "
    #         ).strip()

    #         if choice_str.lower() in {"q", "quit"}:
    #             return None

    #         if not choice_str.isdigit():
    #             print("Please enter a number or 'q' to cancel.")
    #             continue

    #         choice = int(choice_str)
    #         if 1 <= choice <= len(items):
    #             return choice - 1  # Convert to 0-based index

    #         print(f"Please choose a number between 1 and {len(items)}.")
