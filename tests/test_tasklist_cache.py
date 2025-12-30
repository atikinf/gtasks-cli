"""Unit tests for TaskListCache."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from gtasks.tasklist_cache import TaskListCache


class TestTaskListCacheInit:
    """Tests for TaskListCache initialization."""

    def test_init_creates_empty_cache_when_file_not_exists(
        self, tmp_path: Path
    ) -> None:
        cache_path = tmp_path / "cache.json"
        cache = TaskListCache(cache_path=cache_path)

        assert cache.is_empty()
        assert len(cache) == 0

    def test_init_loads_existing_cache(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        existing_data = {"id1": "Title One", "id2": "Title Two"}
        cache_path.write_text(json.dumps(existing_data), encoding="utf-8")

        cache = TaskListCache(cache_path=cache_path)

        assert len(cache) == 2
        assert cache.get_title("id1") == "Title One"
        assert cache.get_title("id2") == "Title Two"

    def test_init_handles_corrupted_json(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        cache_path.write_text("not valid json {{{", encoding="utf-8")

        cache = TaskListCache(cache_path=cache_path)

        assert cache.is_empty()

    def test_init_with_string_path(self, tmp_path: Path) -> None:
        cache_path = str(tmp_path / "cache.json")
        cache = TaskListCache(cache_path=cache_path)

        assert cache.is_empty()


class TestUpdateFromApiResponse:
    """Tests for update_from_api_response method."""

    def test_update_from_api_response_populates_cache(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        response = {
            "items": [
                {"id": "abc123", "title": "Work Tasks"},
                {"id": "def456", "title": "Personal"},
            ]
        }

        cache.update_from_api_response(response)

        assert len(cache) == 2
        assert cache.get_title("abc123") == "Work Tasks"
        assert cache.get_title("def456") == "Personal"

    def test_update_from_api_response_persists_to_disk(
        self, tmp_path: Path
    ) -> None:
        cache_path = tmp_path / "cache.json"
        cache = TaskListCache(cache_path=cache_path)
        response = {"items": [{"id": "id1", "title": "My List"}]}

        cache.update_from_api_response(response)

        # Verify file was written
        assert cache_path.exists()
        saved_data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert saved_data == {"id1": "My List"}

    def test_update_from_api_response_handles_empty_items(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        cache.update_from_api_response({"items": []})

        assert cache.is_empty()

    def test_update_from_api_response_handles_missing_items_key(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        cache.update_from_api_response({})

        assert cache.is_empty()

    def test_update_from_api_response_skips_items_without_id(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        response = {
            "items": [
                {"id": "valid_id", "title": "Valid"},
                {"title": "No ID"},  # Missing id
            ]
        }

        cache.update_from_api_response(response)

        assert len(cache) == 1
        assert cache.get_title("valid_id") == "Valid"

    def test_update_from_api_response_handles_missing_title(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        response = {"items": [{"id": "id1"}]}  # No title

        cache.update_from_api_response(response)

        assert cache.get_title("id1") == ""

    def test_update_from_api_response_merges_with_existing(
        self, tmp_path: Path
    ) -> None:
        cache_path = tmp_path / "cache.json"
        cache_path.write_text(
            json.dumps({"existing_id": "Existing Title"}),
            encoding="utf-8",
        )
        cache = TaskListCache(cache_path=cache_path)
        response = {"items": [{"id": "new_id", "title": "New Title"}]}

        cache.update_from_api_response(response)

        assert len(cache) == 2
        assert cache.get_title("existing_id") == "Existing Title"
        assert cache.get_title("new_id") == "New Title"


class TestUpdateFromItems:
    """Tests for update_from_items method."""

    def test_update_from_items_populates_cache(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        items = [
            {"id": "id1", "title": "List One"},
            {"id": "id2", "title": "List Two"},
        ]

        cache.update_from_items(items)

        assert len(cache) == 2
        assert cache.get_title("id1") == "List One"
        assert cache.get_title("id2") == "List Two"

    def test_update_from_items_persists_to_disk(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        cache = TaskListCache(cache_path=cache_path)

        cache.update_from_items([{"id": "id1", "title": "Title"}])

        assert cache_path.exists()
        saved_data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert saved_data == {"id1": "Title"}

    def test_update_from_items_handles_empty_list(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        cache.update_from_items([])

        assert cache.is_empty()


class TestGetTitle:
    """Tests for get_title method."""

    def test_get_title_returns_title_for_existing_id(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([{"id": "id1", "title": "My Title"}])

        result = cache.get_title("id1")

        assert result == "My Title"

    def test_get_title_returns_none_for_missing_id(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        result = cache.get_title("nonexistent")

        assert result is None


class TestGetId:
    """Tests for get_id method (title -> id lookup)."""

    def test_get_id_returns_id_for_existing_title(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([{"id": "abc123", "title": "Work Tasks"}])

        result = cache.get_id("Work Tasks")

        assert result == "abc123"

    def test_get_id_returns_none_for_missing_title(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        result = cache.get_id("Nonexistent")

        assert result is None

    def test_get_id_returns_last_match_for_duplicates(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        # When multiple items have the same title, the last one wins
        cache.update_from_items([
            {"id": "first_id", "title": "Same Title"},
            {"id": "second_id", "title": "Same Title"},
        ])

        result = cache.get_id("Same Title")

        assert result == "second_id"


class TestGetAll:
    """Tests for get_all method."""

    def test_get_all_returns_copy_of_cache(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([
            {"id": "id1", "title": "Title 1"},
            {"id": "id2", "title": "Title 2"},
        ])

        result = cache.get_all()

        assert result == {"id1": "Title 1", "id2": "Title 2"}

    def test_get_all_returns_independent_copy(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([{"id": "id1", "title": "Title 1"}])

        result = cache.get_all()
        result["id1"] = "Modified"

        # Original cache should be unchanged
        assert cache.get_title("id1") == "Title 1"

    def test_get_all_returns_empty_dict_when_empty(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        result = cache.get_all()

        assert result == {}


class TestClear:
    """Tests for clear method."""

    def test_clear_removes_all_entries(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([{"id": "id1", "title": "Title"}])

        cache.clear()

        assert cache.is_empty()
        assert len(cache) == 0

    def test_clear_deletes_cache_file(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        cache = TaskListCache(cache_path=cache_path)
        cache.update_from_items([{"id": "id1", "title": "Title"}])
        assert cache_path.exists()

        cache.clear()

        assert not cache_path.exists()

    def test_clear_handles_missing_file(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        cache = TaskListCache(cache_path=cache_path)

        # Should not raise even if file doesn't exist
        cache.clear()

        assert cache.is_empty()


class TestIsEmpty:
    """Tests for is_empty method."""

    def test_is_empty_returns_true_for_new_cache(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        assert cache.is_empty() is True

    def test_is_empty_returns_false_after_adding_items(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([{"id": "id1", "title": "Title"}])

        assert cache.is_empty() is False


class TestContains:
    """Tests for __contains__ method."""

    def test_contains_returns_true_for_existing_id(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([{"id": "id1", "title": "Title"}])

        assert "id1" in cache

    def test_contains_returns_false_for_missing_id(
        self, tmp_path: Path
    ) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        assert "nonexistent" not in cache


class TestLen:
    """Tests for __len__ method."""

    def test_len_returns_zero_for_empty_cache(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")

        assert len(cache) == 0

    def test_len_returns_correct_count(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([
            {"id": "id1", "title": "Title 1"},
            {"id": "id2", "title": "Title 2"},
            {"id": "id3", "title": "Title 3"},
        ])

        assert len(cache) == 3


class TestPersistence:
    """Tests for cache persistence across instances."""

    def test_cache_persists_across_instances(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"

        # First instance writes data
        cache1 = TaskListCache(cache_path=cache_path)
        cache1.update_from_items([{"id": "id1", "title": "Persisted Title"}])

        # Second instance should load the data
        cache2 = TaskListCache(cache_path=cache_path)

        assert cache2.get_title("id1") == "Persisted Title"

    def test_cache_creates_parent_directories(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "nested" / "dirs" / "cache.json"
        cache = TaskListCache(cache_path=cache_path)

        cache.update_from_items([{"id": "id1", "title": "Title"}])

        assert cache_path.exists()


class TestUnicodeSupport:
    """Tests for Unicode/international character support."""

    def test_handles_unicode_titles(self, tmp_path: Path) -> None:
        cache = TaskListCache(cache_path=tmp_path / "cache.json")
        cache.update_from_items([
            {"id": "id1", "title": "日本語タスク"},
            {"id": "id2", "title": "Tâches françaises"},
            {"id": "id3", "title": "Задачи"},
            {"id": "id4", "title": "📝 Tasks with emoji"},
        ])

        assert cache.get_title("id1") == "日本語タスク"
        assert cache.get_title("id2") == "Tâches françaises"
        assert cache.get_title("id3") == "Задачи"
        assert cache.get_title("id4") == "📝 Tasks with emoji"

    def test_unicode_persists_to_disk(self, tmp_path: Path) -> None:
        cache_path = tmp_path / "cache.json"
        cache = TaskListCache(cache_path=cache_path)
        cache.update_from_items([{"id": "id1", "title": "日本語"}])

        # Reload from disk
        cache2 = TaskListCache(cache_path=cache_path)

        assert cache2.get_title("id1") == "日本語"

