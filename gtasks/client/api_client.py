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

    def resolve_tasklist_from_title(self, tasklist_title: str) -> list["TaskList"]:
        return [
            tl for tl in self.get_tasklists()
            if tl.get("title", "").lower() == tasklist_title.lower() and tl.get("id") is not None
        ]

    def resolve_task_from_title(self, title: str, tasklist_id: str) -> list["Task"]:
        return [
            t for t in self.get_tasks(tasklist_id)
            if t.get("title", "").lower() == title.lower() and t.get("id") is not None
        ]

    def get_tasks(
        self,
        tasklist_id: str,
        max_results: int | None = None,
        show_completed: bool = True,
        completed_min: str | None = None,
    ) -> list["Task"]:
        tasks_resource: TasksResource.TasksResource = self._service.tasks()
        kwargs_init: dict[str, Any] = {
            "tasklist": tasklist_id,
            "showCompleted": show_completed,
        }
        if completed_min is not None:
            kwargs_init["completedMin"] = completed_min
        return self._pagination_loop(kwargs_init, max_results, tasks_resource)

    def add_task(
        self,
        tasklist_id: str,
        title: str,
        notes: str | None = None,
        due: str | None = None,
    ) -> Task:
        task_body: Task = {"title": title}
        if notes is not None:
            task_body["notes"] = notes
        if due is not None:
            task_body["due"] = due

        tasks_resource = self._service.tasks()
        return tasks_resource.insert(tasklist=tasklist_id, body=task_body).execute()

    def complete_task(self, tasklist_id: str, task_id: str) -> "Task":
        tasks_resource = self._service.tasks()
        return tasks_resource.patch(
            tasklist=tasklist_id,
            task=task_id,
            body={"status": Status.COMPLETED.value},
        ).execute()

    def complete_tasks(self, tasklist_id: str, tasks: list["Task"]) -> list["Task"]:
        results: list[Task] = []
        errors: list[Exception] = []

        def _cb(request_id: str, response: "Task", exception: Exception | None) -> None:
            if exception is not None:
                errors.append(exception)
            elif response:
                results.append(response)

        batch = self._service.new_batch_http_request(callback=_cb)
        for task in tasks:
            batch.add(
                self._service.tasks().patch(
                    tasklist=tasklist_id,
                    task=task["id"],
                    body={"status": Status.COMPLETED.value},
                )
            )
        batch.execute()
        if errors:
            raise ExceptionGroup("batch complete_tasks failed", errors)
        return results

    def delete_task(self, tasklist_id: str, task_id: str) -> None:
        tasks_resource = self._service.tasks()
        tasks_resource.delete(tasklist=tasklist_id, task=task_id).execute()

    def delete_tasks(self, tasklist_id: str, tasks: list["Task"]) -> list["Task"]:
        errors: list[Exception] = []

        def _cb(request_id: str, response: object, exception: Exception | None) -> None:
            if exception is not None:
                errors.append(exception)

        batch = self._service.new_batch_http_request(callback=_cb)
        for task in tasks:
            batch.add(self._service.tasks().delete(tasklist=tasklist_id, task=task["id"]))
        batch.execute()
        if errors:
            raise ExceptionGroup("batch delete_tasks failed", errors)
        return tasks

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
