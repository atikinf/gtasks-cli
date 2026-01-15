"""Tasks subcommand - list tasks from a task list."""

import argparse
import sys
from functools import partial

from gtasks.cli.cli_utils import print_tasks, prompt_choose_tasklist_id
from gtasks.client.api_client import ApiClient
from gtasks.client.client_utils import resolve_tasklist_id
from gtasks.utils.config import Config


def cmd_list_tasks(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'list' command to display tasks."""
    tasklist_title: None | str = args.tasklist_title or cfg.get_tasklist_title()
    if tasklist_title is None:
        print(
            "Error: You must specify a --tasklist-title (-t) or set a default tasklist"
        )
        sys.exit(1)
        return
    tasks = []

    tasklists: list = client.get_tasklists()
    ids: list[str] = resolve_tasklist_id(tasklist_title, tasklists)

    id_ = prompt_choose_tasklist_id(ids, tasklists, tasklist_title)
    if id_ is not None:
        tasks = client.get_tasks(id_, args.limit)
    else:
        print(f"Couldn't find a tasklist named {tasklist_title}")

    print(f"==[{tasklist_title}]==")
    print_tasks(tasks, args)


def add_subparser_tasks(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'tasks' subcommand to list tasks."""
    tasks_parser = subparsers.add_parser(
        "tasks",
        help="List tasks from a task list",
        description="Display tasks from the specified or default task list.",
    )
    tasks_parser.add_argument(
        "-l",
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
    tasks_parser.set_defaults(func=partial(cmd_list_tasks, client=client, cfg=cfg))
