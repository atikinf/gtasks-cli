import json
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from gtasks.client.cache_store import (
    DEFAULT_TTL_SECONDS,
    SCHEMA_VERSION,
    CacheStore,
    account_key,
    clear_cache,
)

T0 = 1_000_000.0
TASKS = [{"id": "t1", "title": "Buy milk"}, {"id": "t2", "title": "Eggs"}]


class Clock:
    def __init__(self, t: float = T0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def store(root: Path, clock: Clock) -> CacheStore:
    return CacheStore(root, "acct", now=clock)


def _only_tasks_file(root: Path) -> Path:
    (path,) = (root / "acct" / "lists").glob("*.json")
    return path


class TestTasks:
    def test_read_tasks_GIVEN_nothing_written_THEN_none(self, store: CacheStore) -> None:
        assert store.read_tasks("list1") is None

    def test_read_tasks_GIVEN_written_THEN_returns_tasks_and_fetch_time(
        self, store: CacheStore
    ) -> None:
        store.write_tasks("list1", TASKS)

        assert store.read_tasks("list1") == (TASKS, T0)

    def test_read_tasks_GIVEN_other_list_written_THEN_none(self, store: CacheStore) -> None:
        store.write_tasks("list1", TASKS)

        assert store.read_tasks("list2") is None

    @pytest.mark.parametrize(
        "age, fresh",
        [(0, True), (DEFAULT_TTL_SECONDS - 1, True), (DEFAULT_TTL_SECONDS, False)],
        ids=["just-fetched", "just-under-ttl", "exactly-ttl"],
    )
    def test_read_tasks_GIVEN_age_THEN_fresh_only_within_ttl(
        self, store: CacheStore, clock: Clock, age: float, fresh: bool
    ) -> None:
        store.write_tasks("list1", TASKS)
        clock.t += age

        assert (store.read_tasks("list1") is not None) is fresh

    @pytest.mark.parametrize(
        "ahead, fresh", [(30, True), (61, False)], ids=["small-skew", "far-future"]
    )
    def test_read_tasks_GIVEN_fetch_time_in_future_THEN_only_small_skew_trusted(
        self, store: CacheStore, clock: Clock, ahead: float, fresh: bool
    ) -> None:
        store.write_tasks("list1", TASKS)
        clock.t -= ahead  # equivalent to the file's timestamp being in the future

        assert (store.read_tasks("list1") is not None) is fresh

    def test_update_tasks_THEN_applies_change_and_keeps_fetch_time(
        self, store: CacheStore, clock: Clock
    ) -> None:
        store.write_tasks("list1", TASKS)
        clock.t += 600

        store.update_tasks("list1", lambda tasks: tasks[1:])

        assert store.read_tasks("list1") == (TASKS[1:], T0)

    def test_update_tasks_GIVEN_frequent_edits_THEN_still_expires_at_ttl(
        self, store: CacheStore, clock: Clock
    ) -> None:
        store.write_tasks("list1", TASKS)
        for _ in range(3):
            clock.t += DEFAULT_TTL_SECONDS / 3
            store.update_tasks("list1", lambda tasks: tasks)

        assert store.read_tasks("list1") is None

    def test_update_tasks_GIVEN_change_cannot_apply_THEN_drops_cached_copy(
        self, store: CacheStore
    ) -> None:
        store.write_tasks("list1", TASKS)

        store.update_tasks("list1", lambda tasks: None)

        assert store.read_tasks("list1") is None

    def test_update_tasks_GIVEN_nothing_cached_THEN_writes_nothing(
        self, store: CacheStore, root: Path
    ) -> None:
        store.update_tasks("list1", lambda tasks: TASKS)

        assert store.read_tasks("list1") is None
        assert not root.exists()

    def test_drop_tasks_THEN_miss(self, store: CacheStore) -> None:
        store.write_tasks("list1", TASKS)

        store.drop_tasks("list1")

        assert store.read_tasks("list1") is None

    def test_write_tasks_GIVEN_id_with_slash_THEN_stored_under_hashed_name(
        self, store: CacheStore, root: Path
    ) -> None:
        store.write_tasks("ab/c+d==", TASKS)

        assert store.read_tasks("ab/c+d==") == (TASKS, T0)
        assert "/" not in _only_tasks_file(root).stem

    def test_read_tasks_GIVEN_file_for_different_id_THEN_none(
        self, store: CacheStore, root: Path
    ) -> None:
        """A hash collision (simulated by editing the stored ID) must never serve wrong data."""
        store.write_tasks("list1", TASKS)
        path = _only_tasks_file(root)
        path.write_text(path.read_text().replace('"list1"', '"other"'))

        assert store.read_tasks("list1") is None


class TestTasklists:
    def test_read_tasklists_GIVEN_written_THEN_returns_items(self, store: CacheStore) -> None:
        store.write_tasklists([{"id": "l1", "title": "Work"}])

        assert store.read_tasklists() == ([{"id": "l1", "title": "Work"}], T0)

    def test_default_GIVEN_written_alongside_lists_THEN_both_kept(
        self, store: CacheStore
    ) -> None:
        store.write_tasklists([{"id": "l1", "title": "Work"}])
        store.write_default({"id": "l1", "title": "Work"})

        assert store.read_default() == {"id": "l1", "title": "Work"}
        assert store.read_tasklists() == ([{"id": "l1", "title": "Work"}], T0)

    def test_default_GIVEN_stale_THEN_none_but_fresh_lists_still_served(
        self, store: CacheStore, clock: Clock
    ) -> None:
        store.write_default({"id": "l1"})
        clock.t += DEFAULT_TTL_SECONDS
        store.write_tasklists([{"id": "l1", "title": "Work"}])

        assert store.read_default() is None
        assert store.read_tasklists() is not None

    def test_default_GIVEN_entry_without_id_THEN_none(self, store: CacheStore) -> None:
        store.write_default({"title": "no id"})

        assert store.read_default() is None

    def test_drop_tasklists_THEN_lists_and_default_both_miss(self, store: CacheStore) -> None:
        store.write_tasklists([{"id": "l1"}])
        store.write_default({"id": "l1"})

        store.drop_tasklists()

        assert store.read_tasklists() is None
        assert store.read_default() is None


class TestSchema:
    @pytest.mark.parametrize(
        "version, readable",
        [
            (SCHEMA_VERSION, True),
            ("1.7.0", True),
            ("2.0.0", False),
            ("0.9.0", False),
            ("garbage", False),
            (None, False),
            (1, False),
        ],
        ids=["current", "newer-minor", "newer-major", "older-major", "malformed", "missing",
             "not-a-string"],
    )
    def test_read_GIVEN_schema_version_THEN_only_same_major_readable(
        self, store: CacheStore, root: Path, version: object, readable: bool
    ) -> None:
        store.write_tasks("list1", TASKS)
        path = _only_tasks_file(root)
        doc = json.loads(path.read_text())
        doc["schema"] = version
        doc["added_in_newer_minor"] = {"ignored": True}
        path.write_text(json.dumps(doc))

        assert (store.read_tasks("list1") is not None) is readable

    def test_write_GIVEN_incompatible_file_THEN_overwrites_with_current_schema(
        self, store: CacheStore, root: Path
    ) -> None:
        store.write_tasklists([{"id": "old"}])
        path = root / "acct" / "tasklists.json"
        path.write_text(json.dumps({"schema": "2.0.0", "lists": "new format"}))

        store.write_default({"id": "l1"})

        assert json.loads(path.read_text()) == {
            "schema": SCHEMA_VERSION,
            "default": {"fetched_at": T0, "item": {"id": "l1"}},
        }


class TestRobustness:
    @pytest.mark.parametrize(
        "content",
        [
            "{not json",
            "[]",
            json.dumps({"schema": SCHEMA_VERSION, "tasklist_id": "list1", "fetched_at": T0,
                        "tasks": "not a list"}),
            json.dumps({"schema": SCHEMA_VERSION, "tasklist_id": "list1", "fetched_at": T0,
                        "tasks": ["not a dict"]}),
            json.dumps({"schema": SCHEMA_VERSION, "tasklist_id": "list1", "fetched_at": "noon",
                        "tasks": []}),
            json.dumps({"schema": SCHEMA_VERSION, "tasklist_id": "list1", "fetched_at": True,
                        "tasks": []}),
        ],
        ids=["bad-json", "not-an-object", "tasks-not-list", "task-not-dict", "time-not-number",
             "time-is-bool"],
    )
    def test_read_tasks_GIVEN_corrupt_file_THEN_miss(
        self, store: CacheStore, root: Path, content: str
    ) -> None:
        store.write_tasks("list1", TASKS)
        _only_tasks_file(root).write_text(content)

        assert store.read_tasks("list1") is None

    def test_read_tasks_GIVEN_unreadable_file_THEN_miss(
        self, store: CacheStore, root: Path
    ) -> None:
        store.write_tasks("list1", TASKS)
        path = _only_tasks_file(root)
        path.unlink()
        path.mkdir()  # reading a directory raises IsADirectoryError, an OSError

        assert store.read_tasks("list1") is None

    def test_write_GIVEN_cache_path_blocked_by_a_file_THEN_silently_skipped(
        self, store: CacheStore, root: Path
    ) -> None:
        root.parent.mkdir(parents=True, exist_ok=True)
        root.write_text("not a directory")

        store.write_tasks("list1", TASKS)  # must not raise

        assert store.read_tasks("list1") is None

    def test_write_GIVEN_disk_full_THEN_silently_skipped(self, store: CacheStore) -> None:
        with patch(
            "gtasks.utils.json_files.tempfile.mkstemp", side_effect=OSError(28, "No space")
        ):
            store.write_tasks("list1", TASKS)  # must not raise

        assert store.read_tasks("list1") is None

    def test_write_GIVEN_failure_after_temp_file_created_THEN_temp_file_removed(
        self, store: CacheStore, root: Path
    ) -> None:
        with patch("gtasks.utils.json_files.os.replace", side_effect=OSError("boom")):
            store.write_tasks("list1", TASKS)

        assert list((root / "acct" / "lists").iterdir()) == []

    def test_write_THEN_leaves_no_temp_files(self, store: CacheStore, root: Path) -> None:
        store.write_tasks("list1", TASKS)
        store.write_tasks("list1", TASKS[:1])

        assert [p.name for p in (root / "acct" / "lists").iterdir()] == [
            _only_tasks_file(root).name
        ]

    def test_write_THEN_owner_only_permissions(self, store: CacheStore, root: Path) -> None:
        store.write_tasks("list1", TASKS)

        for directory in (root, root / "acct", root / "acct" / "lists"):
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE(_only_tasks_file(root).stat().st_mode) == 0o600


class TestAccounts:
    def test_account_key_GIVEN_different_sign_ins_THEN_different_keys(self) -> None:
        assert account_key("client", "token-a") != account_key("client", "token-b")
        assert account_key("client", "token-a") == account_key("client", "token-a")

    def test_account_key_THEN_does_not_contain_token(self) -> None:
        assert "secret" not in account_key("client", "secret")

    def test_stores_GIVEN_different_accounts_THEN_isolated(
        self, root: Path, clock: Clock
    ) -> None:
        CacheStore(root, "alice", now=clock).write_tasks("list1", TASKS)

        assert CacheStore(root, "bob", now=clock).read_tasks("list1") is None

    def test_write_THEN_records_current_account(self, root: Path, clock: Clock) -> None:
        CacheStore(root, "alice", now=clock).write_tasklists([])
        CacheStore(root, "bob", now=clock).write_tasklists([])

        assert (root / "current").read_text() == "bob"

    def test_clear_cache_THEN_every_account_removed(self, root: Path, clock: Clock) -> None:
        CacheStore(root, "alice", now=clock).write_tasks("list1", TASKS)
        bob = CacheStore(root, "bob", now=clock)
        bob.write_tasks("list1", TASKS)

        clear_cache(root)

        assert not root.exists()
