"""Structural contract for anything that can act as a Google Tasks client.

Any object providing these seven methods - with these exact signatures - can be used
wherever a `TasksClient` is expected, whether or not it inherits from `ApiClient`.
`ApiClient` (client/api_client.py) satisfies this contract structurally; no explicit
subclassing or declaration is required or expected.
"""

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList


class TasksClient(Protocol):
    def get_tasklists(self, max_results: int | None = None) -> list[TaskList]: ...

    def resolve_tasklist_from_title(self, tasklist_title: str) -> list[TaskList]: ...

    def resolve_task_from_title(self, task_title: str, tasklist_id: str) -> list[Task]: ...

    def get_tasks(
        self,
        tasklist_id: str,
        max_results: int | None = None,
        show_completed: bool = True,
        completed_min: str | None = None,
    ) -> list[Task]: ...

    def add_task(
        self,
        tasklist_id: str,
        task_title: str,
        notes: str | None = None,
        due: str | None = None,
    ) -> Task: ...

    def complete_tasks(self, tasklist_id: str, task_ids: list[str]) -> list[Task]: ...

    def delete_tasks(self, tasklist_id: str, task_ids: list[str]) -> None: ...
