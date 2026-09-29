"""Lists subcommand - list all task lists."""

import argparse

from gtasks.cli.cli_utils import print_tasklists
from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config


def cmd_list_tasklists(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'lists' command to display task lists.

    Takes an unused `cfg` to match the uniform dispatch signature main()
    calls args.func with; 'lists' has no default-tasklist concept.
    """
    tasklists = client.get_tasklists(args.limit)
    print_tasklists(tasklists, args)


def add_subparser_lists(subparsers) -> None:
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
