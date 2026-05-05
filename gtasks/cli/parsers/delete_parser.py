"""Delete subcommand - delete tasks by name or display index."""

import argparse
import sys
from functools import partial

from gtasks.cli.cli_utils import prompt_choose_tasklist_id, resolve_tasks_from_inputs
from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config, ConfigKey


def cmd_delete(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'delete' command to remove one or more tasks."""
    tasklist_title: None | str = args.tasklist_title or cfg.get(ConfigKey.DEFAULT_TASKLIST_TITLE)
    if tasklist_title is None:
        print("Error: You must specify a --tasklist-title (-l) or set a default tasklist")
        sys.exit(1)

    matches = client.resolve_tasklist_from_title(tasklist_title)
    tasklist_id = prompt_choose_tasklist_id(matches, tasklist_title)
    if tasklist_id is None:
        print(f"Couldn't find a tasklist named '{tasklist_title}'")
        return

    tasks = resolve_tasks_from_inputs(args.tasks, client, tasklist_id)
    if not tasks:
        return

    deleted = client.delete_tasks(tasklist_id, tasks)
    if len(deleted) == 1:
        print(f"Deleted: {deleted[0].get('title', '?')}")
    else:
        print("Deleted:")
        for t in deleted:
            print(f"    {t.get('title', '?')}")


def add_subparser_delete(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'delete' subcommand to remove one or more tasks."""
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete one or more tasks",
        description="Delete tasks by title or display index (e.g. 'gtasks delete 1 3' or 'gtasks delete \"Buy milk\"').",  # noqa: E501
    )
    delete_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles or 1-based display indices of tasks to delete",
    )
    delete_parser.add_argument(
        "-l",
        "--tasklist-title",
        type=str,
        default=None,
        help="Title of the task list (uses default if not specified)",
    )
    delete_parser.set_defaults(func=partial(cmd_delete, client=client, cfg=cfg))
