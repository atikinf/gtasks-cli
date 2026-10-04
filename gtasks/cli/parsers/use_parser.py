"""Use subcommand - set the active task list."""

import argparse
from typing import TYPE_CHECKING

from rich.text import Text

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_refresh_option, prompt_index_choice
from gtasks.cli.errors import Cancelled, CliError
from gtasks.cli.title_id_resolution import find_tasklist, set_active_tasklist
from gtasks.utils.config import Config, ConfigKey

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider


def cmd_use(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'use' command to set the active task list."""
    client = get_client()
    if args.name is None:
        tasklists = client.get_tasklists()
        if not tasklists:
            raise CliError("You have no task lists.")
        ui.render_tasklists(tasklists, active_id=cfg.get(ConfigKey.ACTIVE_TASKLIST_ID))
        choice = prompt_index_choice(len(tasklists), "Make which list active?", input)
        if choice is None:
            raise Cancelled()
        tasklist = tasklists[choice]
    else:
        tasklist = find_tasklist(client, args.name)

    set_active_tasklist(cfg, tasklist)
    ui.success(Text.assemble("Active list: ", (tasklist.get("title", ""), "heading")))


def add_subparser_use(subparsers) -> None:
    """Add the 'use' subcommand to set the active task list."""
    use_parser = subparsers.add_parser(
        "use",
        help="Set the active task list",
        description=(
            "Set the task list that commands act on when no -l/--list is given. "
            "Pick interactively if no name is given."
        ),
    )
    use_parser.add_argument(
        "name",
        type=str,
        nargs="?",
        default=None,
        help="Name of the task list to make active",
    )
    add_refresh_option(use_parser)
    use_parser.set_defaults(func=cmd_use)
