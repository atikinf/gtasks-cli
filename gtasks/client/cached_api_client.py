from pathlib import Path
from typing import TYPE_CHECKING, override

from gtasks.client.client_utils import tasklist_list_to_title_id_map
from gtasks.utils.bidict_cache import BidictCache

from .api_client import ApiClient

CONFIG_DIR: Path = Path("~/.config/gtasks-cli").expanduser()


SCOPES: list[str] = ["https://www.googleapis.com/auth/tasks"]

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource
    from googleapiclient._apis.tasks.v1.schemas import TaskList


# TODO: Unused. Needs refining. When to refresh/invalidate cache?
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
        tasklists: list[TaskList] = super().get_tasklists(max_results)
        self._title_id_cache.clear_and_update(tasklist_list_to_title_id_map(tasklists))
        self._title_id_cache.save()

        return tasklists

    @override
    def resolve_tasklist_id(
        self,
        tasklist_title: str,
    ) -> list[str]:
        """Resolve a tasklist title to its ID using the cache."""
        return list(self._title_id_cache[tasklist_title])
