"""A `TasksClient` that serves recent reads from the on-disk cache (`cache_store`).

Reads: task lists and a list's open tasks come from the cache while fresh (see
`CacheStore`'s TTL). Only the query the CLI makes for open tasks is cached; any other filter
goes straight to the API. With `fresh=True` cached data is never served, but what's fetched is
still stored, which is how `done`/`delete` match titles against current data.

Writes go to the API first. For task writes, the list is refetched at the same time on a
second client (so the extra call adds no wall-clock time) and the result of the write is merged
into that fresh copy. If the list was already fetched fresh in this run, that copy is reused
instead. When a merge isn't safe, the list's file is dropped so the next read refetches.
"""

import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, cast

from gtasks.client.cache_store import CacheStore, Tasks
from gtasks.client.protocol import DEFAULT_TASKLIST_ID, CacheState, Status

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList

    from gtasks.client.protocol import TasksClient

# A merge either returns the new task list, or None for "can't tell, drop the cached copy".
Merge = Callable[[Tasks], Tasks | None]


def _saved(fetched_at: float | None) -> CacheState | None:
    """State for data fetched live: saved to the cache at `fetched_at`, or None if not saved."""
    return CacheState(from_cache=False, fetched_at=fetched_at) if fetched_at is not None else None


class _Refetch:
    """Fetch a list's open tasks on a daemon thread, on its own client.

    The Google client's HTTP layer (httplib2) isn't thread-safe, so the refetch must never
    share the main client. Daemon, so a slow refetch can't hold up exit once the command is done.
    """

    def __init__(self, make_client: Callable[[], "TasksClient"], tasklist_id: str) -> None:
        self._result: Tasks | None = None
        self._thread = threading.Thread(
            target=self._run, args=(make_client, tasklist_id), daemon=True
        )
        self._thread.start()

    def _run(self, make_client: Callable[[], "TasksClient"], tasklist_id: str) -> None:
        try:
            tasks = make_client().get_tasks(tasklist_id, show_completed=False)
            self._result = cast(Tasks, tasks)
        except Exception:
            self._result = None  # treated as "no fresh copy"; never surfaces to the user

    def result(self) -> Tasks | None:
        self._thread.join()
        return self._result


class CachingClient:
    def __init__(
        self,
        store: CacheStore,
        *,
        make_inner: Callable[[], "TasksClient"],
        fresh: bool = False,
        make_refresher: Callable[[], "TasksClient"] | None = None,
    ) -> None:
        # The real client is built on first use: a command served entirely from the cache
        # never pays for building it (or importing the Google libraries behind it).
        self._make_inner = make_inner
        self._inner_client: "TasksClient | None" = None
        self._store = store
        self._fresh = fresh
        self._make_refresher = make_refresher
        # Lists fetched from the API during this run, so a write can merge into them
        # instead of refetching.
        self._fetched: dict[str, Tasks] = {}
        # How the data last returned for a list (or for all lists) relates to the cache.
        self._tasks_state: dict[str, CacheState | None] = {}
        self._tasklists_state: CacheState | None = None

    def _inner(self) -> "TasksClient":
        if self._inner_client is None:
            self._inner_client = self._make_inner()
        return self._inner_client

    # --- Cache metadata --------------------------------------------------------------------

    def tasks_cache_state(self, tasklist_id: str) -> CacheState | None:
        """Served from the cache, or fetched live and saved to it; None if neither."""
        return self._tasks_state.get(tasklist_id)

    def tasklists_cache_state(self) -> CacheState | None:
        """Served from the cache, or fetched live and saved to it; None if neither."""
        return self._tasklists_state

    # --- Task lists ------------------------------------------------------------------------

    def get_tasklists(self, max_results: int | None = None) -> "list[TaskList]":
        cached = None if self._fresh else self._store.read_tasklists()
        if cached is not None:
            items = cached[0]
            self._tasklists_state = CacheState(from_cache=True, fetched_at=cached[1])
        else:
            # Always fetch and store the full set; a limit is applied afterwards.
            items = cast(Tasks, self._inner().get_tasklists())
            self._tasklists_state = _saved(self._store.write_tasklists(items))
        return cast("list[TaskList]", items[:max_results] if max_results is not None else items)

    def get_tasklist(self, tasklist_id: str) -> "TaskList":
        if not self._fresh:
            cached = self._cached_tasklist(tasklist_id)
            if cached is not None:
                return cached
        tasklist = self._inner().get_tasklist(tasklist_id)
        if tasklist_id == DEFAULT_TASKLIST_ID and tasklist.get("id"):
            self._store.write_default(cast(dict[str, Any], tasklist))
        return tasklist

    def _cached_tasklist(self, tasklist_id: str) -> "TaskList | None":
        if tasklist_id == DEFAULT_TASKLIST_ID:
            return cast("TaskList | None", self._store.read_default())
        cached = self._store.read_tasklists()
        for item in cached[0] if cached is not None else []:
            if item.get("id") == tasklist_id:
                return cast("TaskList", item)
        return None

    def add_tasklist(self, tasklist_title: str) -> "TaskList":
        with self._dropping(tasklists=True):
            return self._inner().add_tasklist(tasklist_title)

    def update_tasklist(self, tasklist_id: str, tasklist_title: str) -> "TaskList":
        with self._dropping(tasklists=True):
            return self._inner().update_tasklist(tasklist_id, tasklist_title)

    def delete_tasklist(self, tasklist_id: str) -> None:
        with self._dropping(tasklist_id, tasklists=True):
            self._inner().delete_tasklist(tasklist_id)

    # --- Reading tasks ---------------------------------------------------------------------

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
    ) -> "list[Task]":
        filters: dict[str, Any] = dict(
            show_completed=show_completed,
            show_hidden=show_hidden,
            show_deleted=show_deleted,
            show_assigned=show_assigned,
            completed_min=completed_min,
            completed_max=completed_max,
            due_min=due_min,
            due_max=due_max,
            updated_min=updated_min,
        )
        # Only "open tasks, no other filters" is cached: that's what the CLI asks for, and
        # caching other combinations would need one file per filter set.
        canonical = (
            tasklist_id != DEFAULT_TASKLIST_ID
            and not show_completed
            and not any(v for k, v in filters.items() if k != "show_completed")
        )
        if not canonical:
            return self._inner().get_tasks(tasklist_id, max_results, **filters)

        tasks = self._read_open_tasks(tasklist_id)
        return cast("list[Task]", tasks[:max_results] if max_results is not None else tasks)

    def _read_open_tasks(self, tasklist_id: str) -> Tasks:
        if not self._fresh:
            cached = self._store.read_tasks(tasklist_id)
            if cached is not None:
                tasks, fetched_at = cached
                self._tasks_state[tasklist_id] = CacheState(from_cache=True, fetched_at=fetched_at)
                return tasks
        # Fetch the whole open list (all pages) so the cached copy is never partial.
        tasks = cast(Tasks, self._inner().get_tasks(tasklist_id, show_completed=False))
        self._tasks_state[tasklist_id] = _saved(self._store.write_tasks(tasklist_id, tasks))
        self._fetched[tasklist_id] = tasks
        return tasks

    def get_task(self, tasklist_id: str, task_id: str) -> "Task":
        return self._inner().get_task(tasklist_id, task_id)

    # --- Writing tasks ---------------------------------------------------------------------

    def add_task(
        self,
        tasklist_id: str,
        task_title: str,
        notes: str | None = None,
        due: str | None = None,
        parent_task_id: str | None = None,
        previous_task_id: str | None = None,
    ) -> "Task":
        def add() -> "Task":
            return self._inner().add_task(
                tasklist_id, task_title, notes, due, parent_task_id, previous_task_id
            )

        def merge(task: "Task") -> Merge:
            if parent_task_id is not None or previous_task_id is not None:
                return lambda tasks: None  # can't tell where it went
            # The refetch may have run before or after the insert; don't add it twice.
            # A task added without a position goes to the top of the list.
            return lambda tasks: (
                tasks if any(t.get("id") == task.get("id") for t in tasks)
                else [cast(dict[str, Any], task), *tasks]
            )

        return self._write(tasklist_id, add, merge)

    def update_task(
        self,
        tasklist_id: str,
        task_id: str,
        task_title: str | None = None,
        notes: str | None = None,
        due: str | None = None,
        status: Status | None = None,
    ) -> "Task":
        def update() -> "Task":
            return self._inner().update_task(tasklist_id, task_id, task_title, notes, due, status)

        def merge(task: "Task") -> Merge:
            def apply(tasks: Tasks) -> Tasks | None:
                if task.get("status") == Status.COMPLETED.value:
                    return [t for t in tasks if t.get("id") != task_id]
                if not any(t.get("id") == task_id for t in tasks):
                    return None  # newly open again, position unknown
                return [cast(dict[str, Any], task) if t.get("id") == task_id else t
                        for t in tasks]

            return apply

        return self._write(tasklist_id, update, merge)

    def complete_tasks(self, tasklist_id: str, task_ids: list[str]) -> "list[Task]":
        done = set(task_ids)
        return self._write(
            tasklist_id,
            lambda: self._inner().complete_tasks(tasklist_id, task_ids),
            lambda _: lambda tasks: [t for t in tasks if t.get("id") not in done],
        )

    def delete_tasks(self, tasklist_id: str, task_ids: list[str]) -> None:
        def without_deleted(tasks: Tasks) -> Tasks:
            # Deleting a task takes its subtasks with it, so drop descendants too.
            gone = set(task_ids)
            changed = True
            while changed:
                changed = False
                for t in tasks:
                    if t.get("parent") in gone and t.get("id") not in gone:
                        gone.add(t["id"])
                        changed = True
            return [t for t in tasks if t.get("id") not in gone]

        self._write(
            tasklist_id,
            lambda: self._inner().delete_tasks(tasklist_id, task_ids),
            lambda _: without_deleted,
        )

    def reopen_tasks(self, tasklist_id: str, task_ids: list[str]) -> "list[Task]":
        with self._dropping(tasklist_id):  # reopened tasks' positions are unknown
            return self._inner().reopen_tasks(tasklist_id, task_ids)

    def move_task(
        self,
        tasklist_id: str,
        task_id: str,
        parent_task_id: str | None = None,
        previous_task_id: str | None = None,
        destination_tasklist_id: str | None = None,
    ) -> "Task":
        destination = [destination_tasklist_id] if destination_tasklist_id is not None else []
        with self._dropping(tasklist_id, *destination):
            return self._inner().move_task(
                tasklist_id, task_id, parent_task_id, previous_task_id, destination_tasklist_id
            )

    def clear_completed_tasks(self, tasklist_id: str) -> None:
        with self._dropping(tasklist_id):
            self._inner().clear_completed_tasks(tasklist_id)

    # --- Internals -------------------------------------------------------------------------

    def _write[R](
        self, tasklist_id: str, mutate: Callable[[], R], merge_for: Callable[[R], Merge]
    ) -> R:
        """Run a task write, refetching the list alongside it, then merge the result in."""
        # Build the main client (loading credentials) before the refetch thread starts, so
        # the two never race to load or refresh the same credentials.
        self._inner()
        base = self._fetched.get(tasklist_id)
        refetch = None
        if base is None and self._make_refresher is not None:
            refetch = _Refetch(self._make_refresher, tasklist_id)

        try:
            result = mutate()
        except BaseException:
            # Includes a batch that partly failed (ExceptionGroup): what changed is unknown.
            self._drop_tasks(tasklist_id)
            raise

        merge = merge_for(result)
        if refetch is not None:
            base = refetch.result()
            if base is None:  # refetch failed; the write itself succeeded
                self._drop_tasks(tasklist_id)
                return result

        if base is None:
            # No fresh copy and no refresher: patch whatever is cached, keeping its age.
            self._store.update_tasks(tasklist_id, merge)
            return result

        merged = merge(base)
        if merged is None:
            self._drop_tasks(tasklist_id)
        else:
            self._store.write_tasks(tasklist_id, merged)
            self._fetched[tasklist_id] = merged
        return result

    @contextmanager
    def _dropping(self, *tasklist_ids: str, tasklists: bool = False) -> Iterator[None]:
        """Drop these cached lists (and/or the list index) once the write is done, even if
        it failed: for writes whose effect on the cached copy can't be merged."""
        try:
            yield
        finally:
            if tasklists:
                self._store.drop_tasklists()
            for tasklist_id in tasklist_ids:
                self._drop_tasks(tasklist_id)

    def _drop_tasks(self, tasklist_id: str) -> None:
        self._store.drop_tasks(tasklist_id)
        self._fetched.pop(tasklist_id, None)
