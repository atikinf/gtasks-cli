from unittest.mock import MagicMock, patch

import pytest

from gtasks.client.cached_api_client import CachedApiClient
from gtasks.utils.bidict_cache import BidictCache


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
def client_empty_cache(service: MagicMock, empty_cache: BidictCache) -> CachedApiClient:
    return CachedApiClient(service, empty_cache)


@pytest.fixture
def client_populated_cache(
    service: MagicMock, populated_cache: BidictCache
) -> CachedApiClient:
    return CachedApiClient(service, populated_cache)


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
