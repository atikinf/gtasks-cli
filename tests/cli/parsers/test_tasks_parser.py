"""The `tasks` command (and bare `gtasks`)."""

import argparse
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli.errors import CliError
from gtasks.cli.listing_state import ListingState
from gtasks.cli.parsers.tasks_parser import cmd_tasks
from gtasks.client.protocol import CacheState
from gtasks.utils.config import Config


class TestTasksParserArgs:
    """Test argument parsing for the 'tasks' subcommand."""

    def test_tasks_GIVEN_tasklist_title_THEN_parses_correctly(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["tasks", "-l", "list123"])

        assert args.command == "tasks"
        assert args.tasklist_title == "list123"
        assert args.limit is None
        assert args.show_ids is False

    @pytest.mark.parametrize(
        "cli_args, expected_limit, expected_show_ids",
        [
            (["tasks", "-l", "title1", "-n", "10"], 10, False),
            (["tasks", "-l", "title1", "--show-ids"], None, True),
            (["tasks", "-l", "title1", "-n", "5", "--show-ids"], 5, True),
        ],
        ids=["limit-only", "show-ids-only", "limit-and-show-ids"],
    )
    def test_tasks_GIVEN_optional_flags_THEN_parses_correctly(
        self,
        parser: argparse.ArgumentParser,
        cli_args: list[str],
        expected_limit: int | None,
        expected_show_ids: bool,
    ) -> None:
        args = parser.parse_args(cli_args)

        assert args.limit == expected_limit
        assert args.show_ids == expected_show_ids


class TestCmdTasks:
    """Test the cmd_tasks command handler."""

    SAMPLE_TASKS = [
        {"id": "t1", "title": "Task 1", "notes": "Notes 1"},
        {"id": "t2", "title": "Task 2"},
        {"id": "t3", "title": "Task 3"},
    ]

    @pytest.fixture
    def base_args(self) -> dict:
        return {"tasklist_title": None, "limit": None, "show_ids": False}

    def test_cmd_tasks_GIVEN_active_list_THEN_fetches_and_shows_heading(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS

        cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)
        output = capsys.readouterr().out
        assert "Work · 3 open" in output
        assert "Task 1" in output
        assert "Notes 1" in output

    def test_cmd_tasks_GIVEN_cached_data_THEN_heading_says_how_old(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        mock_client.tasks_cache_state.return_value = CacheState(True, 1_000_000.0)

        with patch("gtasks.cli.ui.time.time", return_value=1_000_000.0 + 300):
            cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.tasks_cache_state.assert_called_once_with("list1")
        assert "Work · 3 open · cached 5m ago" in capsys.readouterr().out

    def test_cmd_tasks_GIVEN_data_just_saved_to_cache_THEN_heading_says_refreshed(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        mock_client.tasks_cache_state.return_value = CacheState(False, 1_000_000.0)

        cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert "Work · 3 open · cache refreshed" in capsys.readouterr().out

    def test_cmd_tasks_GIVEN_nothing_set_THEN_uses_account_default(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklist.return_value = {"id": "def", "title": "My Tasks"}
        mock_client.get_tasks.return_value = []

        cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.get_tasks.assert_called_once_with("def", show_completed=False)
        assert "My Tasks · 0 open" in capsys.readouterr().out

    def test_cmd_tasks_GIVEN_limit_and_more_tasks_THEN_truncates_and_says_so(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        base_args["limit"] = 2

        cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        # The whole list: the limit applies after putting it in display order.
        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)
        output = capsys.readouterr().out
        assert "2+ open" in output
        assert "Task 3" not in output

    def test_cmd_tasks_GIVEN_api_order_THEN_app_order_with_subtasks_under_parent(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        # As the API returns them: most recently updated first.
        mock_client.get_tasks.return_value = [
            {"id": "c", "title": "Pack", "parent": "a", "position": "00000000000000000001"},
            {"id": "b", "title": "Taxes", "position": "00000000000000000001"},
            {"id": "a", "title": "Trip", "position": "00000000000000000000"},
            {"id": "d", "title": "Book", "parent": "a", "position": "00000000000000000000"},
        ]
        base_args["limit"] = 3

        cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        rows = [line.strip() for line in capsys.readouterr().out.splitlines()[1:4]]
        assert rows == ["1 ○ Trip", "2 └ ○ Book", "3 └ ○ Pack"]
        # Numbers follow the displayed order.
        assert [r["id"] for r in ListingState.default().rows("list1") or []] == ["a", "d", "c"]

    def test_cmd_tasks_GIVEN_show_ids_THEN_includes_ids_in_output(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        base_args["show_ids"] = True

        cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        output = capsys.readouterr().out
        assert "t1" in output
        assert "t2" in output

    def test_cmd_tasks_THEN_records_listing_for_numbered_commands(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS[:2]

        cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert ListingState.default().rows("list1") == [
            {"id": "t1", "title": "Task 1"},
            {"id": "t2", "title": "Task 2"},
        ]

    def test_cmd_tasks_GIVEN_no_matching_tasklist_THEN_raises(
        self, mock_client: Mock, config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = []
        base_args["tasklist_title"] = "NonExistent"

        with pytest.raises(CliError):
            cmd_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.get_tasks.assert_not_called()
