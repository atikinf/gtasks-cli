from configparser import ConfigParser
from pathlib import Path

import pytest

from gtasks.utils.config import Config
from gtasks.utils.listing_state import STATE_FILE_NAME, ListingState

TASKS = [
    {"id": "t1", "title": "Buy milk"},
    {"id": "t2", "title": "Eggs"},
]


@pytest.fixture
def state(tmp_path: Path) -> ListingState:
    return ListingState(tmp_path / STATE_FILE_NAME)


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

    def test_rows_GIVEN_corrupt_file_THEN_none(self, tmp_path: Path) -> None:
        path = tmp_path / STATE_FILE_NAME
        path.write_text("{not json")

        assert ListingState(path).rows("list1") is None

    def test_beside_GIVEN_config_THEN_lives_in_same_directory(self, tmp_path: Path) -> None:
        cfg = Config(tmp_path / "sub" / "config.toml", ConfigParser())

        ListingState.beside(cfg).save("list1", TASKS)

        assert (tmp_path / "sub" / STATE_FILE_NAME).exists()
