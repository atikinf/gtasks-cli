from typing import TYPE_CHECKING, Any, cast

from gtasks.client.protocol import Status

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList


def _given(**fields: Any) -> dict[str, Any]:
    """Drop unset (None) values, so they're left out of a request rather than sent.

    In a body that matters: None is sent as JSON null, which a patch takes as "clear this
    field". googleapiclient already drops None query parameters, but its stubs type them
    as `str`, so they go through here too.
    """
    return {k: v for k, v in fields.items() if v is not None}


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

    def update_tasklist(self, tasklist_id: str, tasklist_title: str) -> "TaskList":
        return self._service.tasklists().patch(
            tasklist=tasklist_id, body={"title": tasklist_title}
        ).execute()

    def delete_tasklist(self, tasklist_id: str) -> None:
        self._service.tasklists().delete(tasklist=tasklist_id).execute()

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
    ) -> list["Task"]:
        tasks_resource: TasksResource.TasksResource = self._service.tasks()
        kwargs_init: dict[str, Any] = {
            "tasklist": tasklist_id,
            "showCompleted": show_completed,
            "showHidden": show_hidden,
            "showDeleted": show_deleted,
            "showAssigned": show_assigned,
            **_given(
                completedMin=completed_min,
                completedMax=completed_max,
                dueMin=due_min,
                dueMax=due_max,
                updatedMin=updated_min,
            ),
        }
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
    ) -> "Task":
        return self._service.tasks().insert(
            tasklist=tasklist_id,
            body=cast("Task", _given(title=task_title, notes=notes, due=due)),
            **_given(parent=parent_task_id, previous=previous_task_id),
        ).execute()

    def update_task(
        self,
        tasklist_id: str,
        task_id: str,
        task_title: str | None = None,
        notes: str | None = None,
        due: str | None = None,
        status: Status | None = None,
    ) -> "Task":
        """Patch only the given fields; None means "leave unchanged", not "clear"."""
        task_body = _given(
            title=task_title,
            notes=notes,
            due=due,
            status=status.value if status is not None else None,
        )
        if not task_body:
            raise ValueError(
                "update_task requires at least one of task_title, notes, due, status"
            )

        return self._service.tasks().patch(
            tasklist=tasklist_id, task=task_id, body=cast("Task", task_body)
        ).execute()

    def move_task(
        self,
        tasklist_id: str,
        task_id: str,
        parent_task_id: str | None = None,
        previous_task_id: str | None = None,
        destination_tasklist_id: str | None = None,
    ) -> "Task":
        return self._service.tasks().move(
            tasklist=tasklist_id,
            task=task_id,
            **_given(
                parent=parent_task_id,
                previous=previous_task_id,
                destinationTasklist=destination_tasklist_id,
            ),
        ).execute()

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

    def tasks_fetched_at(self, tasklist_id: str) -> None:
        """Always None: every read is live."""
        return None

    def tasklists_fetched_at(self) -> None:
        """Always None: every read is live."""
        return None

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
            kwargs: dict[str, Any] = dict(kwargs_init)
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
