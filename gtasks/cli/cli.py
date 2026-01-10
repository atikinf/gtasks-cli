"""CLI parser building for the Google Tasks CLI."""

import argparse

from gtasks.cli.parsers.add_parser import add_add_task_subparser
from gtasks.cli.parsers.lists_parser import add_lists_subparser
from gtasks.cli.parsers.set_default_parser import add_set_default_subparser
from gtasks.cli.parsers.tasks_parser import add_tasks_subparser
from gtasks.utils.config import Config


def build_parser(cfg: Config) -> argparse.ArgumentParser:
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

    add_tasks_subparser(subparsers)
    add_lists_subparser(subparsers)
    add_add_task_subparser(subparsers)
    add_set_default_subparser(subparsers, cfg)

    return parser
