"""Shell Tab completion of task and list titles (via argcomplete).

Every Tab press runs gtasks, so completers read only local data: the cache's fresh files,
found through its `current` record (no sign-in, no Google imports, no network). Suggestions
are hints; whatever is finally typed is matched again on Enter (see `title_matching`).
A completer never raises: any failure means no suggestions.

`argcomplete` itself is imported only while completing (or by `gtasks completion`).
"""

import argparse
import os
from collections.abc import Callable
from datetime import date
from functools import wraps
from typing import Any

from gtasks import defaults
from gtasks.cli import ui
from gtasks.cli.title_matching import complete_titles, match_titles, normalize
from gtasks.client.cache_store import CacheStore
from gtasks.defaults import ENV_VAR
from gtasks.utils.config import Config, ConfigKey

# Candidates, or {candidate: description} (zsh and fish show descriptions; bash ignores them).
Completer = Callable[..., list[str] | dict[str, str]]


def attach(action: argparse.Action, completer: Completer) -> argparse.Action:
    """Give an argparse argument its Tab completer (argcomplete reads `.completer`)."""
    setattr(action, "completer", completer)
    return action


def complete(parser: argparse.ArgumentParser) -> None:
    """Answer the shell's completion request; called only when it asks.

    Normally exits the process. Returns (offering nothing) if argcomplete isn't installed,
    e.g. an install that predates the dependency; the caller must then stop, not run a command.
    """
    try:
        import argcomplete
        from argcomplete.completers import SuppressCompleter
    except ImportError:
        return

    argcomplete.autocomplete(
        parser,
        # Prefix match ignoring case and spacing, the same rule Enter-matching uses.
        validator=lambda candidate, prefix: normalize(candidate).startswith(normalize(prefix)),
        # Arguments without a completer (e.g. a new task's title) get nothing, not file names,
        # and flags are offered only once a "-" is typed, not mixed in with titles.
        default_completer=SuppressCompleter(),
        always_complete_options=False,
    )


def _never_raises(completer: Completer) -> Completer:
    @wraps(completer)
    def safe(*args: Any, **kwargs: Any) -> list[str] | dict[str, str]:
        try:
            return completer(*args, **kwargs)
        except Exception:
            return []

    return safe


def _store() -> CacheStore | None:
    return CacheStore.for_current_account(defaults.CACHE_DIR)


@_never_raises
def complete_tasklists(prefix: str, **_: Any) -> list[str]:
    """Titles of all lists (`-l/--list`, `use NAME`)."""
    store = _store()
    cached = store.read_tasklists() if store is not None else None
    if cached is None:
        return []
    return complete_titles((tl.get("title") or "" for tl in cached[0]), prefix)


@_never_raises
def complete_tasks(
    prefix: str, parsed_args: argparse.Namespace, **_: Any
) -> dict[str, str] | list[str]:
    """Open-task titles of the list the command would act on (`done`/`delete`), each described
    by its due date where it has one (zsh and fish show descriptions; bash ignores them)."""
    store = _store()
    if store is None:
        return []
    tasklist_id = _target_tasklist_id(store, parsed_args)
    cached = store.read_tasks(tasklist_id) if tasklist_id else None
    if cached is None:
        return []
    already = {normalize(t) for t in getattr(parsed_args, "tasks", None) or []}
    tasks = [t for t in cached[0] if normalize(t.get("title") or "") not in already]
    titles = complete_titles((t.get("title") or "" for t in tasks), prefix)
    due_by_title: dict[str, str] = {}
    for task in tasks:  # first task wins for duplicate titles, as in complete_titles
        title, due = task.get("title") or "", task.get("due")
        if title not in due_by_title:
            due_by_title[title] = ui.format_due(due, date.today())[0] if due else ""
    return {title: due_by_title.get(title, "") for title in titles}


@_never_raises
def complete_config_keys(prefix: str, **_: Any) -> list[str]:
    return [k.value for k in ConfigKey if k.value.startswith(prefix)]


@_never_raises
def complete_config_values(prefix: str, parsed_args: argparse.Namespace, **_: Any) -> list[str]:
    from gtasks.cli.parsers.config_parser import _ALLOWED_VALUES

    allowed = _ALLOWED_VALUES.get(ConfigKey(parsed_args.key), ())
    return [v for v in allowed if v.startswith(prefix)]


def _target_tasklist_id(store: CacheStore, parsed_args: argparse.Namespace) -> str | None:
    """The list a command would act on, by the same precedence as `resolve_target_tasklist`,
    but using only cached data."""
    explicit = getattr(parsed_args, "tasklist_title", None) or os.environ.get(ENV_VAR)
    if explicit:
        cached = store.read_tasklists()
        match = match_titles(cached[0], explicit) if cached is not None else None
        # An ambiguous or unknown list gets no suggestions rather than a guess.
        return match.matches[0]["id"] if match is not None and len(match.matches) == 1 else None

    active = Config(defaults.CONFIG_FILE_PATH).get(ConfigKey.ACTIVE_TASKLIST_ID)
    if active:
        return active

    default = store.read_default()
    return default["id"] if default is not None else None

