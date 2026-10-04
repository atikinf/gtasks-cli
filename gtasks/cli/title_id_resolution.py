"""Turn what the user typed - list titles, task titles, display numbers - into API objects.

Which list a command acts on: every list-scoped command goes through
`resolve_target_tasklist`, so precedence is the same everywhere:

    -l/--list flag  >  $GTASKS_LIST  >  active list (`gtasks use`)  >  account default list

The active list is stored by ID (with its title cached for display), so it survives renames
and duplicate titles without a lookup on every command.

Which tasks a command acts on: `resolve_tasks_from_inputs` takes titles or 1-based display
numbers. Titles of both kinds match case-insensitively and prompt only when they collide.
"""

import argparse
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gtasks.cli import ui
from gtasks.cli.cli_utils import add_shared_option, prompt_index_choice
from gtasks.cli.errors import Cancelled, CliError
from gtasks.client.protocol import DEFAULT_TASKLIST_ID
from gtasks.utils.config import LEGACY_DEFAULT_TASKLIST_KEY, Config, ConfigKey
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList

    from gtasks.client.protocol import TasksClient

ENV_VAR = "GTASKS_LIST"

_REFRESH_HINT = "Run `gtasks tasks` to see the current numbers."


@dataclass(frozen=True)
class TargetList:
    id: str
    title: str


# --- Shared title matching -------------------------------------------------------------


def match_title[T: Mapping[str, Any]](items: list[T], title: str) -> list[T]:
    """Return the items whose title matches `title`, ignoring case; items without an ID are
    skipped, since there'd be nothing to act on."""
    wanted = title.lower()
    return [item for item in items if item.get("id") and item.get("title", "").lower() == wanted]


def _choose_one[T](
    matches: list[T],
    title: str,
    *,
    noun: str,
    hint: str,
    render: Callable[..., None],
    input_fn: Callable[[str], str] | None,
) -> T:
    """Pick one of `matches`, prompting only when the title is ambiguous."""
    if not matches:
        raise CliError(f"No {noun} named '{title}'.", hint=hint)
    if len(matches) == 1:
        return matches[0]

    ui.info(f"Several {noun}s are named '{title}':")
    render(matches, show_ids=True)
    ix = prompt_index_choice(len(matches), "Which one?", input_fn or input)
    if ix is None:
        raise Cancelled()
    return matches[ix]


# --- Task lists ------------------------------------------------------------------------


def choose_tasklist(
    matches: "list[TaskList]",
    title: str,
    input_fn: Callable[[str], str] | None = None,
) -> "TaskList":
    """Pick one list from title matches, prompting only when the title is ambiguous."""
    return _choose_one(
        matches,
        title,
        noun="task list",
        # --refresh also updates the cached lists, so retrying the command then finds it.
        hint="Run `gtasks lists --refresh` to see current lists.",
        render=ui.render_tasklists,
        input_fn=input_fn,
    )


def find_tasklist(client: "TasksClient", title: str) -> "TaskList":
    """Return the one list titled `title`; raises CliError if there's none."""
    return choose_tasklist(match_title(client.get_tasklists(), title), title)


def set_active_tasklist(cfg: Config, tasklist: "TaskList") -> None:
    cfg.set(ConfigKey.ACTIVE_TASKLIST_ID, tasklist["id"])
    cfg.set(ConfigKey.ACTIVE_TASKLIST_TITLE, tasklist.get("title", ""))


def add_tasklist_option(parser: argparse.ArgumentParser, *, top_level: bool = False) -> None:
    """Register -l/--list, so it reads the same on every list-scoped command (and before
    the subcommand: `gtasks -l Work`)."""
    add_shared_option(
        parser,
        "-l",
        "--list",
        top_level=top_level,
        default=None,
        dest="tasklist_title",
        metavar="LIST",
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
        tasklist = find_tasklist(client, explicit)
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

    matches = match_title(client.get_tasklists(), legacy_title)
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


# --- Tasks -----------------------------------------------------------------------------


def resolve_tasks_from_inputs(
    inputs: list[str],
    client: "TasksClient",
    tasklist_id: str,
    listing: ListingState | None = None,
) -> "list[Task]":
    """Resolve user inputs (1-based numbers or title strings) to task objects.

    Numbers refer to the last listing of this list the user was shown (`listing`), so
    they keep meaning what the user saw even if the list changed since. With no recorded
    listing, they index into the current needsAction list. Titles are matched (ignoring
    case) against that same needsAction list, which is fetched once, lazily.

    Raises CliError on the first input that can't be resolved, so a typo never lets the
    rest of a batch `delete` go ahead.
    """
    shown = listing.rows(tasklist_id) if listing is not None else None
    current: list | None = None
    resolved: list = []

    def open_tasks() -> list:
        nonlocal current
        if current is None:
            current = client.get_tasks(tasklist_id, show_completed=False)
        return current

    for inp in inputs:
        if not inp.isdigit():
            resolved.append(
                _choose_one(
                    match_title(open_tasks(), inp),
                    inp,
                    noun="task",
                    hint=_REFRESH_HINT,
                    render=ui.render_tasks,
                    input_fn=None,
                )
            )
            continue

        n = int(inp)
        if shown is not None:
            if not 1 <= n <= len(shown):
                raise CliError(
                    f"There's no task #{n}; the last listing showed {len(shown)}.",
                    hint=_REFRESH_HINT,
                )
            row = shown[n - 1]
            if row is None:
                raise CliError(f"Task #{n} was already completed or deleted.", hint=_REFRESH_HINT)
            resolved.append(dict(row))
        else:
            tasks = open_tasks()
            if not 1 <= n <= len(tasks):
                raise CliError(
                    f"There's no task #{n}; the list has {len(tasks)} open tasks.",
                    hint=_REFRESH_HINT,
                )
            resolved.append(tasks[n - 1])

    # `done 1 1` or a title that matches a number already given: act on each task once.
    unique = {t["id"]: t for t in resolved}
    return list(unique.values())
