"""Delete subcommand - delete a task by name."""

import argparse
import sys
from functools import partial

from gtasks.cli.cli_utils import prompt_choose_task_id, prompt_choose_tasklist_id
from gtasks.client.api_client import ApiClient
from gtasks.client.client_utils import resolve_task_id, resolve_tasklist_id
from gtasks.utils.config import Config


def cmd_delete(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'delete' command to remove a task."""
    tasklist_title: None | str = args.tasklist_title or cfg.get_tasklist_title()
    if tasklist_title is None:
        print("Error: You must specify a --tasklist-title (-l) or set a default tasklist")
        sys.exit(1)

    tasklists = client.get_tasklists()
    tasklist_ids = resolve_tasklist_id(tasklist_title, tasklists)
    tasklist_id = prompt_choose_tasklist_id(tasklist_ids, tasklists, tasklist_title)
    if tasklist_id is None:
        print(f"Couldn't find a tasklist named '{tasklist_title}'")
        return

    tasks = client.get_tasks(tasklist_id)
    task_ids = resolve_task_id(args.title, tasks)
    task_id = prompt_choose_task_id(task_ids, tasks, args.title)
    if task_id is None:
        return

    client.delete_task(tasklist_id, task_id)
    print(f"Deleted: {args.title}")


def add_subparser_delete(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'delete' subcommand to remove a task."""
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete a task",
        description="Delete a task by title.",
    )
    delete_parser.add_argument(
        "title",
        type=str,
        help="Title of the task to delete",
    )
    delete_parser.add_argument(
        "-l",
        "--tasklist-title",
        type=str,
        default=None,
        help="Title of the task list (uses default if not specified)",
    )
    delete_parser.set_defaults(func=partial(cmd_delete, client=client, cfg=cfg))
