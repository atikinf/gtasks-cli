"""The `delete` command."""

import argparse
from unittest.mock import Mock

import pytest
from pytest import CaptureFixture

from gtasks.cli.errors import CliError
from gtasks.cli.listing_state import ListingState
from gtasks.cli.parsers.delete_parser import cmd_delete
from gtasks.utils.config import Config


class TestDeleteParserArgs:
    """Test argument parsing for the 'delete' subcommand."""

    def test_delete_GIVEN_multiple_titles_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["delete", "Buy milk", "Walk dog"])

        assert args.tasks == ["Buy milk", "Walk dog"]


class TestCmdDelete:
    """Test the cmd_delete command handler."""

    SAMPLE_TASKS = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
        {"id": "task2", "title": "Walk dog", "status": "needsAction"},
    ]

    def test_cmd_delete_GIVEN_single_title_THEN_deletes_and_confirms_with_list(
        self, mock_client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS

        cmd_delete(argparse.Namespace(tasks=["Buy milk"]), lambda **_: mock_client, active_config)

        mock_client.delete_tasks.assert_called_once_with("list1", ["task1"])
        assert "✓ Deleted Buy milk · Work" in capsys.readouterr().out

    def test_cmd_delete_GIVEN_multiple_indices_THEN_deletes_all_and_summarises(
        self, mock_client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS

        cmd_delete(argparse.Namespace(tasks=["1", "2"]), lambda **_: mock_client, active_config)

        mock_client.delete_tasks.assert_called_once_with("list1", ["task1", "task2"])
        output = capsys.readouterr().out
        assert "Buy milk" in output
        assert "Walk dog" in output
        assert "Deleted 2 tasks · Work" in output

    def test_cmd_delete_GIVEN_one_bad_number_THEN_deletes_nothing(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        ListingState.default().save("list1", self.SAMPLE_TASKS)

        with pytest.raises(CliError):
            cmd_delete(argparse.Namespace(tasks=["1", "9"]), lambda **_: mock_client, active_config)

        mock_client.delete_tasks.assert_not_called()
