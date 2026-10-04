import json
from pathlib import Path

import pytest

from gtasks import defaults
from gtasks.client.cache_store import clear_cache
from gtasks.utils.listing_state import LISTING_FILE_NAME, SCHEMA_VERSION, ListingState

TASKS = [
    {"id": "t1", "title": "Buy milk"},
    {"id": "t2", "title": "Eggs"},
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "cache"


@pytest.fixture
def state(root: Path) -> ListingState:
    return ListingState(root)


class TestListingState:
    def test_rows_GIVEN_nothing_saved_THEN_none(self, state: ListingState) -> None:
        assert state.rows("list1") is None

    def test_rows_GIVEN_saved_for_same_list_THEN_returns_id_and_title(
        self, state: ListingState
    ) -> None:
        state.save("list1", TASKS)

        assert state.rows("list1") == TASKS

    def test_rows_GIVEN_saved_for_other_list_THEN_none(self, state: ListingState) -> None:
        state.save("list1", TASKS)

        assert state.rows("list2") is None

    def test_consume_GIVEN_task_ids_THEN_rows_become_none_in_place(
        self, state: ListingState
    ) -> None:
        state.save("list1", TASKS)

        state.consume("list1", ["t1"])

        assert state.rows("list1") == [None, TASKS[1]]

    def test_consume_GIVEN_other_list_THEN_no_change(self, state: ListingState) -> None:
        state.save("list1", TASKS)

        state.consume("list2", ["t1"])

        assert state.rows("list1") == TASKS


class TestLocation:
    def test_default_THEN_lives_in_cache_dir(self) -> None:
        ListingState.default().save("list1", TASKS)

        assert (defaults.CACHE_DIR / LISTING_FILE_NAME).exists()

    def test_clear_cache_THEN_listing_cleared_too(self) -> None:
        ListingState.default().save("list1", TASKS)

        clear_cache(defaults.CACHE_DIR)

        assert ListingState.default().rows("list1") is None


class TestFileConventions:
    """Listing-specific checks; the shared conventions are tested in test_json_files.py."""

    def test_save_THEN_schema_versioned(self, state: ListingState, root: Path) -> None:
        state.save("list1", TASKS)

        assert json.loads((root / LISTING_FILE_NAME).read_text())["schema"] == SCHEMA_VERSION

    @pytest.mark.parametrize(
        "content",
        [
            json.dumps({"schema": SCHEMA_VERSION, "tasklist_id": "list1", "rows": "nope"}),
            json.dumps(
                {"schema": SCHEMA_VERSION, "tasklist_id": "list1", "rows": [{"title": "x"}]}
            ),
        ],
        ids=["rows-not-list", "row-without-id"],
    )
    def test_rows_and_consume_GIVEN_corrupt_file_THEN_treated_as_no_listing(
        self, state: ListingState, root: Path, content: str
    ) -> None:
        root.mkdir(parents=True)
        (root / LISTING_FILE_NAME).write_text(content)

        state.consume("list1", ["t1"])  # must not raise

        assert state.rows("list1") is None

    def test_save_GIVEN_unwritable_location_THEN_silently_skipped(self, tmp_path: Path) -> None:
        blocked = tmp_path / "blocked"
        blocked.write_text("a file where the folder should be")

        ListingState(blocked).save("list1", TASKS)  # must not raise

        assert ListingState(blocked).rows("list1") is None
