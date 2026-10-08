"""The `lists` command."""

import argparse
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli.parsers.lists_parser import cmd_lists
from gtasks.client.protocol import CacheState
from gtasks.utils.config import Config, ConfigKey

ACTIVE = {"id": "list1", "title": "Work"}


class TestListsParserArgs:
    """Test argument parsing for the 'lists' subcommand."""

    def test_lists_GIVEN_no_args_THEN_uses_defaults(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["lists"])

        assert args.command == "lists"
        assert args.limit is None
        assert args.show_ids is False

    @pytest.mark.parametrize(
        "cli_args,expected_limit,expected_show_ids",
        [
            (["lists", "-n", "5"], 5, False),
            (["lists", "--show-ids"], None, True),
            (["lists", "-n", "10", "--show-ids"], 10, True),
        ],
        ids=["limit-only", "show-ids-only", "limit-and-show-ids"],
    )
    def test_lists_GIVEN_optional_flags_THEN_parses_correctly(
        self,
        parser: argparse.ArgumentParser,
        cli_args: list[str],
        expected_limit: int | None,
        expected_show_ids: bool,
    ) -> None:
        args = parser.parse_args(cli_args)

        assert args.limit == expected_limit
        assert args.show_ids == expected_show_ids


class TestCmdLists:
    """Test the cmd_lists command handler."""

    SAMPLE_TASKLISTS = [{"id": "list1", "title": "Work"}, {"id": "list2", "title": "Personal"}]

    @pytest.fixture
    def base_args(self) -> dict:
        return {"limit": None, "show_ids": False}

    def test_cmd_lists_GIVEN_defaults_THEN_fetches_all(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS

        cmd_lists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.get_tasklists.assert_called_once_with()
        output = capsys.readouterr().out
        assert "Work" in output
        assert "Personal" in output

    def test_cmd_lists_GIVEN_limit_and_more_lists_THEN_truncates_and_says_so(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS
        base_args["limit"] = 1

        cmd_lists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        output = capsys.readouterr().out
        assert "Task lists · 1+" in output
        assert "Personal" not in output
        assert "More not shown" in output

    def test_cmd_lists_GIVEN_limit_not_reached_THEN_no_truncation_note(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS
        base_args["limit"] = 5

        cmd_lists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        output = capsys.readouterr().out
        assert output.splitlines()[0].strip() == "Task lists · 2"
        assert "More not shown" not in output

    def test_cmd_lists_GIVEN_active_list_THEN_marks_it(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS

        cmd_lists(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert "● Work" in capsys.readouterr().out

    def test_cmd_lists_GIVEN_cached_lists_THEN_heading_says_how_old(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS
        mock_client.tasklists_cache_state.return_value = CacheState(True, 1_000_000.0)

        with patch("gtasks.cli.ui.time.time", return_value=1_000_000.0 + 600):
            cmd_lists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        assert "Task lists · 2 · cached 10m ago" in capsys.readouterr().out

    def test_cmd_lists_GIVEN_active_list_renamed_THEN_refreshes_cached_title(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = [{"id": "list1", "title": "Job"}]

        cmd_lists(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert active_config.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "Job"

    def test_cmd_lists_GIVEN_show_ids_THEN_includes_ids_in_output(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS
        base_args["show_ids"] = True

        cmd_lists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        output = capsys.readouterr().out
        assert "list1" in output
        assert "list2" in output
