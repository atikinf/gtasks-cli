"""Structural contract for anything that can act as a Google Tasks client.

Any object providing these methods - with these exact signatures - can be used
wherever a `TasksClient` is expected, whether or not it inherits from `ApiClient`.
`ApiClient` (client/api_client.py) satisfies this contract structurally; no explicit
subclassing or declaration is required or expected.
"""

from enum import Enum
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList


# Tasks API alias for the account's primary list ("My Tasks"), accepted wherever a list ID is.
DEFAULT_TASKLIST_ID = "@default"


class Status(Enum):
    NEEDS_ACTION = "needsAction"
    COMPLETED = "completed"


class TasksClient(Protocol):
    def get_tasklists(self, max_results: int | None = None) -> list[TaskList]: ...

    def get_tasklist(self, tasklist_id: str) -> TaskList: ...

    def add_tasklist(self, tasklist_title: str) -> TaskList: ...

    def update_tasklist(self, tasklist_id: str, tasklist_title: str) -> TaskList: ...

    def delete_tasklist(self, tasklist_id: str) -> None: ...

    def get_tasks(
        self,
        tasklist_id: str,
        max_results: int | None = None,
        *,
        show_completed: bool = True,
        show_hidden: bool = False,
        show_deleted: bool = False,
        show_assigned: bool = False,
        completed_min: str | None = None,
        completed_max: str | None = None,
        due_min: str | None = None,
        due_max: str | None = None,
        updated_min: str | None = None,
    ) -> list[Task]: ...

    def get_task(self, tasklist_id: str, task_id: str) -> Task: ...

    def add_task(
        self,
        tasklist_id: str,
        task_title: str,
        notes: str | None = None,
        due: str | None = None,
        parent_task_id: str | None = None,
        previous_task_id: str | None = None,
    ) -> Task: ...

    def update_task(
        self,
        tasklist_id: str,
        task_id: str,
        task_title: str | None = None,
        notes: str | None = None,
        due: str | None = None,
        status: Status | None = None,
    ) -> Task: ...

    def move_task(
        self,
        tasklist_id: str,
        task_id: str,
        parent_task_id: str | None = None,
        previous_task_id: str | None = None,
        destination_tasklist_id: str | None = None,
    ) -> Task: ...

    def complete_tasks(self, tasklist_id: str, task_ids: list[str]) -> list[Task]: ...

    def reopen_tasks(self, tasklist_id: str, task_ids: list[str]) -> list[Task]: ...

    def clear_completed_tasks(self, tasklist_id: str) -> None: ...

    def delete_tasks(self, tasklist_id: str, task_ids: list[str]) -> None: ...

    # Not part of the Tasks API: lets callers say when they're showing cached data.

    def tasks_fetched_at(self, tasklist_id: str) -> float | None:
        """When the open tasks last returned for this list were fetched (a Unix time), if
        they came from a cache; None if they were fetched live."""
        ...


class ClientProvider(Protocol):
    """What handlers receive as `get_client`: builds (once per run) the client to use.

    `fresh=True` asks for a client that never serves cached reads, for commands whose reads
    decide which task a write hits (`done`, `delete`).
    """

    def __call__(self, *, fresh: bool = False) -> TasksClient: ...
