from unittest.mock import Mock

import pytest
from pytest import CaptureFixture

from gtasks.cli.task_resolution import resolve_tasks_from_inputs


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

    def test_GIVEN_out_of_range_index_THEN_skips_and_prints_error(
        self, mock_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        result = resolve_tasks_from_inputs(["99"], mock_client, "list1")

        assert result == []
        assert "out of range" in capsys.readouterr().out

    def test_GIVEN_mixed_index_and_title_THEN_resolves_both(
        self, mock_client: Mock
    ) -> None:
        mock_client.resolve_task_from_title.return_value = [self.SAMPLE_TASKS[2]]

        result = resolve_tasks_from_inputs(["1", "Call dentist"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0], self.SAMPLE_TASKS[2]]

    def test_GIVEN_unresolvable_title_THEN_skips(
        self, mock_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.resolve_task_from_title.return_value = []

        result = resolve_tasks_from_inputs(["Nonexistent"], mock_client, "list1")

        assert result == []
