"""The `use` command."""

import argparse
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli import ui
from gtasks.cli.errors import Cancelled, CliError
from gtasks.cli.listing_state import ListingState
from gtasks.cli.parsers.use_parser import cmd_use
from gtasks.utils.config import Config, ConfigKey

ACTIVE = {"id": "list1", "title": "Work"}


class TestUseParserArgs:
    """Test argument parsing for the 'use' subcommand."""

    def test_use_GIVEN_no_args_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["use"])

        assert args.command == "use"
        assert args.name is None
        assert hasattr(args, "func")

    def test_use_GIVEN_name_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["use", "Work"])

        assert args.command == "use"
        assert args.name == "Work"


class TestCmdUse:
    """Test the cmd_use command handler."""

    @pytest.fixture(autouse=True)
    def no_tasks(self, mock_client: Mock) -> None:
        # `use` shows the new active list after switching.
        mock_client.get_tasks.return_value = []

    def test_cmd_use_GIVEN_name_THEN_stores_id_and_canonical_title(
        self, mock_client: Mock, config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE]

        cmd_use(argparse.Namespace(name="work"), lambda **_: mock_client, config)

        assert config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list1"
        assert config.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "Work"
        assert "✓ Active list: Work" in capsys.readouterr().out

    def test_cmd_use_GIVEN_unknown_name_THEN_raises_and_keeps_previous(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = []

        with pytest.raises(CliError):
            cmd_use(argparse.Namespace(name="Nope"), lambda **_: mock_client, active_config)

        assert active_config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list1"
        mock_client.get_tasks.assert_not_called()

    def test_cmd_use_GIVEN_no_name_THEN_picks_interactively(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE, {"id": "list2", "title": "Home"}]

        with patch("builtins.input", return_value="2"):
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, config)

        assert config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list2"

    def test_cmd_use_GIVEN_no_name_THEN_picker_has_heading(
        self, mock_client: Mock, config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE, {"id": "list2", "title": "Home"}]

        with patch("builtins.input", return_value="1"):
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, config)

        assert capsys.readouterr().out.splitlines()[0].strip() == "Task lists · 2"

    def test_cmd_use_GIVEN_no_lists_THEN_one_error_and_nothing_printed(
        self, mock_client: Mock, config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = []

        with pytest.raises(CliError) as exc_info:
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, config)

        assert exc_info.value.message == ui.NO_TASKLISTS
        assert capsys.readouterr().out == ""

    def test_cmd_use_GIVEN_picker_and_active_list_renamed_THEN_stored_title_updated(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [
            {"id": "list1", "title": "Work (renamed)"},
            {"id": "list2", "title": "Home"},
        ]

        with patch("builtins.input", return_value="q"), pytest.raises(Cancelled):
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, active_config)

        # The picker shows lists the same way `lists` does, title sync included.
        assert active_config.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "Work (renamed)"

    def test_cmd_use_GIVEN_picker_cancelled_THEN_raises_cancelled(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE, {"id": "list2", "title": "Home"}]

        with patch("builtins.input", return_value="q"), pytest.raises(Cancelled):
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, config)

        assert config.get(ConfigKey.ACTIVE_TASKLIST_ID) is None
        mock_client.get_tasks.assert_not_called()

    def test_cmd_use_GIVEN_name_THEN_shows_list(
        self, mock_client: Mock, config: Config, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE]
        mock_client.get_tasks.return_value = [{"id": "t1", "title": "Ship it"}]
        get_client = Mock(return_value=mock_client)

        cmd_use(argparse.Namespace(name="work"), get_client, config)

        get_client.assert_called_once_with()  # cached like bare `gtasks`; --refresh forces fresh
        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)
        lines = [line.strip() for line in capsys.readouterr().out.splitlines()]
        assert lines[0] == "✓ Active list: Work"
        assert lines[1].startswith("Work · 1 open")
        assert "Ship it" in lines[2]

    def test_cmd_use_GIVEN_picker_choice_THEN_shows_chosen_list(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE, {"id": "list2", "title": "Home"}]

        with patch("builtins.input", return_value="2"):
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, config)

        assert mock_client.get_tasks.call_args.args[0] == "list2"

    def test_cmd_use_THEN_records_listing_for_numbers(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE]
        mock_client.get_tasks.return_value = [{"id": "t1", "title": "Ship it"}]

        cmd_use(argparse.Namespace(name="Work"), lambda **_: mock_client, config)

        # So `done 1` right after hits the task `use` showed as 1.
        assert ListingState.default().rows("list1") == [{"id": "t1", "title": "Ship it"}]
