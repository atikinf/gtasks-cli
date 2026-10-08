import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gtasks.client.cache_store import DEFAULT_TTL_SECONDS, CacheStore
from gtasks.client.caching_client import CachingClient
from gtasks.client.protocol import CacheState, Status

T0 = 1_000_000.0
LISTS = [{"id": "l1", "title": "Work"}, {"id": "l2", "title": "Home"}]
OPEN = [
    {"id": "t1", "title": "Buy milk", "status": "needsAction"},
    {"id": "t2", "title": "Eggs", "status": "needsAction"},
]


class Clock:
    def __init__(self) -> None:
        self.t = T0

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(tmp_path: Path, clock: Clock) -> CacheStore:
    return CacheStore(tmp_path / "cache", "acct", now=clock)


@pytest.fixture
def inner() -> MagicMock:
    inner = MagicMock()
    inner.get_tasklists.return_value = LISTS
    inner.get_tasks.return_value = OPEN
    return inner


@pytest.fixture
def refresher() -> MagicMock:
    """The second client used for concurrent refetches."""
    refresher = MagicMock()
    refresher.get_tasks.return_value = OPEN
    return refresher


@pytest.fixture
def client(inner: MagicMock, store: CacheStore, refresher: MagicMock) -> CachingClient:
    return CachingClient(store, make_inner=lambda: inner, make_refresher=lambda: refresher)


def _cached(store: CacheStore, tasklist_id: str = "l1") -> list | None:
    cached = store.read_tasks(tasklist_id)
    return None if cached is None else [t["id"] for t in cached[0]]


class TestTasklistReads:
    def test_get_tasklists_GIVEN_second_call_THEN_served_from_cache(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        client.get_tasklists()
        result = CachingClient(store, make_inner=lambda: inner).get_tasklists()

        assert result == LISTS
        inner.get_tasklists.assert_called_once_with()

    def test_get_tasklists_GIVEN_limit_on_miss_THEN_fetches_all_and_slices(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        assert client.get_tasklists(1) == LISTS[:1]
        inner.get_tasklists.assert_called_once_with()
        assert store.read_tasklists() == (LISTS, T0)  # never a partial copy

    def test_get_tasklists_GIVEN_expired_THEN_refetches(
        self, client: CachingClient, inner: MagicMock, clock: Clock
    ) -> None:
        client.get_tasklists()
        clock.t += DEFAULT_TTL_SECONDS

        client.get_tasklists()

        assert inner.get_tasklists.call_count == 2

    def test_tasklists_cache_state_GIVEN_live_then_hit_then_fresh_THEN_added_cached_added(
        self, client: CachingClient, inner: MagicMock, store: CacheStore, clock: Clock
    ) -> None:
        client.get_tasklists()
        assert client.tasklists_cache_state() == CacheState(from_cache=False, fetched_at=T0)

        clock.t += 600
        later = CachingClient(store, make_inner=lambda: inner)
        later.get_tasklists()
        assert later.tasklists_cache_state() == CacheState(from_cache=True, fetched_at=T0)

        fresh = CachingClient(store, make_inner=lambda: inner, fresh=True)
        fresh.get_tasklists()
        assert fresh.tasklists_cache_state() == CacheState(from_cache=False, fetched_at=T0 + 600)

    def test_tasklists_cache_state_GIVEN_live_data_not_saved_THEN_none(
        self, inner: MagicMock, store: CacheStore
    ) -> None:
        """Never claim "cache refreshed" when the save failed."""
        with patch.object(CacheStore, "write_tasklists", return_value=None):
            client = CachingClient(store, make_inner=lambda: inner)
            client.get_tasklists()

        assert client.tasklists_cache_state() is None

    def test_get_tasklist_GIVEN_id_in_cached_lists_THEN_no_api_call(
        self, client: CachingClient, inner: MagicMock
    ) -> None:
        client.get_tasklists()

        assert client.get_tasklist("l2") == LISTS[1]
        inner.get_tasklist.assert_not_called()

    def test_get_tasklist_GIVEN_default_alias_THEN_resolved_once_then_cached(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        """Even when the full set of lists was never fetched (bare `gtasks`, no active list)."""
        inner.get_tasklist.return_value = LISTS[0]

        first = client.get_tasklist("@default")
        second = CachingClient(store, make_inner=lambda: inner).get_tasklist("@default")

        assert first == second == LISTS[0]
        inner.get_tasklist.assert_called_once_with("@default")

    def test_get_tasklist_GIVEN_unknown_id_THEN_passes_through_and_errors_not_cached(
        self, client: CachingClient, inner: MagicMock
    ) -> None:
        inner.get_tasklist.side_effect = RuntimeError("404")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                client.get_tasklist("missing")

        assert inner.get_tasklist.call_count == 2


class TestTaskReads:
    def test_get_tasks_GIVEN_cli_query_twice_THEN_second_from_cache(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        client.get_tasks("l1", show_completed=False)
        result = CachingClient(
            store,
            make_inner=lambda: inner,
        ).get_tasks("l1", show_completed=False)

        assert result == OPEN
        inner.get_tasks.assert_called_once_with("l1", show_completed=False)

    def test_get_tasks_GIVEN_limit_on_miss_THEN_fetches_all_and_slices(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        assert client.get_tasks("l1", 1, show_completed=False) == OPEN[:1]
        inner.get_tasks.assert_called_once_with("l1", show_completed=False)
        assert _cached(store) == ["t1", "t2"]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},  # show_completed defaults to True
            {"show_completed": False, "show_hidden": True},
            {"show_completed": False, "due_max": "2026-01-01T00:00:00Z"},
        ],
        ids=["completed-included", "hidden", "due-filter"],
    )
    def test_get_tasks_GIVEN_other_filters_THEN_always_passes_through_uncached(
        self, client: CachingClient, inner: MagicMock, store: CacheStore, kwargs: dict
    ) -> None:
        client.get_tasks("l1", **kwargs)
        client.get_tasks("l1", **kwargs)

        assert inner.get_tasks.call_count == 2
        assert store.read_tasks("l1") is None

    def test_get_tasks_GIVEN_default_alias_THEN_uncached(
        self, client: CachingClient, inner: MagicMock
    ) -> None:
        client.get_tasks("@default", show_completed=False)
        client.get_tasks("@default", show_completed=False)

        assert inner.get_tasks.call_count == 2

    def test_tasks_cache_state_GIVEN_live_then_hit_THEN_added_then_cached(
        self, client: CachingClient, inner: MagicMock, store: CacheStore, clock: Clock
    ) -> None:
        client.get_tasks("l1", show_completed=False)
        assert client.tasks_cache_state("l1") == CacheState(from_cache=False, fetched_at=T0)

        clock.t += 600
        later = CachingClient(store, make_inner=lambda: inner)
        later.get_tasks("l1", show_completed=False)

        assert later.tasks_cache_state("l1") == CacheState(from_cache=True, fetched_at=T0)

    def test_tasks_cache_state_GIVEN_live_data_not_saved_THEN_none(
        self, inner: MagicMock, store: CacheStore
    ) -> None:
        with patch.object(CacheStore, "write_tasks", return_value=None):
            client = CachingClient(store, make_inner=lambda: inner)
            client.get_tasks("l1", show_completed=False)

        assert client.tasks_cache_state("l1") is None

    def test_tasks_cache_state_GIVEN_list_never_read_THEN_none(self, client: CachingClient) -> None:
        assert client.tasks_cache_state("l1") is None

    def test_get_task_THEN_always_passes_through(
        self, client: CachingClient, inner: MagicMock
    ) -> None:
        client.get_task("l1", "t1")
        client.get_task("l1", "t1")

        assert inner.get_task.call_count == 2


class TestFreshMode:
    def test_fresh_GIVEN_cached_data_THEN_refetches_and_stores(
        self, inner: MagicMock, store: CacheStore, clock: Clock
    ) -> None:
        CachingClient(store, make_inner=lambda: inner).get_tasks("l1", show_completed=False)
        inner.get_tasks.return_value = OPEN[:1]
        clock.t += 60

        result = CachingClient(
            store,
            make_inner=lambda: inner,
            fresh=True,
        ).get_tasks("l1", show_completed=False)

        assert result == OPEN[:1]
        assert store.read_tasks("l1") == (OPEN[:1], T0 + 60)

    def test_fresh_GIVEN_cached_lists_THEN_refetches_lists_too(
        self, inner: MagicMock, store: CacheStore
    ) -> None:
        CachingClient(store, make_inner=lambda: inner).get_tasklists()
        CachingClient(store, make_inner=lambda: inner, fresh=True).get_tasklists()

        assert inner.get_tasklists.call_count == 2


class TestTaskWrites:
    def test_complete_GIVEN_list_fetched_this_run_THEN_merges_without_refetch(
        self, client: CachingClient, inner: MagicMock, refresher: MagicMock, store: CacheStore
    ) -> None:
        client.get_tasks("l1", show_completed=False)

        client.complete_tasks("l1", ["t1"])

        refresher.get_tasks.assert_not_called()
        assert _cached(store) == ["t2"]

    @pytest.mark.parametrize(
        "refetched", [OPEN, OPEN[1:]], ids=["refetch-before-write", "refetch-after-write"]
    )
    def test_complete_GIVEN_not_fetched_this_run_THEN_refetches_and_removes(
        self, client: CachingClient, refresher: MagicMock, store: CacheStore, refetched: list
    ) -> None:
        refresher.get_tasks.return_value = refetched

        client.complete_tasks("l1", ["t1"])

        refresher.get_tasks.assert_called_once_with("l1", show_completed=False)
        assert _cached(store) == ["t2"]

    @pytest.mark.parametrize(
        "refetched", [OPEN, [{"id": "new"}, *OPEN]], ids=["before-insert", "after-insert"]
    )
    def test_add_GIVEN_refetch_before_or_after_insert_THEN_new_task_on_top_once(
        self, client: CachingClient, inner: MagicMock, refresher: MagicMock,
        store: CacheStore, refetched: list,
    ) -> None:
        refresher.get_tasks.return_value = refetched
        inner.add_task.return_value = {"id": "new", "title": "New"}

        client.add_task("l1", "New")

        assert _cached(store) == ["new", "t1", "t2"]

    def test_add_GIVEN_explicit_position_THEN_drops_cached_list(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        client.get_tasks("l1", show_completed=False)
        inner.add_task.return_value = {"id": "new"}

        client.add_task("l1", "Sub", parent_task_id="t1")

        assert store.read_tasks("l1") is None

    def test_delete_GIVEN_parent_THEN_cached_subtasks_removed_too(
        self, client: CachingClient, refresher: MagicMock, store: CacheStore
    ) -> None:
        refresher.get_tasks.return_value = [
            {"id": "p"}, {"id": "c", "parent": "p"}, {"id": "gc", "parent": "c"}, {"id": "x"},
        ]

        client.delete_tasks("l1", ["p"])

        assert _cached(store) == ["x"]

    TREE = [{"id": "p"}, {"id": "c", "parent": "p"}, {"id": "gc", "parent": "c"}, {"id": "x"}]

    def test_complete_GIVEN_parent_THEN_cached_subtasks_removed_too(
        self, client: CachingClient, refresher: MagicMock, store: CacheStore
    ) -> None:
        refresher.get_tasks.return_value = self.TREE

        client.complete_tasks("l1", ["p"])

        assert _cached(store) == ["x"]

    def test_complete_GIVEN_parent_and_list_fetched_this_run_THEN_subtasks_removed(
        self, client: CachingClient, inner: MagicMock, refresher: MagicMock, store: CacheStore
    ) -> None:
        inner.get_tasks.return_value = self.TREE
        client.get_tasks("l1", show_completed=False)

        client.complete_tasks("l1", ["p"])

        refresher.get_tasks.assert_not_called()
        assert _cached(store) == ["x"]

    def test_complete_GIVEN_subtask_THEN_parent_and_others_stay(
        self, client: CachingClient, refresher: MagicMock, store: CacheStore
    ) -> None:
        refresher.get_tasks.return_value = self.TREE

        client.complete_tasks("l1", ["c"])

        assert _cached(store) == ["p", "x"]

    def test_update_GIVEN_parent_completed_THEN_cached_subtasks_removed_too(
        self, client: CachingClient, inner: MagicMock, refresher: MagicMock, store: CacheStore
    ) -> None:
        refresher.get_tasks.return_value = self.TREE
        inner.update_task.return_value = {"id": "p", "status": Status.COMPLETED.value}

        client.update_task("l1", "p", status=Status.COMPLETED)

        assert _cached(store) == ["x"]

    @pytest.mark.parametrize(
        "returned, expected",
        [
            ({"id": "t1", "title": "Oat milk", "status": "needsAction"}, ["t1", "t2"]),
            ({"id": "t1", "status": Status.COMPLETED.value}, ["t2"]),
        ],
        ids=["edited", "completed"],
    )
    def test_update_GIVEN_result_THEN_merged(
        self, client: CachingClient, inner: MagicMock, store: CacheStore,
        returned: dict, expected: list,
    ) -> None:
        inner.update_task.return_value = returned

        client.update_task("l1", "t1", task_title="Oat milk")

        assert _cached(store) == expected

    def test_update_GIVEN_task_not_in_open_list_THEN_drops(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        inner.update_task.return_value = {"id": "reopened", "status": "needsAction"}

        client.update_task("l1", "reopened", status=Status.NEEDS_ACTION)

        assert store.read_tasks("l1") is None

    def test_write_GIVEN_mutation_fails_THEN_drops_and_reraises_unchanged(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        client.get_tasks("l1", show_completed=False)
        error = ExceptionGroup("batch complete_tasks failed", [RuntimeError("500")])
        inner.complete_tasks.side_effect = error

        with pytest.raises(ExceptionGroup) as exc:
            client.complete_tasks("l1", ["t1", "t2"])

        assert exc.value is error
        assert store.read_tasks("l1") is None

    def test_write_GIVEN_refetch_fails_THEN_write_succeeds_and_cache_dropped(
        self, client: CachingClient, inner: MagicMock, refresher: MagicMock, store: CacheStore
    ) -> None:
        store.write_tasks("l1", OPEN)
        refresher.get_tasks.side_effect = RuntimeError("network down")
        inner.complete_tasks.return_value = [OPEN[0]]

        assert client.complete_tasks("l1", ["t1"]) == [OPEN[0]]
        assert store.read_tasks("l1") is None

    def test_write_GIVEN_no_refresher_THEN_patches_cache_keeping_its_age(
        self, inner: MagicMock, store: CacheStore, clock: Clock
    ) -> None:
        store.write_tasks("l1", OPEN)
        clock.t += 600

        CachingClient(store, make_inner=lambda: inner).complete_tasks("l1", ["t1"])

        assert store.read_tasks("l1") == ([OPEN[1]], T0)

    def test_write_THEN_refetch_runs_while_mutation_runs(
        self, inner: MagicMock, refresher: MagicMock, store: CacheStore
    ) -> None:
        """The refetch must overlap the write, not follow it: both must be in flight at once."""
        both_running = threading.Barrier(2, timeout=5)

        def refetch(*args, **kwargs):
            both_running.wait()
            return OPEN

        def complete(*args, **kwargs):
            both_running.wait()
            return [OPEN[0]]

        refresher.get_tasks.side_effect = refetch
        inner.complete_tasks.side_effect = complete

        CachingClient(
            store,
            make_inner=lambda: inner,
            make_refresher=lambda: refresher,
        ).complete_tasks("l1", ["t1"])

        assert _cached(store) == ["t2"]

    def test_write_THEN_main_client_built_on_main_thread_before_refetch_starts(
        self, inner: MagicMock, refresher: MagicMock, store: CacheStore
    ) -> None:
        """Building the main client loads credentials; doing that before the refetch thread
        exists means the two can never race to load or refresh them."""
        events: list[tuple[str, str]] = []

        def make_inner() -> MagicMock:
            events.append(("inner", threading.current_thread().name))
            return inner

        def make_refresher() -> MagicMock:
            events.append(("refresher", threading.current_thread().name))
            return refresher

        CachingClient(store, make_inner=make_inner, make_refresher=make_refresher).delete_tasks(
            "l1", ["t1"]
        )

        assert events[0] == ("inner", threading.main_thread().name)
        assert [name for name, _ in events] == ["inner", "refresher"]

    def test_reads_GIVEN_cache_hit_THEN_main_client_never_built(
        self, inner: MagicMock, store: CacheStore
    ) -> None:
        store.write_tasklists(LISTS)
        store.write_tasks("l1", OPEN)
        make_inner = MagicMock(return_value=inner)
        client = CachingClient(store, make_inner=make_inner)

        client.get_tasklists()
        client.get_tasks("l1", show_completed=False)

        make_inner.assert_not_called()

    def test_write_THEN_refetch_uses_its_own_client(
        self, inner: MagicMock, refresher: MagicMock, store: CacheStore
    ) -> None:
        CachingClient(
            store,
            make_inner=lambda: inner,
            make_refresher=lambda: refresher,
        ).delete_tasks("l1", ["t1"])

        inner.get_tasks.assert_not_called()  # the main client is never shared across threads
        refresher.get_tasks.assert_called_once()

    @pytest.mark.parametrize(
        "call",
        [
            lambda c: c.reopen_tasks("l1", ["t1"]),
            lambda c: c.clear_completed_tasks("l1"),
            lambda c: c.move_task("l1", "t1"),
        ],
        ids=["reopen", "clear-completed", "move"],
    )
    def test_other_writes_THEN_drop_cached_list(
        self, client: CachingClient, store: CacheStore, call
    ) -> None:
        store.write_tasks("l1", OPEN)

        call(client)

        assert store.read_tasks("l1") is None

    def test_move_GIVEN_destination_THEN_both_lists_dropped(
        self, client: CachingClient, store: CacheStore
    ) -> None:
        store.write_tasks("l1", OPEN)
        store.write_tasks("l2", OPEN)

        client.move_task("l1", "t1", destination_tasklist_id="l2")

        assert store.read_tasks("l1") is None
        assert store.read_tasks("l2") is None


class TestTasklistWrites:
    @pytest.mark.parametrize(
        "call",
        [
            lambda c: c.add_tasklist("New"),
            lambda c: c.update_tasklist("l1", "Renamed"),
            lambda c: c.delete_tasklist("l1"),
        ],
        ids=["add", "rename", "delete"],
    )
    def test_tasklist_writes_THEN_drop_lists_and_default(
        self, client: CachingClient, store: CacheStore, call
    ) -> None:
        store.write_tasklists(LISTS)
        store.write_default(LISTS[0])

        call(client)

        assert store.read_tasklists() is None
        assert store.read_default() is None

    def test_delete_tasklist_THEN_its_tasks_dropped(
        self, client: CachingClient, store: CacheStore
    ) -> None:
        store.write_tasks("l1", OPEN)

        client.delete_tasklist("l1")

        assert store.read_tasks("l1") is None

    def test_tasklist_write_GIVEN_failure_THEN_still_drops(
        self, client: CachingClient, inner: MagicMock, store: CacheStore
    ) -> None:
        store.write_tasklists(LISTS)
        inner.update_tasklist.side_effect = RuntimeError("500")

        with pytest.raises(RuntimeError):
            client.update_tasklist("l1", "Renamed")

        assert store.read_tasklists() is None
