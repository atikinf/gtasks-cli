"""Utility functions for Google Tasks data transformation."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import TaskList


def tasklist_list_to_title_id_map(tasklists: list[TaskList]) -> dict[str, str]:
    """Convert a list of task lists to a title->id mapping."""
    title_id_map: dict[str, str] = {}
    for tasklist in tasklists:
        title: str | None = tasklist.get("title")
        id_: str | None = tasklist.get("id")
        if title is not None and id_ is not None:
            title_id_map[title] = id_
        else:
            raise ValueError("Cannot parse tasklist with empty id and title.")
    return title_id_map


def resolve_tasklist_id(tasklist_title: str, tasklists: list) -> list[str]:
    matching_ids: list[str] = []
    for tasklist in tasklists:
        cur_title = tasklist.get("title")
        cur_id = tasklist.get("id")
        if tasklist_title == cur_title and cur_id is not None:
            matching_ids.append(cur_id)
    return matching_ids
