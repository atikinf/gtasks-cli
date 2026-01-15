"""CLI parser building for the Google Tasks CLI."""

import argparse

from gtasks.cli.parsers.add_parser import add_subparser_add_task
from gtasks.cli.parsers.lists_parser import add_subparser_lists
from gtasks.cli.parsers.set_default_parser import add_subparser_set_default
from gtasks.cli.parsers.tasks_parser import add_subparser_tasks
from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config


def build_parser(client: ApiClient, cfg: Config) -> argparse.ArgumentParser:
    """Build and return the argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        prog="gtasks",
        description="Command-line interface for Google Tasks",
    )

    subparsers = parser.add_subparsers(
        title="commands",
        dest="command",
        required=True,
    )

    add_subparser_tasks(subparsers, client, cfg)
    add_subparser_lists(subparsers, client)
    add_subparser_add_task(subparsers, client, cfg)
    add_subparser_set_default(subparsers, client, cfg)

    return parser


"""
    Goal Example usage:

> gtasks <anything>
Do you have an API credentials file in `~/.config/gtasks`? See <insert_doc_link>
> gtasks <anything>
This is your first time using `gtasks`. Run `gtasks auth` to open a browser tab to authenticate your Google account.
> gtasks config 
<print flags, etc.>
> gtasks tasks 
==[To Do]==
1.  Hello 
    ∟ Say hello      
2.  Test 
3.  Yes
> gtasks add task "Yes" "Descr" [parsed as Title: "Yes", Description: "Descr", optional flags for other params]
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
