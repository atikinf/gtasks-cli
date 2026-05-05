from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gtasks.client.cached_api_client import CachedApiClient
from gtasks.utils.bidict_cache import BidictCache
from gtasks.utils.tasks_cache import TasksCache


@pytest.fixture
def service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def empty_cache() -> BidictCache:
    return BidictCache()  # no cache_path → in-memory only, starts empty


@pytest.fixture
def populated_cache() -> BidictCache:
    cache: BidictCache[str, str] = BidictCache()
    cache.update({"Work": "list1", "Personal": "list2"})
    return cache


@pytest.fixture
def tasks_cache(tmp_path: Path) -> TasksCache:
    return TasksCache(tmp_path / "tasks")


@pytest.fixture
def client_empty_cache(
    service: MagicMock, empty_cache: BidictCache, tasks_cache: TasksCache
) -> CachedApiClient:
    return CachedApiClient(service, empty_cache, tasks_cache)


@pytest.fixture
def client_populated_cache(
    service: MagicMock, populated_cache: BidictCache, tasks_cache: TasksCache
) -> CachedApiClient:
    return CachedApiClient(service, populated_cache, tasks_cache)


class TestCachedGetTasklists:
    SAMPLE_TASKLISTS = [
        {"id": "list1", "title": "Work"},
        {"id": "list2", "title": "Personal"},
    ]

    def test_GIVEN_empty_cache_THEN_fetches_from_api_and_populates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, empty_cache: BidictCache
    ) -> None:
        service.tasklists().list().execute.return_value = {"items": self.SAMPLE_TASKLISTS}

        with patch.object(empty_cache, "_save"):
            result = client_empty_cache.get_tasklists()

        service.tasklists().list.assert_called()
        assert result == self.SAMPLE_TASKLISTS
        assert empty_cache["Work"] == "list1"
        assert empty_cache["Personal"] == "list2"

    def test_GIVEN_populated_cache_THEN_returns_from_cache_without_api_call(
        self, client_populated_cache: CachedApiClient, service: MagicMock
    ) -> None:
        result = client_populated_cache.get_tasklists()

        service.tasklists().list.assert_not_called()
        assert {"title": "Work", "id": "list1"} in result
        assert {"title": "Personal", "id": "list2"} in result

    def test_GIVEN_populated_cache_and_max_results_THEN_truncates(
        self, client_populated_cache: CachedApiClient, service: MagicMock
    ) -> None:
        result = client_populated_cache.get_tasklists(max_results=1)

        service.tasklists().list.assert_not_called()
        assert len(result) == 1

    def test_GIVEN_empty_cache_and_max_results_THEN_fetches_all_and_truncates(
        self, client_empty_cache: CachedApiClient, service: MagicMock, empty_cache: BidictCache
    ) -> None:
        service.tasklists().list().execute.return_value = {"items": self.SAMPLE_TASKLISTS}

        with patch.object(empty_cache, "_save"):
            result = client_empty_cache.get_tasklists(max_results=1)

        # Fetched with max_results=None to fully populate the cache
        service.tasklists().list.assert_called_with()
        assert len(result) == 1
        # Cache has all items, not just the truncated result
        assert len(empty_cache) == 2


class TestCachedGetTasks:
    SAMPLE_TASKS = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
        {"id": "task2", "title": "Walk dog", "status": "needsAction"},
    ]
    SAMPLE_TASKS_WITH_COMPLETED = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
        {"id": "task2", "title": "Walk dog", "status": "completed"},
    ]

    def test_GIVEN_cache_miss_THEN_fetches_from_api_and_caches(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        service.tasks().list().execute.return_value = {"items": self.SAMPLE_TASKS}

        result = client_empty_cache.get_tasks("list1")

        service.tasks().list.assert_called()
        assert result == self.SAMPLE_TASKS
        assert tasks_cache.get("list1") == self.SAMPLE_TASKS

    def test_GIVEN_cache_hit_THEN_returns_from_cache_without_api_call(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)

        result = client_empty_cache.get_tasks("list1")

        service.tasks().list.assert_not_called()
        assert result == self.SAMPLE_TASKS

    def test_GIVEN_show_completed_false_THEN_filters_completed_from_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS_WITH_COMPLETED)

        result = client_empty_cache.get_tasks("list1", show_completed=False)

        service.tasks().list.assert_not_called()
        assert result == [{"id": "task1", "title": "Buy milk", "status": "needsAction"}]

    def test_GIVEN_max_results_THEN_truncates_cached_result(
        self, client_empty_cache: CachedApiClient, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)

        result = client_empty_cache.get_tasks("list1", max_results=1)

        assert len(result) == 1

    def test_GIVEN_completed_min_THEN_bypasses_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)
        service.tasks().list().execute.return_value = {"items": []}

        client_empty_cache.get_tasks("list1", completed_min="2026-01-01T00:00:00Z")

        service.tasks().list.assert_called()


class TestCachedGetTasksMutationInvalidation:
    SAMPLE_TASKS = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
    ]

    def test_add_task_THEN_invalidates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)
        service.tasks().insert().execute.return_value = {"id": "task2", "title": "New"}

        client_empty_cache.add_task("list1", "New")

        assert tasks_cache.get("list1") is None

    def test_complete_task_THEN_invalidates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)
        service.tasks().patch().execute.return_value = {}

        client_empty_cache.complete_task("list1", "task1")

        assert tasks_cache.get("list1") is None

    def test_delete_task_THEN_invalidates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)
        service.tasks().delete().execute.return_value = None

        client_empty_cache.delete_task("list1", "task1")

        assert tasks_cache.get("list1") is None

    def test_complete_tasks_THEN_invalidates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)
        batch_mock = MagicMock()
        service.new_batch_http_request.return_value = batch_mock

        client_empty_cache.complete_tasks("list1", self.SAMPLE_TASKS)

        assert tasks_cache.get("list1") is None

    def test_complete_tasks_GIVEN_batch_error_THEN_still_invalidates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)

        def fake_execute_with_error():
            cb = service.new_batch_http_request.call_args.kwargs.get("callback")
            if cb:
                cb("0", None, Exception("API error"))

        batch_mock = MagicMock()
        batch_mock.execute.side_effect = fake_execute_with_error
        service.new_batch_http_request.return_value = batch_mock

        with pytest.raises(ExceptionGroup):
            client_empty_cache.complete_tasks("list1", self.SAMPLE_TASKS)

        assert tasks_cache.get("list1") is None

    def test_delete_tasks_THEN_invalidates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)
        batch_mock = MagicMock()
        service.new_batch_http_request.return_value = batch_mock

        client_empty_cache.delete_tasks("list1", self.SAMPLE_TASKS)

        assert tasks_cache.get("list1") is None

    def test_delete_tasks_GIVEN_batch_error_THEN_still_invalidates_cache(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)

        def fake_execute_with_error():
            cb = service.new_batch_http_request.call_args.kwargs.get("callback")
            if cb:
                cb("0", None, Exception("API error"))

        batch_mock = MagicMock()
        batch_mock.execute.side_effect = fake_execute_with_error
        service.new_batch_http_request.return_value = batch_mock

        with pytest.raises(ExceptionGroup):
            client_empty_cache.delete_tasks("list1", self.SAMPLE_TASKS)

        assert tasks_cache.get("list1") is None


class TestCachedResolveTasklistId:
    def test_GIVEN_title_in_cache_THEN_returns_matching_dict(
        self, client_populated_cache: CachedApiClient
    ) -> None:
        assert client_populated_cache.resolve_tasklist_from_title("Work") == [
            {"title": "Work", "id": "list1"}
        ]

    def test_GIVEN_title_not_in_cache_THEN_returns_empty(
        self, client_populated_cache: CachedApiClient
    ) -> None:
        assert client_populated_cache.resolve_tasklist_from_title("Nonexistent") == []

    def test_GIVEN_empty_cache_THEN_fetches_then_resolves(
        self, client_empty_cache: CachedApiClient, service: MagicMock, empty_cache: BidictCache
    ) -> None:
        service.tasklists().list().execute.return_value = {
            "items": [{"id": "list1", "title": "Work"}]
        }

        with patch.object(empty_cache, "_save"):
            result = client_empty_cache.resolve_tasklist_from_title("Work")

        assert result == [{"title": "Work", "id": "list1"}]
        service.tasklists().list.assert_called()


class TestCachedResolveTaskFromTitle:
    SAMPLE_TASKS = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
        {"id": "task2", "title": "Walk dog", "status": "needsAction"},
    ]

    def test_GIVEN_matching_title_THEN_returns_task(
        self, client_empty_cache: CachedApiClient, service: MagicMock
    ) -> None:
        service.tasks().list().execute.return_value = {"items": self.SAMPLE_TASKS}

        result = client_empty_cache.resolve_task_from_title("Buy milk", "list1")

        assert result == [{"id": "task1", "title": "Buy milk", "status": "needsAction"}]

    def test_GIVEN_case_insensitive_title_THEN_returns_task(
        self, client_empty_cache: CachedApiClient, service: MagicMock
    ) -> None:
        service.tasks().list().execute.return_value = {"items": self.SAMPLE_TASKS}

        result = client_empty_cache.resolve_task_from_title("buy MILK", "list1")

        assert result == [{"id": "task1", "title": "Buy milk", "status": "needsAction"}]

    def test_GIVEN_no_match_THEN_returns_empty(
        self, client_empty_cache: CachedApiClient, service: MagicMock
    ) -> None:
        service.tasks().list().execute.return_value = {"items": self.SAMPLE_TASKS}

        assert client_empty_cache.resolve_task_from_title("Nonexistent", "list1") == []

    def test_GIVEN_cache_populated_THEN_resolves_without_api_call(
        self, client_empty_cache: CachedApiClient, service: MagicMock, tasks_cache: TasksCache
    ) -> None:
        tasks_cache.set("list1", self.SAMPLE_TASKS)

        result = client_empty_cache.resolve_task_from_title("Buy milk", "list1")

        service.tasks().list.assert_not_called()
        assert result == [{"id": "task1", "title": "Buy milk", "status": "needsAction"}]
