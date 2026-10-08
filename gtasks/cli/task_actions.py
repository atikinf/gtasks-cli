"""The flow shared by commands that act on tasks the user names (`done`, `delete`)."""

import argparse
from collections.abc import Callable
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.cli.listing_state import ListingState
from gtasks.cli.title_id_resolution import (
    ResolvedTasks,
    TargetList,
    resolve_target_tasklist,
    resolve_tasks_from_inputs,
)
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider, TasksClient


def act_on_tasks(
    args: argparse.Namespace,
    get_client: "ClientProvider",
    cfg: Config,
    *,
    verb: str,
    act: Callable[["TasksClient", str, list[str]], object],
    confirm: Callable[[ResolvedTasks, TargetList], None] | None = None,
) -> None:
    """Resolve `args.tasks` (numbers or titles) in the target list, optionally `confirm`, then
    `act(client, tasklist_id, task_ids)`, retire the acted-on listing numbers, and report."""
    # Fresh: stale data here could make the write hit the wrong task.
    client = get_client(fresh=True)
    target = resolve_target_tasklist(args, client, cfg)
    listing = ListingState.default()
    resolved = resolve_tasks_from_inputs(args.tasks, client, target.id, listing)
    if confirm is not None:
        confirm(resolved, target)

    task_ids = [t["id"] for t in resolved.tasks]
    act(client, target.id, task_ids)
    listing.consume(target.id, task_ids)
    ui.report_mutation(verb, [ui.display_title(t) for t in resolved.tasks], target.title)
