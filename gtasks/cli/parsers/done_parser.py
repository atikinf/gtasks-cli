"""Done subcommand - mark a task as complete."""

import argparse
import sys
from functools import partial

from gtasks.cli.cli_utils import prompt_choose_tasklist_id, resolve_tasks_from_inputs
from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config, ConfigKey


def cmd_done(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'done' command to mark one or more tasks complete."""
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

    completed = client.complete_tasks(tasklist_id, tasks)
    if len(completed) == 1:
        print(f"Completed: {completed[0].get('title', '?')}")
    else:
        print("Completed:")
        for t in completed:
            print(f"    {t.get('title', '?')}")


def add_subparser_done(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'done' subcommand to mark one or more tasks as complete."""
    done_parser = subparsers.add_parser(
        "done",
        help="Mark one or more tasks as complete",
        description="Mark tasks complete by title or display index (e.g. 'gtasks done 1 3' or 'gtasks done \"Buy milk\"').",  # noqa: E501
    )
    done_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles or 1-based display indices of tasks to mark complete",
    )
    done_parser.add_argument(
        "-l",
        "--tasklist-title",
        type=str,
        default=None,
        help="Title of the task list (uses default if not specified)",
    )
    done_parser.set_defaults(func=partial(cmd_done, client=client, cfg=cfg))
