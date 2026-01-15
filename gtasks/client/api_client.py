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

    def get_tasks(self, tasklist_id: str, max_results: int | None = None) -> list[Task]:
        tasks_resource: TasksResource.TasksResource = self._service.tasks()

        return self._pagination_loop(
            {"tasklist": tasklist_id}, max_results, tasks_resource
        )

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

    def delete_task(self, tasklist_id: str, task_id: str) -> None:
        tasks_resource = self._service.tasks()
        tasks_resource.delete(tasklist=tasklist_id, task=task_id).execute()

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
