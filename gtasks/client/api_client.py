from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList


class Status(Enum):
    NEEDS_ACTION = "needsAction"
    COMPLETED = "completed"


class ApiClient:
    _service: TasksResource

    def __init__(self, service: TasksResource) -> None:
        self._service = service

    def get_tasklists(self, max_results: int | None = None) -> list[TaskList]:
        tasklists_resource: TasksResource.TasklistsResource = self._service.tasklists()

        return self._pagination_loop({}, max_results, tasklists_resource)

    def get_tasklist(self, tasklist_id: str) -> "TaskList":
        return self._service.tasklists().get(tasklist=tasklist_id).execute()

    def add_tasklist(self, tasklist_title: str) -> "TaskList":
        return self._service.tasklists().insert(body={"title": tasklist_title}).execute()

    def rename_tasklist(self, tasklist_id: str, tasklist_title: str) -> "TaskList":
        return self._service.tasklists().patch(
            tasklist=tasklist_id, body={"title": tasklist_title}
        ).execute()

    def delete_tasklist(self, tasklist_id: str) -> None:
        self._service.tasklists().delete(tasklist=tasklist_id).execute()

    def get_tasks(
        self,
        tasklist_id: str,
        max_results: int | None = None,
        show_completed: bool = True,
        completed_min: str | None = None,
    ) -> list["Task"]:
        # TODO: tasks.list also supports completedMax, dueMin/dueMax, showAssigned,
        # showDeleted, showHidden, updatedMin — not exposed yet, may be useful later.
        tasks_resource: TasksResource.TasksResource = self._service.tasks()
        kwargs_init: dict[str, Any] = {
            "tasklist": tasklist_id,
            "showCompleted": show_completed,
        }
        if completed_min is not None:
            kwargs_init["completedMin"] = completed_min
        return self._pagination_loop(kwargs_init, max_results, tasks_resource)

    def get_task(self, tasklist_id: str, task_id: str) -> "Task":
        return self._service.tasks().get(tasklist=tasklist_id, task=task_id).execute()

    def add_task(
        self,
        tasklist_id: str,
        task_title: str,
        notes: str | None = None,
        due: str | None = None,
        parent_task_id: str | None = None,
        previous_task_id: str | None = None,
    ) -> Task:
        task_body: Task = {"title": task_title}
        if notes is not None:
            task_body["notes"] = notes
        if due is not None:
            task_body["due"] = due

        insert_kwargs: dict[str, Any] = {"tasklist": tasklist_id, "body": task_body}
        if parent_task_id is not None:
            insert_kwargs["parent"] = parent_task_id
        if previous_task_id is not None:
            insert_kwargs["previous"] = previous_task_id

        tasks_resource = self._service.tasks()
        return tasks_resource.insert(**insert_kwargs).execute()

    def update_task(
        self,
        tasklist_id: str,
        task_id: str,
        task_title: str | None = None,
        notes: str | None = None,
        due: str | None = None,
    ) -> "Task":
        """Patch only the given fields; None means "leave unchanged", not "clear"."""
        task_body: Task = {}
        if task_title is not None:
            task_body["title"] = task_title
        if notes is not None:
            task_body["notes"] = notes
        if due is not None:
            task_body["due"] = due
        if not task_body:
            raise ValueError("update_task requires at least one of task_title, notes, due")

        return self._service.tasks().patch(
            tasklist=tasklist_id, task=task_id, body=task_body
        ).execute()

    def move_task(
        self,
        tasklist_id: str,
        task_id: str,
        parent_task_id: str | None = None,
        previous_task_id: str | None = None,
        destination_tasklist_id: str | None = None,
    ) -> "Task":
        kwargs: dict[str, str] = {"tasklist": tasklist_id, "task": task_id}
        if parent_task_id is not None:
            kwargs["parent"] = parent_task_id
        if previous_task_id is not None:
            kwargs["previous"] = previous_task_id
        if destination_tasklist_id is not None:
            kwargs["destinationTasklist"] = destination_tasklist_id
        return self._service.tasks().move(**kwargs).execute()

    def complete_tasks(self, tasklist_id: str, task_ids: list[str]) -> list["Task"]:
        return self._batch_patch_status(
            tasklist_id, task_ids, Status.COMPLETED, "complete_tasks"
        )

    def reopen_tasks(self, tasklist_id: str, task_ids: list[str]) -> list["Task"]:
        return self._batch_patch_status(
            tasklist_id, task_ids, Status.NEEDS_ACTION, "reopen_tasks"
        )

    def clear_completed_tasks(self, tasklist_id: str) -> None:
        self._service.tasks().clear(tasklist=tasklist_id).execute()

    def delete_tasks(self, tasklist_id: str, task_ids: list[str]) -> None:
        errors: list[Exception] = []

        def _cb(request_id: str, response: object, exception: Exception | None) -> None:
            if exception is not None:
                errors.append(exception)

        batch = self._service.new_batch_http_request(callback=_cb)
        for task_id in task_ids:
            batch.add(self._service.tasks().delete(tasklist=tasklist_id, task=task_id))
        batch.execute()
        if errors:
            raise ExceptionGroup("batch delete_tasks failed", errors)

    # TODO: revisit alongside cache work — resolve_task_from_title is pure composition
    # over get_tasks() and could become a free function; resolve_tasklist_from_title
    # does its own lookup and should probably stay a per-implementation method.

    def resolve_tasklist_from_title(self, tasklist_title: str) -> list["TaskList"]:
        return [
            tl for tl in self.get_tasklists()
            if tl.get("title", "").lower() == tasklist_title.lower() and tl.get("id") is not None
        ]

    def resolve_task_from_title(self, task_title: str, tasklist_id: str) -> list["Task"]:
        return [
            t for t in self.get_tasks(tasklist_id)
            if t.get("title", "").lower() == task_title.lower() and t.get("id") is not None
        ]

    def _batch_patch_status(
        self, tasklist_id: str, task_ids: list[str], status: Status, op_name: str
    ) -> list["Task"]:
        results: list[Task] = []
        errors: list[Exception] = []

        def _cb(request_id: str, response: "Task", exception: Exception | None) -> None:
            if exception is not None:
                errors.append(exception)
            elif response:
                results.append(response)

        batch = self._service.new_batch_http_request(callback=_cb)
        for task_id in task_ids:
            batch.add(
                self._service.tasks().patch(
                    tasklist=tasklist_id,
                    task=task_id,
                    body={"status": status.value},
                )
            )
        batch.execute()
        if errors:
            raise ExceptionGroup(f"batch {op_name} failed", errors)
        return results

    def _pagination_loop(
        self, kwargs_init: dict[str, Any], max_results: int | None, listable_resource
    ) -> list:
        all_items: list[Task] = []
        page_token: str | None = None
        n: int | None = max_results

        while True:
            kwargs: dict[str, str] = kwargs_init
            if page_token is not None:
                kwargs["pageToken"] = page_token
            if n is not None:
                kwargs["maxResults"] = n - len(all_items)
            response = listable_resource.list(**kwargs).execute()
            all_items.extend(response.get("items", []))
            page_token = response.get("nextPageToken")
            if not page_token or (n is not None and len(all_items) >= n):
                break

        return all_items[:n] if n is not None else all_items
