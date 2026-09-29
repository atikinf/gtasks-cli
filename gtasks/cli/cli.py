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

    # Default: bare `gtasks` shows the first 10 tasks from the default list.
    parser.set_defaults(
        func=cmd_list_tasks,
        tasklist_title=None,
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


"""
    Goal Example usage:

> gtasks <anything>
Do you have an API credentials file in `~/.config/gtasks`? See <insert_doc_link>
> gtasks <anything>
This is your first time using `gtasks`. Run `gtasks auth` to open a browser tab
to authenticate your Google account.
> gtasks config
<print flags, etc.>
> gtasks tasks
==[To Do]==
1.  Hello
    ∟ Say hello
2.  Test
3.  Yes
> gtasks add task "Yes" "Descr" [parsed as Title: "Yes", Description: "Descr", optional flags]
Added task:
    Yes
    ∟ Descr
> gtasks add list "List Name"
Added list:
    [List Name]
> gtasks delete task "Hello"
Deleted task:
    Hello
    ∟ Say hello

TODO

> gtasks complete task "Test"
< patches task to update status>
"""
