"""Refresh subcommand - force-clear and repopulate the tasklist cache."""

import argparse
from functools import partial

from gtasks.client.api_client import ApiClient
from gtasks.client.cached_api_client import CachedApiClient


def cmd_refresh(args: argparse.Namespace, client: ApiClient) -> None:
    """Handle the 'refresh' command to repopulate the cache from the API."""
    if not isinstance(client, CachedApiClient):
        print("Caching is disabled; nothing to refresh.")
        return
    tasklists = client.refresh_cache()
    print(f"Cache refreshed: {len(tasklists)} task list(s) loaded.")


def add_subparser_refresh(subparsers, client: ApiClient) -> None:
    """Add the 'refresh' subcommand to force-clear and repopulate the cache."""
    refresh_parser = subparsers.add_parser(
        "refresh",
        help="Refresh the task list cache",
        description="Force-clears the local cache and repopulates it from the Google Tasks API.",
    )
    refresh_parser.set_defaults(func=partial(cmd_refresh, client=client))
