"""Config subcommand - view and set configuration defaults."""

import argparse
import sys

from gtasks.client.api_client import ApiClient
from gtasks.utils.config import Config, ConfigKey

_DESCRIPTIONS: dict[ConfigKey, str] = {
    ConfigKey.DEFAULT_TASKLIST_TITLE: "The default task list used when no -l flag is given",
}

_VALID_KEYS = ", ".join(k.value for k in ConfigKey)


def cmd_config(args: argparse.Namespace, client: ApiClient, cfg: Config) -> None:
    """Handle the 'config' command to view or set configuration defaults.

    Takes an unused `client` to match the uniform dispatch signature main()
    calls args.func with; 'config' never touches the API.
    """
    if args.key is None:
        for key in ConfigKey:
            value = cfg.get(key)
            display = value if value is not None else "(not set)"
            print(f"{key.value} = {display}")
            print(f"    {_DESCRIPTIONS[key]}")
        return

    try:
        config_key = ConfigKey(args.key)
    except ValueError:
        print(f"Unknown key: {args.key!r}. Valid keys: {_VALID_KEYS}")
        sys.exit(1)

    if args.value is None:
        value = cfg.get(config_key)
        display = value if value is not None else "(not set)"
        print(f"{config_key.value} = {display}")
    else:
        cfg.set(config_key, args.value)
        print(f"{config_key.value} = {args.value}")


def add_subparser_config(subparsers) -> None:
    """Add the 'config' subcommand to view and set configuration defaults."""
    config_parser = subparsers.add_parser(
        "config",
        help="View or set configuration defaults",
        description="View all settings or get/set a specific configuration value.",
    )
    config_parser.add_argument(
        "key",
        type=str,
        nargs="?",
        default=None,
        help=f"Config key to read or set (one of: {_VALID_KEYS})",
    )
    config_parser.add_argument(
        "value",
        type=str,
        nargs="?",
        default=None,
        help="Value to assign to the key",
    )
    config_parser.set_defaults(func=cmd_config)
