"""Lists subcommand - list all task lists."""

import argparse

from gtasks.client.client_factory import build_cached_client


def cmd_list_tasklists(args: argparse.Namespace) -> None:
    """Handle the 'lists' command to display task lists."""
    client = build_cached_client()
    tasklists = client.get_tasklists(args.limit)
    for tasklist in tasklists:
        title = tasklist.get("title", "<no title>")
        if args.show_ids:
            tasklist_id = tasklist.get("id", "<no id>")
            print(f"- [{tasklist_id}] {title}")
        else:
            print(f"- {title}")


def add_lists_subparser(subparsers) -> None:
    """Add the 'lists' subcommand to list task lists."""
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
