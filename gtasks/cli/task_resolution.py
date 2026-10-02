"""Resolve user-supplied task references (1-based display numbers or titles) to tasks."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.cli_utils import prompt_index_choice
from gtasks.cli.errors import Cancelled, CliError
from gtasks.utils.listing_state import ListingState

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task

    from gtasks.client.protocol import TasksClient

_REFRESH_HINT = "Run `gtasks tasks` to see the current numbers."


def choose_task(
    matches: "list[Task]",
    title: str,
    input_fn: Callable[[str], str] | None = None,
) -> "Task":
    """Pick one task from title matches, prompting only when the title is ambiguous."""
    matches = [t for t in matches if t.get("id")]
    if not matches:
        raise CliError(f"No task named '{title}'.", hint=_REFRESH_HINT)
    if len(matches) == 1:
        return matches[0]

    ui.info(f"Several tasks are named '{title}':")
    ui.render_tasks(matches, show_ids=True)
    ix = prompt_index_choice(len(matches), "Which one?", input_fn or input)
    if ix is None:
        raise Cancelled()
    return matches[ix]


def resolve_tasks_from_inputs(
    inputs: list[str],
    client: "TasksClient",
    tasklist_id: str,
    listing: ListingState | None = None,
) -> "list[Task]":
    """Resolve user inputs (1-based numbers or title strings) to task objects.

    Numbers refer to the last listing of this list the user was shown (`listing`), so
    they keep meaning what the user saw even if the list changed since. With no recorded
    listing, they index into the current needsAction list (fetched once, lazily).

    Raises CliError on the first input that can't be resolved, so a typo never lets the
    rest of a batch `delete` go ahead.
    """
    shown = listing.rows(tasklist_id) if listing is not None else None
    current: list | None = None
    resolved: list = []

    for inp in inputs:
        if not inp.isdigit():
            resolved.append(choose_task(client.resolve_task_from_title(inp, tasklist_id), inp))
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
            if current is None:
                current = client.get_tasks(tasklist_id, show_completed=False)
            if not 1 <= n <= len(current):
                raise CliError(
                    f"There's no task #{n}; the list has {len(current)} open tasks.",
                    hint=_REFRESH_HINT,
                )
            resolved.append(current[n - 1])

    # `done 1 1` or a title that matches a number already given: act on each task once.
    unique = {t["id"]: t for t in resolved}
    return list(unique.values())
