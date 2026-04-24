"""Done subcommand - mark a task as complete."""

import argparse
import sys
from functools import partial

from gtasks.cli.cli_utils import prompt_choose_task_id, prompt_choose_tasklist_id
from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config, ConfigKey


def cmd_done(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'done' command to mark a task complete."""
    tasklist_title: None | str = args.tasklist_title or cfg.get(ConfigKey.DEFAULT_TASKLIST_TITLE)
    if tasklist_title is None:
        print("Error: You must specify a --tasklist-title (-l) or set a default tasklist")
        sys.exit(1)

    matches = client.resolve_tasklist_from_title(tasklist_title)
    tasklist_id = prompt_choose_tasklist_id(matches, tasklist_title)
    if tasklist_id is None:
        print(f"Couldn't find a tasklist named '{tasklist_title}'")
        return

    matches = client.resolve_task_from_title(args.title, tasklist_id)
    task_ids = [t["id"] for t in matches if t.get("id")]
    task_id = prompt_choose_task_id(task_ids, matches, args.title)
    if task_id is None:
        return

    client.complete_task(tasklist_id, task_id)
    print(f"Completed: {args.title}")


def add_subparser_done(subparsers, client: ApiClient, cfg: Config) -> None:
    """Add the 'done' subcommand to mark a task as complete."""
    done_parser = subparsers.add_parser(
        "done",
        help="Mark a task as complete",
        description="Mark a task as complete by title.",
    )
    done_parser.add_argument(
        "title",
        type=str,
        help="Title of the task to mark complete",
    )
    done_parser.add_argument(
        "-l",
        "--tasklist-title",
        type=str,
        default=None,
        help="Title of the task list (uses default if not specified)",
    )
    done_parser.set_defaults(func=partial(cmd_done, client=client, cfg=cfg))
