import sys
from typing import TYPE_CHECKING, override

from gtasks.utils.bidict_cache import BidictCache
from gtasks.utils.tasks_cache import TasksCache

from .api_client import ApiClient

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList


class CachedApiClient(ApiClient):
    def __init__(
        self,
        service: "TasksResource",
        title_id_cache: BidictCache[str, str],  # title <-> id tasklists
        tasks_cache: TasksCache,
    ) -> None:
        super().__init__(service)
        self._title_id_cache: BidictCache[str, str] = title_id_cache
        self._tasks_cache: TasksCache = tasks_cache

    @override
    def get_tasklists(
        self,
        max_results: int | None = None,
    ) -> list["TaskList"]:
        if self._title_id_cache:
            items = [{"title": t, "id": i} for t, i in self._title_id_cache.items()]
            return items[:max_results] if max_results is not None else items

        # Cache empty: fetch all from API and populate cache for future calls.
        tasklists: list[TaskList] = super().get_tasklists(None)
        self._title_id_cache.overwrite(self._dedup_by_title(tasklists, "tasklist"))
        return tasklists[:max_results] if max_results is not None else tasklists

    @override
    def get_tasks(
        self,
        tasklist_id: str,
        max_results: int | None = None,
        show_completed: bool = True,
        completed_min: str | None = None,
    ) -> list["Task"]:
        # Bypass cache for completed_min — rare, specific filter not worth caching.
        if completed_min is not None:
            return super().get_tasks(tasklist_id, max_results, show_completed, completed_min)

        cached = self._tasks_cache.get(tasklist_id)
        if cached is None:
            # Fetch all tasks once (completed + needsAction) so the cache serves all callers.
            cached = super().get_tasks(tasklist_id, show_completed=True)
            self._tasks_cache.set(tasklist_id, cached)

        result = cached if show_completed else [t for t in cached if t.get("status") != "completed"]
        return result[:max_results] if max_results is not None else result

    @override
    def add_task(
        self,
        tasklist_id: str,
        title: str,
        notes: str | None = None,
        due: str | None = None,
    ) -> "Task":
        task = super().add_task(tasklist_id, title, notes, due)
        self._tasks_cache.invalidate(tasklist_id)
        return task

    @override
    def complete_task(self, tasklist_id: str, task_id: str) -> "Task":
        task = super().complete_task(tasklist_id, task_id)
        self._tasks_cache.invalidate(tasklist_id)
        return task

    @override
    def delete_task(self, tasklist_id: str, task_id: str) -> None:
        super().delete_task(tasklist_id, task_id)
        self._tasks_cache.invalidate(tasklist_id)

    @override
    def resolve_task_from_title(self, title: str, tasklist_id: str) -> list["Task"]:
        return [
            t for t in self.get_tasks(tasklist_id)
            if t.get("title", "").lower() == title.lower()
        ]

    @staticmethod
    def _dedup_by_title(items: list[dict], label: str) -> dict[str, str]:
        """Build a title->id mapping, warning to stderr on duplicate titles."""
        deduped: dict[str, str] = {}
        for item in items:
            title, id_ = item.get("title"), item.get("id")
            if not title or not id_:
                continue
            if title in deduped:
                print(
                    f"Warning: duplicate {label} title '{title}' — skipping duplicate in cache",
                    file=sys.stderr,
                )
                continue
            deduped[title] = id_
        return deduped

    def refresh_cache(self) -> list["TaskList"]:
        """Force-clear and repopulate the tasklist cache from the API.

        # TODO: add a configurable auto-refresh cutoff (e.g. invalidate cache
        # entries older than N hours) so callers don't need to invoke this
        # explicitly when the cache is stale.
        # TODO: Add async functionality.
        """
        self._tasks_cache.clear()
        self._title_id_cache.clear()
        return self.get_tasklists()

    @override
    def resolve_tasklist_from_title(
        self,
        tasklist_title: str,
    ) -> list["TaskList"]:
        """Resolve a tasklist title to a list of matching TaskList dicts using the cache.

        Populates the cache via get_tasklists() if it is empty.
        Returns a single-element list on a hit, or an empty list on a miss.
        """
        if not self._title_id_cache:
            self.get_tasklists()
        try:
            return [{"title": tasklist_title, "id": self._title_id_cache[tasklist_title]}]
        except KeyError:
            return []
