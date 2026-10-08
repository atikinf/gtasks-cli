"""Done subcommand - mark a task as complete."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli.cli_utils import add_refresh_option
from gtasks.cli.completion import attach, complete_tasks
from gtasks.cli.task_actions import act_on_tasks
from gtasks.cli.title_id_resolution import add_tasklist_option
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider


def cmd_done(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'done' command to mark one or more tasks complete."""
    act_on_tasks(
        args,
        get_client,
        cfg,
        verb="Completed",
        act=lambda client, tasklist_id, task_ids: client.complete_tasks(tasklist_id, task_ids),
    )


def add_subparser_done(subparsers) -> None:
    """Add the 'done' subcommand to mark one or more tasks as complete."""
    done_parser = subparsers.add_parser(
        "done",
        help="Mark one or more tasks as complete",
        description="Mark tasks complete by title or the number shown by `gtasks` (e.g. 'gtasks done 1 3' or 'gtasks done \"Buy milk\"').",  # noqa: E501
    )
    tasks_arg = done_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles (or a unique part of one), or numbers as shown by `gtasks`, to mark complete",
    )
    attach(tasks_arg, complete_tasks)
    add_tasklist_option(done_parser)
    add_refresh_option(done_parser)
    done_parser.set_defaults(func=cmd_done)
