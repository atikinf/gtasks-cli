"""The `done` command."""

import argparse
from unittest.mock import Mock

import pytest
from pytest import CaptureFixture

from gtasks.cli.errors import CliError
from gtasks.cli.listing_state import ListingState
from gtasks.cli.parsers.done_parser import cmd_done
from gtasks.utils.config import Config


class TestDoneParserArgs:
    """Test argument parsing for the 'done' subcommand."""

    def test_done_GIVEN_multiple_titles_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["done", "Buy milk", "Walk dog"])

        assert args.tasks == ["Buy milk", "Walk dog"]


class TestCmdDone:
    """Test the cmd_done command handler."""

    SAMPLE_TASKS = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
        {"id": "task2", "title": "Walk dog", "status": "needsAction"},
    ]

    def test_cmd_done_GIVEN_single_title_THEN_completes_and_confirms_with_list(
        self, mock_client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        mock_client.complete_tasks.return_value = [
            {"id": "task1", "title": "Buy milk", "status": "completed"}
        ]

        cmd_done(argparse.Namespace(tasks=["Buy milk"]), lambda **_: mock_client, active_config)

        mock_client.complete_tasks.assert_called_once_with("list1", ["task1"])
        assert "✓ Completed Buy milk · Work" in capsys.readouterr().out

    def test_cmd_done_GIVEN_untitled_task_THEN_confirms_it_as_untitled(
        self, mock_client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        # Google sends an untitled task with an empty title, not a missing one.
        mock_client.get_tasks.return_value = [{"id": "t1", "title": "", "status": "needsAction"}]

        cmd_done(argparse.Namespace(tasks=["1"]), lambda **_: mock_client, active_config)

        assert "✓ Completed (untitled) · Work" in capsys.readouterr().out

    def test_cmd_done_GIVEN_multiple_indices_THEN_completes_all_and_summarises(
        self, mock_client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        mock_client.complete_tasks.return_value = [
            {"id": "task1", "title": "Buy milk", "status": "completed"},
            {"id": "task2", "title": "Walk dog", "status": "completed"},
        ]

        cmd_done(argparse.Namespace(tasks=["1", "2"]), lambda **_: mock_client, active_config)

        mock_client.complete_tasks.assert_called_once_with("list1", ["task1", "task2"])
        output = capsys.readouterr().out
        assert "✓ Buy milk" in output
        assert "✓ Walk dog" in output
        assert "Completed 2 tasks · Work" in output

    def test_cmd_done_GIVEN_list_changed_since_listing_THEN_acts_on_task_user_saw(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        ListingState.default().save("list1", self.SAMPLE_TASKS)
        # Elsewhere, a new task was added at the top; #1 would now be "Surprise".
        mock_client.get_tasks.return_value = [{"id": "new", "title": "Surprise"}]
        mock_client.complete_tasks.return_value = [{"id": "task1", "title": "Buy milk"}]

        cmd_done(argparse.Namespace(tasks=["1"]), lambda **_: mock_client, active_config)

        mock_client.complete_tasks.assert_called_once_with("list1", ["task1"])
        mock_client.get_tasks.assert_not_called()

    def test_cmd_done_GIVEN_same_number_twice_across_runs_THEN_second_run_raises(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        ListingState.default().save("list1", self.SAMPLE_TASKS)
        mock_client.complete_tasks.return_value = [{"id": "task1", "title": "Buy milk"}]
        cmd_done(argparse.Namespace(tasks=["1"]), lambda **_: mock_client, active_config)

        with pytest.raises(CliError, match="already completed"):
            cmd_done(argparse.Namespace(tasks=["1"]), lambda **_: mock_client, active_config)

        mock_client.complete_tasks.assert_called_once()
