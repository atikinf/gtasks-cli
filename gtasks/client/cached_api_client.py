import sys
from pathlib import Path
from typing import TYPE_CHECKING, override

from gtasks.utils.bidict_cache import BidictCache

from .api_client import ApiClient

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList


class CachedApiClient(ApiClient):
    def __init__(
        self,
        service: "TasksResource",
        title_id_cache: BidictCache[str, str],  # title <-> id tasklists
        tasks_cache_dir: Path,
        tasks_cache: dict[str, BidictCache[str, str]],
    ) -> None:
        super().__init__(service)
        self._title_id_cache: BidictCache[str, str] = title_id_cache
        self._tasks_cache_dir: Path = tasks_cache_dir
        self._tasks_cache: dict[str, BidictCache[str, str]] = tasks_cache

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
        # TODO: Write dedicated tasks cache that includes task metadata.
        # Cache only stores title->id; callers expecting full task objects
        # (due dates, notes, status) would get stripped results. Bypass until fixed.
        return super().get_tasks(tasklist_id, max_results, show_completed, completed_min)

        # Only cache the default unfiltered call — bypass for any filtered variant.
        if max_results is not None or not show_completed or completed_min is not None:
            return super().get_tasks(tasklist_id, max_results, show_completed, completed_min)

        if tasklist_id not in self._tasks_cache:
            cache_file = self._tasks_cache_dir / f"{tasklist_id}.json"
            if cache_file.exists():
                self._tasks_cache[tasklist_id] = BidictCache(cache_file)
            else:
                tasks = super().get_tasks(tasklist_id)
                cache = BidictCache(cache_file)
                cache.overwrite(self._dedup_by_title(tasks, "task"))
                self._tasks_cache[tasklist_id] = cache

        cache = self._tasks_cache[tasklist_id]
        return [{"title": t, "id": i} for t, i in cache.items()]

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
        if self._tasks_cache_dir.exists():
            for f in self._tasks_cache_dir.glob("*.json"):
                f.unlink()
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
