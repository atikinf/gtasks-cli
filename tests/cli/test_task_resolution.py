from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from gtasks.cli.errors import CliError
from gtasks.cli.task_resolution import resolve_tasks_from_inputs
from gtasks.utils.listing_state import ListingState


class TestResolveTasksFromInputs:
    SAMPLE_TASKS = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
        {"id": "task2", "title": "Walk dog", "status": "needsAction"},
        {"id": "task3", "title": "Call dentist", "status": "needsAction"},
    ]

    @pytest.fixture
    def mock_client(self) -> Mock:
        client = Mock()
        client.get_tasks.return_value = self.SAMPLE_TASKS
        return client

    def test_GIVEN_single_index_THEN_resolves_to_task_object(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["1"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0]]
        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)

    def test_GIVEN_multiple_indices_THEN_resolves_all(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["1", "3"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0], self.SAMPLE_TASKS[2]]

    def test_GIVEN_title_input_THEN_does_not_fetch_all_tasks(
        self, mock_client: Mock
    ) -> None:
        mock_client.resolve_task_from_title.return_value = [self.SAMPLE_TASKS[1]]

        resolve_tasks_from_inputs(["Walk dog"], mock_client, "list1")

        mock_client.get_tasks.assert_not_called()

    def test_GIVEN_title_input_THEN_returns_task_object(
        self, mock_client: Mock
    ) -> None:
        mock_client.resolve_task_from_title.return_value = [self.SAMPLE_TASKS[1]]

        result = resolve_tasks_from_inputs(["Walk dog"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[1]]
        mock_client.resolve_task_from_title.assert_called_once_with("Walk dog", "list1")

    def test_GIVEN_out_of_range_index_THEN_raises(self, mock_client: Mock) -> None:
        with pytest.raises(CliError, match="no task #99"):
            resolve_tasks_from_inputs(["99"], mock_client, "list1")

    def test_GIVEN_mixed_index_and_title_THEN_resolves_both(
        self, mock_client: Mock
    ) -> None:
        mock_client.resolve_task_from_title.return_value = [self.SAMPLE_TASKS[2]]

        result = resolve_tasks_from_inputs(["1", "Call dentist"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0], self.SAMPLE_TASKS[2]]

    def test_GIVEN_unresolvable_title_THEN_raises(self, mock_client: Mock) -> None:
        mock_client.resolve_task_from_title.return_value = []

        with pytest.raises(CliError, match="No task named 'Nonexistent'"):
            resolve_tasks_from_inputs(["Nonexistent"], mock_client, "list1")

    def test_GIVEN_bad_input_after_good_one_THEN_raises_before_returning_any(
        self, mock_client: Mock
    ) -> None:
        with pytest.raises(CliError):
            resolve_tasks_from_inputs(["1", "99"], mock_client, "list1")

    def test_GIVEN_same_task_twice_THEN_returned_once(self, mock_client: Mock) -> None:
        mock_client.resolve_task_from_title.return_value = [self.SAMPLE_TASKS[0]]

        result = resolve_tasks_from_inputs(["1", "Buy milk", "1"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0]]

    def test_GIVEN_duplicate_titles_THEN_prompts(self, mock_client: Mock) -> None:
        dupes = [{"id": "a", "title": "Same"}, {"id": "b", "title": "Same"}]
        mock_client.resolve_task_from_title.return_value = dupes

        with patch("builtins.input", return_value="2"):
            result = resolve_tasks_from_inputs(["Same"], mock_client, "list1")

        assert result == [dupes[1]]


class TestResolveAgainstLastListing:
    """Numbers resolve against what the user was last shown, not the current list."""

    SHOWN = [{"id": "task1", "title": "Buy milk"}, {"id": "task2", "title": "Walk dog"}]

    @pytest.fixture
    def listing(self, tmp_path: Path) -> ListingState:
        listing = ListingState(tmp_path / "state.json")
        listing.save("list1", self.SHOWN)
        return listing

    def test_GIVEN_listing_for_list_THEN_uses_it_without_fetching(
        self, listing: ListingState
    ) -> None:
        client = Mock()

        result = resolve_tasks_from_inputs(["2"], client, "list1", listing)

        assert result == [self.SHOWN[1]]
        client.get_tasks.assert_not_called()

    def test_GIVEN_listing_for_other_list_THEN_falls_back_to_fetch(
        self, listing: ListingState
    ) -> None:
        client = Mock()
        client.get_tasks.return_value = [{"id": "x", "title": "Other"}]

        result = resolve_tasks_from_inputs(["1"], client, "list2", listing)

        assert result == [{"id": "x", "title": "Other"}]

    def test_GIVEN_index_past_listing_THEN_raises_with_count(
        self, listing: ListingState
    ) -> None:
        with pytest.raises(CliError, match="showed 2"):
            resolve_tasks_from_inputs(["3"], Mock(), "list1", listing)

    def test_GIVEN_consumed_row_THEN_raises_already_done(self, listing: ListingState) -> None:
        listing.consume("list1", ["task1"])

        with pytest.raises(CliError, match="already completed or deleted"):
            resolve_tasks_from_inputs(["1"], Mock(), "list1", listing)
