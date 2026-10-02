"""Config subcommand - view and set configuration defaults."""

import argparse
from collections.abc import Callable
from typing import TYPE_CHECKING

from rich.text import Text

from gtasks.cli import ui
from gtasks.cli.errors import CliError
from gtasks.utils.config import LEGACY_DEFAULT_TASKLIST_KEY, Config, ConfigKey

if TYPE_CHECKING:
    from gtasks.client.protocol import TasksClient

_DESCRIPTIONS: dict[ConfigKey, str] = {
    ConfigKey.ACTIVE_TASKLIST_ID: "ID of the list commands act on when no -l is given",
    ConfigKey.ACTIVE_TASKLIST_TITLE: "Display name of the active list",
}

# Keys owned by another command; setting them by hand would let ID and title disagree.
_MANAGED_BY: dict[ConfigKey, str] = {
    ConfigKey.ACTIVE_TASKLIST_ID: "gtasks use",
    ConfigKey.ACTIVE_TASKLIST_TITLE: "gtasks use",
}

_VALID_KEYS = ", ".join(k.value for k in ConfigKey)


def _setting_line(key: ConfigKey, value: str | None) -> Text:
    shown = (value, "") if value is not None else ("(not set)", "muted")
    return Text.assemble((key.value, "heading"), " = ", shown)


def cmd_config(
    args: argparse.Namespace, get_client: "Callable[[], TasksClient]", cfg: Config
) -> None:
    """Handle the 'config' command to view or set configuration defaults.

    Never calls `get_client` - 'config' doesn't touch the API, so it works
    before `gtasks auth` has run. The param matches the uniform dispatch signature.
    """
    if args.key is None:
        for key in ConfigKey:
            ui.info(_setting_line(key, cfg.get(key)))
            ui.info(Text(f"    {_DESCRIPTIONS[key]}", style="muted"))
        return

    if args.key == LEGACY_DEFAULT_TASKLIST_KEY:
        raise CliError(
            f"'{args.key}' was replaced by the active list.", hint="Run `gtasks use <list>`."
        )
    try:
        config_key = ConfigKey(args.key)
    except ValueError:
        raise CliError(f"Unknown key '{args.key}'.", hint=f"Valid keys: {_VALID_KEYS}") from None

    if args.value is None:
        ui.info(_setting_line(config_key, cfg.get(config_key)))
        return

    if config_key in _MANAGED_BY:
        command = _MANAGED_BY[config_key]
        raise CliError(f"'{config_key.value}' is set by `{command}`.", hint=f"Run `{command}`.")
    cfg.set(config_key, args.value)
    ui.success(_setting_line(config_key, args.value))


def add_subparser_config(subparsers) -> None:
    """Add the 'config' subcommand to view and set configuration defaults."""
    config_parser = subparsers.add_parser(
        "config",
        help="View or set config defaults",
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
