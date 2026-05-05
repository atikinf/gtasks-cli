import argparse
from unittest.mock import Mock, create_autospec

import pytest
from pytest import CaptureFixture

from gtasks.cli.cli_utils import (
    _STRIKETHROUGH,
    HINT,
    print_tasks,
    prompt_index_choice,
    resolve_tasks_from_inputs,
)


class TestPrintTasks:
    def test_print_tasks_GIVEN_completed_task_THEN_renders_strikethrough(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [{"id": "t1", "title": "Done task", "status": "completed"}]

        print_tasks(tasks, argparse.Namespace(show_ids=False))

        assert _STRIKETHROUGH in capsys.readouterr().out

    def test_print_tasks_GIVEN_needs_action_task_THEN_no_strikethrough(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [{"id": "t1", "title": "Pending task", "status": "needsAction"}]

        print_tasks(tasks, argparse.Namespace(show_ids=False))

        output = capsys.readouterr().out
        assert _STRIKETHROUGH not in output
        assert "Pending task" in output

    def test_print_tasks_GIVEN_no_status_field_THEN_no_strikethrough(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [{"id": "t1", "title": "Task"}]

        print_tasks(tasks, argparse.Namespace(show_ids=False))

        assert _STRIKETHROUGH not in capsys.readouterr().out

    def test_print_tasks_GIVEN_show_ids_THEN_includes_id_in_output(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [{"id": "t1", "title": "Task"}]

        print_tasks(tasks, argparse.Namespace(show_ids=True))

        assert "[t1]" in capsys.readouterr().out

    def test_print_tasks_GIVEN_completed_task_and_show_ids_THEN_strikethrough_and_id(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [{"id": "t1", "title": "Done", "status": "completed"}]

        print_tasks(tasks, argparse.Namespace(show_ids=True))

        output = capsys.readouterr().out
        assert "[t1]" in output
        assert _STRIKETHROUGH in output

    def test_print_tasks_GIVEN_notes_THEN_prints_notes(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [{"id": "t1", "title": "Task", "notes": "Some notes"}]

        print_tasks(tasks, argparse.Namespace(show_ids=False))

        assert "Some notes" in capsys.readouterr().out

    def test_print_tasks_GIVEN_due_date_THEN_prints_due(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [{"id": "t1", "title": "Task", "due": "2026-04-30T00:00:00.000Z"}]

        print_tasks(tasks, argparse.Namespace(show_ids=False))

        assert "Thursday, April 30th" in capsys.readouterr().out

    def test_print_tasks_GIVEN_multiple_tasks_THEN_all_printed(
        self, capsys: CaptureFixture[str]
    ) -> None:
        tasks = [
            {"id": "t1", "title": "First"},
            {"id": "t2", "title": "Second"},
        ]

        print_tasks(tasks, argparse.Namespace(show_ids=False))

        output = capsys.readouterr().out
        assert "First" in output
        assert "Second" in output


@pytest.fixture
def mock_input() -> Mock:
    return create_autospec(input, spec_set=True)


class TestPromptIndexChoice:
    def test_prompt_index_choice_GIVEN_one_option_THEN_returns_zero(
        self, mock_input: Mock
    ):
        result: int | None = prompt_index_choice(1, "Select: ", input_fn=mock_input)

        assert result == 0
        # Should not prompt the user if only one option
        assert mock_input.call_count == 0

    @pytest.mark.parametrize("ret_val", ["q", "Q"])
    def test_prompt_index_choice_GIVEN_quit_uppercase_THEN_returns_none(
        self, ret_val: str, mock_input: Mock
    ):
        mock_input.return_value = ret_val

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result is None

    def test_prompt_index_choice_GIVEN_invalid_then_quit_THEN_returns_none(
        self, mock_input: Mock, capsys: CaptureFixture[str]
    ):
        mock_input.side_effect = ["foo", "q"]

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result is None
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    @pytest.mark.parametrize("invalid", ["5", "0", "-1"])
    def test_prompt_index_choice_GIVEN_invalid_then_valid_THEN_retries(
        self, invalid: str, mock_input: Mock, capsys: CaptureFixture[str]
    ):
        mock_input.side_effect = [invalid, "2"]

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 1
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert HINT.format(num_options=3) in captured.out

    def test_prompt_index_choice_GIVEN_invalid_input_then_valid_THEN_retries(
        self, mock_input: Mock, capsys: CaptureFixture[str]
    ):
        mock_input.side_effect = ["abc", "1"]

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 0
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    def test_prompt_index_choice_GIVEN_whitespace_around_input_THEN_strips(
        self, mock_input: Mock
    ):
        mock_input.return_value = "  2  "

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 1

    def test_prompt_index_choice_GIVEN_first_option_THEN_returns_zero(
        self, mock_input: Mock
    ):
        mock_input.return_value = "1"

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 0

    def test_prompt_index_choice_GIVEN_last_option_THEN_returns_last_index(
        self, mock_input: Mock
    ):
        mock_input.return_value = "3"

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 2


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
