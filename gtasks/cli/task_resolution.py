"""Resolve user-supplied task references (1-based indices or titles) via the API."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli.cli_utils import print_tasks, prompt_index_choice

if TYPE_CHECKING:
    from gtasks.client.api_client import ApiClient


def prompt_choose_task_id(ids: list[str], tasks: list, task_title: str) -> None | str:
    if len(ids) <= 0:
        print(f"Error: No task found with title '{task_title}'!")
    elif len(ids) == 1:
        return ids[0]
    else:
        filtered_tasks = [t for t in tasks if t.get("id") in ids]
        print_tasks(filtered_tasks, argparse.Namespace(show_ids=True))
        ix_choice: None | int = prompt_index_choice(
            len(filtered_tasks),
            f"Found multiple tasks with title '{task_title}'.",
            input,
        )
        if ix_choice is not None:
            return filtered_tasks[ix_choice].get("id")

    return None


def resolve_tasks_from_inputs(
    inputs: list[str],
    client: "ApiClient",
    tasklist_id: str,
) -> list:
    """Resolve user inputs (1-based indices or title strings) to full task objects.

    Digit inputs are treated as 1-based display indices into the needsAction list
    (fetched lazily on the first digit input). Other inputs are matched by title
    with interactive disambiguation when multiple tasks share a title.
    """
    all_tasks: list | None = None
    resolved: list = []
    for inp in inputs:
        if inp.isdigit():
            if all_tasks is None:
                all_tasks = client.get_tasks(tasklist_id, show_completed=False)
            ix = int(inp) - 1
            if 0 <= ix < len(all_tasks):
                task = all_tasks[ix]
                if task.get("id"):
                    resolved.append(task)
            else:
                n = len(all_tasks) if all_tasks else 0
                print(f"Error: index {inp} is out of range (list has {n} tasks)")
        else:
            matches = client.resolve_task_from_title(inp, tasklist_id)
            ids = [t["id"] for t in matches if t.get("id")]
            task_id = prompt_choose_task_id(ids, matches, inp)
            if task_id:
                task = next((t for t in matches if t.get("id") == task_id), None)
                if task:
                    resolved.append(task)
    return resolved
