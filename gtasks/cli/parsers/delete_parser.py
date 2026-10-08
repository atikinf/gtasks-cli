"""Delete subcommand - delete tasks by name or display index."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option, prompt_yes_no
from gtasks.cli.completion import attach, complete_tasks
from gtasks.cli.errors import Cancelled
from gtasks.cli.task_actions import act_on_tasks
from gtasks.cli.title_id_resolution import ResolvedTasks, TargetList, add_tasklist_option
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider


def cmd_delete(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'delete' command to remove one or more tasks."""

    def confirm(resolved: ResolvedTasks, target: TargetList) -> None:
        # A fragment picked these titles, not the user: confirm before an irreversible delete.
        if resolved.partial and not args.yes:
            _confirm_delete(resolved.tasks, target.title)

    act_on_tasks(
        args,
        get_client,
        cfg,
        verb="Deleted",
        act=lambda client, tasklist_id, task_ids: client.delete_tasks(tasklist_id, task_ids),
        confirm=confirm,
    )


def _confirm_delete(tasks: list, tasklist_title: str) -> None:
    titles = [ui.display_title(t) for t in tasks]
    what = f"'{titles[0]}'" if len(titles) == 1 else f"{len(titles)} tasks ({', '.join(titles)})"
    if not prompt_yes_no(f"Delete {what} from {tasklist_title}?"):
        raise Cancelled()


def add_subparser_delete(subparsers) -> None:
    """Add the 'delete' subcommand to remove one or more tasks."""
    delete_parser = subparsers.add_parser(
        "delete",
        help="Delete one or more tasks",
        description="Delete tasks by title or the number shown by `gtasks` (e.g. 'gtasks delete 1 3' or 'gtasks delete \"Buy milk\"').",  # noqa: E501
    )
    tasks_arg = delete_parser.add_argument(
        "tasks",
        type=str,
        nargs="+",
        help="Titles (or a unique part of one), or numbers as shown by `gtasks`, to delete",
    )
    attach(tasks_arg, complete_tasks)
    delete_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Don't ask before deleting tasks matched by part of their title",
    )
    add_tasklist_option(delete_parser)
    add_refresh_option(delete_parser)
    delete_parser.set_defaults(func=cmd_delete)
