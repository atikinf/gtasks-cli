"""The order tasks are shown in: the Google Tasks app's own, with subtasks under their parent.

The API returns open tasks most recently updated first. The app shows the user's manual order,
which the API exposes as `position`: zero-padded digit strings (so they compare as strings),
ordering a task among its siblings. Pure, no I/O.
"""

from collections.abc import Mapping
from typing import Any


def display_order[T: Mapping[str, Any]](tasks: list[T]) -> list[T]:
    """Top-level tasks by position, each followed by its subtasks by position.

    A subtask whose parent isn't among `tasks` (e.g. the parent is completed, or a match list
    holds only the child) is placed as a top-level task.
    """
    ids = {t.get("id") for t in tasks}
    top: list[T] = []
    children: dict[Any, list[T]] = {}  # keyed by parent ID
    for task in tasks:
        parent = task.get("parent")
        if parent in ids and parent != task.get("id"):
            children.setdefault(parent, []).append(task)
        else:
            top.append(task)

    def by_position(siblings: list[T]) -> list[T]:
        return sorted(siblings, key=lambda t: t.get("position") or "")

    ordered: list[T] = []

    def place(task: T) -> None:
        ordered.append(task)
        # Google Tasks nests one level deep; recursing costs nothing if that ever changes.
        for child in by_position(children.get(task.get("id"), [])):
            place(child)

    for task in by_position(top):
        place(task)
    return ordered
