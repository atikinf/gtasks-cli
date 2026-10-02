"""Decide which task list a command acts on.

Every list-scoped command goes through `resolve_target_tasklist`, so precedence is the same
everywhere:

    -l/--list flag  >  $GTASKS_LIST  >  active list (`gtasks use`)  >  account default list

The active list is stored by ID (with its title cached for display), so it survives renames
and duplicate titles without a lookup on every command.
"""

import argparse
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import prompt_index_choice
from gtasks.cli.errors import Cancelled, CliError
from gtasks.utils.config import LEGACY_DEFAULT_TASKLIST_KEY, Config, ConfigKey

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import TaskList

    from gtasks.client.protocol import TasksClient

ENV_VAR = "GTASKS_LIST"
# Tasks API alias for the account's primary list ("My Tasks").
DEFAULT_TASKLIST_ID = "@default"


@dataclass(frozen=True)
class TargetList:
    id: str
    title: str


def choose_tasklist(
    matches: "list[TaskList]",
    title: str,
    input_fn: Callable[[str], str] | None = None,
) -> "TaskList":
    """Pick one list from title matches, prompting only when the title is ambiguous."""
    if not matches:
        raise CliError(f"No task list named '{title}'.", hint="Run `gtasks lists` to see them.")
    if len(matches) == 1:
        return matches[0]

    ui.info(f"Several lists are named '{title}':")
    ui.render_tasklists(matches, show_ids=True)
    ix = prompt_index_choice(len(matches), "Which one?", input_fn or input)
    if ix is None:
        raise Cancelled()
    return matches[ix]


def set_active_tasklist(cfg: Config, tasklist: "TaskList") -> None:
    cfg.set(ConfigKey.ACTIVE_TASKLIST_ID, tasklist["id"])
    cfg.set(ConfigKey.ACTIVE_TASKLIST_TITLE, tasklist.get("title", ""))


def add_tasklist_option(parser: argparse.ArgumentParser, *, top_level: bool = False) -> None:
    """Register -l/--list, so it reads the same on every list-scoped command.

    It's on the top-level parser too (`gtasks -l Work`). Subparser copies default to
    SUPPRESS: otherwise their None would overwrite a value given before the subcommand,
    as in `gtasks -l Work done 1`.
    """
    parser.add_argument(
        "-l",
        "--list",
        dest="tasklist_title",
        metavar="LIST",
        default=None if top_level else argparse.SUPPRESS,
        help=f"task list to act on (default: ${ENV_VAR}, else the active list)",
    )


def resolve_target_tasklist(
    args: argparse.Namespace,
    client: "TasksClient",
    cfg: Config,
    environ: Mapping[str, str] = os.environ,
) -> TargetList:
    """Return the list a command should act on, per the precedence in the module docstring."""
    explicit = getattr(args, "tasklist_title", None) or environ.get(ENV_VAR)
    if explicit:
        tasklist = choose_tasklist(client.resolve_tasklist_from_title(explicit), explicit)
        return TargetList(tasklist["id"], tasklist.get("title", explicit))

    active_id = cfg.get(ConfigKey.ACTIVE_TASKLIST_ID)
    if active_id:
        return TargetList(active_id, cfg.get(ConfigKey.ACTIVE_TASKLIST_TITLE) or "Active list")

    migrated = _migrate_legacy_active_tasklist(client, cfg)
    if migrated is not None:
        return migrated

    default = client.get_tasklist(DEFAULT_TASKLIST_ID)
    return TargetList(default["id"], default.get("title", "My Tasks"))


def _migrate_legacy_active_tasklist(client: "TasksClient", cfg: Config) -> TargetList | None:
    """Convert a pre-ID `default_tasklist = <title>` entry into the ID-based keys, once."""
    legacy_title = cfg.get_raw(LEGACY_DEFAULT_TASKLIST_KEY)
    if not legacy_title:
        return None

    matches = client.resolve_tasklist_from_title(legacy_title)
    if not matches:
        cfg.pop_raw(LEGACY_DEFAULT_TASKLIST_KEY)
        ui.warn(
            f"Your saved list '{legacy_title}' no longer exists; using your default list.",
            hint="Run `gtasks use` to pick an active list.",
        )
        return None

    # Only drop the legacy key once a list is chosen, so cancelling the prompt retries later.
    tasklist = choose_tasklist(matches, legacy_title)
    set_active_tasklist(cfg, tasklist)
    cfg.pop_raw(LEGACY_DEFAULT_TASKLIST_KEY)
    return TargetList(tasklist["id"], tasklist.get("title", legacy_title))
