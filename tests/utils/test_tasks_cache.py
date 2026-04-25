import json
from pathlib import Path

import pytest

from gtasks.utils.tasks_cache import TasksCache


@pytest.fixture
def sample_tasks() -> list[dict]:
    return [
        {"id": "t1", "title": "Buy milk", "status": "needsAction"},
        {"id": "t2", "title": "Walk dog", "status": "completed"},
    ]


@pytest.fixture
def cache_dir(tmp_path: Path) -> Path:
    return tmp_path / "tasks"


@pytest.fixture
def cache(cache_dir: Path) -> TasksCache:
    return TasksCache(cache_dir)


class TestGet:
    def test_GIVEN_no_entry_THEN_returns_none(self, cache: TasksCache) -> None:
        assert cache.get("list1") is None

    def test_GIVEN_entry_set_THEN_returns_tasks(
        self, cache: TasksCache, sample_tasks: list[dict]
    ) -> None:
        cache.set("list1", sample_tasks)

        assert cache.get("list1") == sample_tasks


class TestSet:
    def test_GIVEN_tasks_THEN_persists_to_disk(
        self, cache: TasksCache, cache_dir: Path, sample_tasks: list[dict]
    ) -> None:
        cache.set("list1", sample_tasks)

        path = cache_dir / "list1.json"
        assert path.exists()
        assert json.loads(path.read_text()) == sample_tasks

    def test_GIVEN_existing_entry_THEN_overwrites(
        self, cache: TasksCache, sample_tasks: list[dict]
    ) -> None:
        cache.set("list1", sample_tasks)
        cache.set("list1", [])

        assert cache.get("list1") == []


class TestInvalidate:
    def test_GIVEN_existing_entry_THEN_removes_from_memory(
        self, cache: TasksCache, sample_tasks: list[dict]
    ) -> None:
        cache.set("list1", sample_tasks)
        cache.invalidate("list1")

        assert cache.get("list1") is None

    def test_GIVEN_existing_entry_THEN_deletes_file(
        self, cache: TasksCache, cache_dir: Path, sample_tasks: list[dict]
    ) -> None:
        cache.set("list1", sample_tasks)
        cache.invalidate("list1")

        assert not (cache_dir / "list1.json").exists()

    def test_GIVEN_missing_entry_THEN_no_error(self, cache: TasksCache) -> None:
        cache.invalidate("nonexistent")


class TestClear:
    def test_GIVEN_multiple_entries_THEN_clears_all_from_memory(
        self, cache: TasksCache, sample_tasks: list[dict]
    ) -> None:
        cache.set("list1", sample_tasks)
        cache.set("list2", sample_tasks)

        cache.clear()

        assert cache.get("list1") is None
        assert cache.get("list2") is None

    def test_GIVEN_multiple_entries_THEN_deletes_all_files(
        self, cache: TasksCache, cache_dir: Path, sample_tasks: list[dict]
    ) -> None:
        cache.set("list1", sample_tasks)
        cache.set("list2", sample_tasks)

        cache.clear()

        assert list(cache_dir.glob("*.json")) == []


class TestLoadOnStartup:
    def test_GIVEN_existing_cache_files_THEN_loads_on_init(
        self, cache_dir: Path, sample_tasks: list[dict]
    ) -> None:
        cache_dir.mkdir(parents=True)
        (cache_dir / "list1.json").write_text(json.dumps(sample_tasks))

        cache = TasksCache(cache_dir)

        assert cache.get("list1") == sample_tasks

    def test_GIVEN_corrupt_cache_file_THEN_ignores_and_deletes(
        self, cache_dir: Path
    ) -> None:
        cache_dir.mkdir(parents=True)
        (cache_dir / "list1.json").write_text("not valid json{{{")

        cache = TasksCache(cache_dir)

        assert cache.get("list1") is None
        assert not (cache_dir / "list1.json").exists()

    def test_GIVEN_no_cache_dir_THEN_starts_empty(self, tmp_path: Path) -> None:
        cache = TasksCache(tmp_path / "nonexistent")

        assert cache.get("list1") is None
