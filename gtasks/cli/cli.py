"""CLI parser building for the Google Tasks CLI."""

import argparse

from gtasks.cli.parsers.add_parser import add_subparser_add_task
from gtasks.cli.parsers.auth_parser import add_subparser_auth
from gtasks.cli.parsers.config_parser import add_subparser_config
from gtasks.cli.parsers.delete_parser import add_subparser_delete
from gtasks.cli.parsers.done_parser import add_subparser_done
from gtasks.cli.parsers.lists_parser import add_subparser_lists
from gtasks.cli.parsers.tasks_parser import add_subparser_tasks, cmd_list_tasks
from gtasks.cli.parsers.use_parser import add_subparser_use
from gtasks.cli.tasklist_resolution import add_tasklist_option

_DEFAULT_LIMIT = 10


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the CLI.

    Structure only - no client or config is bound here. Every subcommand's
    `func` is an unbound handler; main() resolves the client/cfg it needs
    only after parse_args() succeeds, so `--help` and invalid invocations
    never trigger credential loading or an OAuth flow.
    """
    parser = argparse.ArgumentParser(
        prog="gtasks",
        description="Command-line interface for Google Tasks",
    )

    # -l works before any subcommand too: `gtasks -l Work` or `gtasks -l Work done 1`.
    add_tasklist_option(parser, top_level=True)

    # Default: bare `gtasks` shows the first 10 tasks from the active list.
    parser.set_defaults(
        func=cmd_list_tasks,
        limit=_DEFAULT_LIMIT,
        show_ids=False,
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=False,
    )

    add_subparser_tasks(subparsers)
    add_subparser_lists(subparsers)
    add_subparser_add_task(subparsers)
    add_subparser_use(subparsers)
    add_subparser_done(subparsers)
    add_subparser_delete(subparsers)
    add_subparser_config(subparsers)
    add_subparser_auth(subparsers)

    return parser
