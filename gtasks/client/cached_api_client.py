from typing import TYPE_CHECKING, override

from gtasks.client.client_utils import tasklist_list_to_title_id_map
from gtasks.utils.bidict_cache import BidictCache

from .api_client import ApiClient

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource
    from googleapiclient._apis.tasks.v1.schemas import TaskList


class CachedApiClient(ApiClient):
    def __init__(
        self,
        service: "TasksResource",
        title_id_cache: BidictCache[str, str],  # title <-> id tasklists
    ) -> None:
        super().__init__(service)
        self._title_id_cache: BidictCache[str, str] = title_id_cache

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
        self._title_id_cache.clear_and_update(tasklist_list_to_title_id_map(tasklists))
        self._title_id_cache.save()
        return tasklists[:max_results] if max_results is not None else tasklists

    def refresh_cache(self) -> list["TaskList"]:
        """Force-clear and repopulate the tasklist cache from the API.

        # TODO: add a configurable auto-refresh cutoff (e.g. invalidate cache
        # entries older than N hours) so callers don't need to invoke this
        # explicitly when the cache is stale.
        """
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
