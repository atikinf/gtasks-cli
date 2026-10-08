"""The `add` command."""

import argparse
from unittest.mock import Mock

import pytest
from pytest import CaptureFixture

from gtasks.cli.errors import CliError
from gtasks.cli.parsers.add_parser import cmd_add
from gtasks.utils.config import Config


class TestAddParserArgs:
    """Test argument parsing for the 'add' subcommand."""

    def test_add_GIVEN_title_and_tasklist_title_THEN_parses_correctly(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["add", "My Task", "-l", "Work"])

        assert args.title == "My Task"
        assert args.tasklist_title == "Work"

    @pytest.mark.parametrize(
        "cli_args, expected_notes, expected_due",
        [
            (["add", "Task", "-l", "title1", "--notes", "Notes here"], "Notes here", None),
            (["add", "Task", "-l", "title1", "-d", "2026-01-15"], None, "2026-01-15"),
            (
                ["add", "Task", "-l", "title1", "--notes", "Notes", "-d", "2026-01-15"],
                "Notes",
                "2026-01-15",
            ),
        ],
        ids=["notes-only", "due-only", "notes-and-due"],
    )
    def test_add_GIVEN_optional_flags_THEN_parses_correctly(
        self,
        parser: argparse.ArgumentParser,
        cli_args: list[str],
        expected_notes: str | None,
        expected_due: str | None,
    ) -> None:
        args = parser.parse_args(cli_args)

        assert args.notes == expected_notes
        assert args.due == expected_due

    def test_add_GIVEN_missing_title_THEN_exits(
        self, parser: argparse.ArgumentParser
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args(["add"])

    def test_add_GIVEN_short_n_THEN_rejected(
        self, parser: argparse.ArgumentParser, capsys: CaptureFixture
    ) -> None:
        """-n is --limit elsewhere; on `add` it must not silently become notes."""
        with pytest.raises(SystemExit):
            parser.parse_args(["add", "Task", "-n", "5"])
        capsys.readouterr()


class TestCmdAdd:
    """Test the cmd_add command handler."""

    @pytest.fixture
    def base_args(self) -> dict:
        return {"tasklist_title": None, "title": "Test Task", "notes": None, "due": None}

    def test_cmd_add_GIVEN_active_list_THEN_adds_there_and_confirms_with_list(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.add_task.return_value = {"title": "Test Task"}

        cmd_add(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.add_task.assert_called_once_with(
            tasklist_id="list1", task_title="Test Task", notes=None, due=None
        )
        mock_client.get_tasklists.assert_not_called()
        assert "✓ Added Test Task · Work" in capsys.readouterr().out

    def test_cmd_add_GIVEN_list_flag_THEN_overrides_active(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = [{"id": "list2", "title": "Home"}]
        mock_client.add_task.return_value = {"title": "Test Task"}
        base_args["tasklist_title"] = "home"

        cmd_add(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert mock_client.add_task.call_args.kwargs["tasklist_id"] == "list2"

    def test_cmd_add_GIVEN_notes_and_due_THEN_passes_to_client(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.add_task.return_value = {"title": "Test Task"}
        base_args.update(notes="Important notes", due="2026-01-20T00:00:00Z")

        cmd_add(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.add_task.assert_called_once_with(
            tasklist_id="list1",
            task_title="Test Task",
            notes="Important notes",
            due="2026-01-20T00:00:00.000Z",
        )

    def test_cmd_add_GIVEN_unparseable_due_THEN_raises_before_api_call(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        base_args["due"] = "blursday"

        with pytest.raises(CliError, match="Could not parse due date"):
            cmd_add(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert mock_client.mock_calls == []

    def test_cmd_add_GIVEN_no_matching_tasklist_THEN_raises(
        self, mock_client: Mock, config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = []
        base_args["tasklist_title"] = "NonExistent"

        with pytest.raises(CliError, match="No task list named 'NonExistent'"):
            cmd_add(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.add_task.assert_not_called()
