from pathlib import Path
from typing import TYPE_CHECKING

from gtasks.api_client import ApiClient
from gtasks.silly_utils import tasklist_list_to_title_id_map
from gtasks.utils.bidict_cache import BidictCache

CONFIG_DIR: Path = Path("~/.config/gtasks-cli").expanduser()


SCOPES: list[str] = ["https://www.googleapis.com/auth/tasks"]

"""
    IGNORE, BROKEN AF!!! Will be fixed shortly
"""

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList


class Service:
    def __init__(
        self,
        client: ApiClient,
        title_id_cache: BidictCache[str, str],  # title <-> id tasklists
    ) -> None:
        self._client: ApiClient = client
        self._title_id_cache: BidictCache[str, str] = title_id_cache

    def list_tasklists(
        self,
        max_results: int | None = None,
    ) -> list[TaskList]:
        tasklists: list[TaskList] = self._client.get_tasklists(max_results)
        self._title_id_cache.clear_and_update(tasklist_list_to_title_id_map(tasklists))
        self._title_id_cache.save()

        return tasklists

    def list_tasks(
        self,
        tasklist_id: str | None = None,
        tasklist_title: str | None = None,
        max_results: int | None = None,
    ) -> list[Task]:
        """
        Note:
            Only one of ``tasklist_id`` or ``tasklist_title`` may be provided.
        """
        assert tasklist_id is not None and tasklist_title is not None

        resolved_tasklist_id: str = tasklist_id
        if tasklist_title is not None:
            resolved_tasklist_id = self._title_id_cache[tasklist_title]

        return self._client.get_tasks(resolved_tasklist_id, max_results)

    def add_task(
        self,
        tasklist_id: str,
        title: str,
        notes: str | None = None,
        due: str | None = None,
    ) -> Task:
        self._client.add_task()
