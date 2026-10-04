"""Tests for CLI argument parsing and command handlers."""

import argparse
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli.cli import build_parser
from gtasks.cli.errors import Cancelled, CliError
from gtasks.cli.parsers.add_parser import cmd_add_task
from gtasks.cli.parsers.config_parser import cmd_config
from gtasks.cli.parsers.delete_parser import cmd_delete
from gtasks.cli.parsers.done_parser import cmd_done
from gtasks.cli.parsers.lists_parser import cmd_list_tasklists
from gtasks.cli.parsers.tasks_parser import cmd_list_tasks
from gtasks.cli.parsers.use_parser import cmd_use
from gtasks.utils.config import Config, ConfigKey
from gtasks.utils.listing_state import ListingState

# =============================================================================
# Shared Fixtures
# =============================================================================


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Provide a Config instance backed by a temp file."""
    return Config(tmp_path / "config.toml", ConfigParser())


@pytest.fixture
def mock_client() -> Mock:
    """Provide a mocked API client whose reads are always live (never from a cache)."""
    client = Mock()
    client.tasks_fetched_at.return_value = None
    return client


@pytest.fixture
def parser() -> argparse.ArgumentParser:
    """Provide a fully-built argument parser."""
    return build_parser()


# =============================================================================
# Argument Parsing Tests
# =============================================================================


class TestRefreshOption:
    @pytest.mark.parametrize(
        "argv",
        [
            ["--refresh"],
            ["--refresh", "tasks"],
            ["tasks", "--refresh"],
            ["lists", "--refresh"],
            ["use", "Work", "--refresh"],
            ["add", "Milk", "--refresh"],
            ["done", "1", "--refresh"],
            ["delete", "1", "--refresh"],
        ],
    )
    def test_GIVEN_refresh_on_any_api_command_THEN_parsed(
        self, parser: argparse.ArgumentParser, argv: list[str]
    ) -> None:
        assert parser.parse_args(argv).refresh is True

    @pytest.mark.parametrize("argv", [[], ["tasks"], ["use", "Work"], ["done", "1"]])
    def test_GIVEN_no_refresh_THEN_false(
        self, parser: argparse.ArgumentParser, argv: list[str]
    ) -> None:
        assert parser.parse_args(argv).refresh is False


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
            (["add", "Task", "-l", "title1", "-n", "Notes here"], "Notes here", None),
            (["add", "Task", "-l", "title1", "-d", "2026-01-15"], None, "2026-01-15"),
            (
                ["add", "Task", "-l", "title1", "-n", "Notes", "-d", "2026-01-15"],
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

    def test_tasks_GIVEN_both_tasklist_flags_THEN_exits(
        self, parser: argparse.ArgumentParser
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args(["tasks", "-t", "id1", "-l", "Work"])


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


class TestDoneParserArgs:
    """Test argument parsing for the 'done' subcommand."""

    def test_done_GIVEN_single_title_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["done", "Buy milk"])

        assert args.command == "done"
        assert args.tasks == ["Buy milk"]
        assert args.tasklist_title is None

    def test_done_GIVEN_multiple_titles_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["done", "Buy milk", "Walk dog"])

        assert args.tasks == ["Buy milk", "Walk dog"]

    def test_done_GIVEN_index_inputs_THEN_parses_as_strings(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["done", "1", "3"])

        assert args.tasks == ["1", "3"]

    def test_done_GIVEN_tasklist_flag_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["done", "Task", "-l", "Work"])

        assert args.tasks == ["Task"]
        assert args.tasklist_title == "Work"


class TestDeleteParserArgs:
    """Test argument parsing for the 'delete' subcommand."""

    def test_delete_GIVEN_single_title_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["delete", "Buy milk"])

        assert args.command == "delete"
        assert args.tasks == ["Buy milk"]
        assert args.tasklist_title is None

    def test_delete_GIVEN_multiple_titles_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["delete", "Buy milk", "Walk dog"])

        assert args.tasks == ["Buy milk", "Walk dog"]

    def test_delete_GIVEN_index_inputs_THEN_parses_as_strings(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["delete", "2", "4"])

        assert args.tasks == ["2", "4"]


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


class TestConfigParserArgs:
    """Test argument parsing for the 'config' subcommand."""

    def test_config_GIVEN_no_args_THEN_key_and_value_are_none(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["config"])

        assert args.command == "config"
        assert args.key is None
        assert args.value is None

    def test_config_GIVEN_key_only_THEN_value_is_none(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["config", "active_tasklist_title"])

        assert args.key == "active_tasklist_title"
        assert args.value is None

    def test_config_GIVEN_key_and_value_THEN_both_parsed(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["config", "active_tasklist_title", "Work"])

        assert args.key == "active_tasklist_title"
        assert args.value == "Work"


# =============================================================================
# Command Handler Tests
# =============================================================================


ACTIVE = {"id": "list1", "title": "Work"}


@pytest.fixture
def active_config(config: Config) -> Config:
    """A config whose active list is ACTIVE."""
    config.set(ConfigKey.ACTIVE_TASKLIST_ID, ACTIVE["id"])
    config.set(ConfigKey.ACTIVE_TASKLIST_TITLE, ACTIVE["title"])
    return config


class TestCmdAddTask:
    """Test the cmd_add_task command handler."""

    @pytest.fixture
    def base_args(self) -> dict:
        return {"tasklist_title": None, "title": "Test Task", "notes": None, "due": None}

    def test_cmd_add_task_GIVEN_active_list_THEN_adds_there_and_confirms_with_list(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.add_task.return_value = {"title": "Test Task"}

        cmd_add_task(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.add_task.assert_called_once_with(
            tasklist_id="list1", task_title="Test Task", notes=None, due=None
        )
        mock_client.get_tasklists.assert_not_called()
        assert "✓ Added Test Task · Work" in capsys.readouterr().out

    def test_cmd_add_task_GIVEN_list_flag_THEN_overrides_active(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = [{"id": "list2", "title": "Home"}]
        mock_client.add_task.return_value = {"title": "Test Task"}
        base_args["tasklist_title"] = "home"

        cmd_add_task(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert mock_client.add_task.call_args.kwargs["tasklist_id"] == "list2"

    def test_cmd_add_task_GIVEN_notes_and_due_THEN_passes_to_client(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.add_task.return_value = {"title": "Test Task"}
        base_args.update(notes="Important notes", due="2026-01-20T00:00:00Z")

        cmd_add_task(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.add_task.assert_called_once_with(
            tasklist_id="list1",
            task_title="Test Task",
            notes="Important notes",
            due="2026-01-20T00:00:00.000Z",
        )

    def test_cmd_add_task_GIVEN_unparseable_due_THEN_raises_before_api_call(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        base_args["due"] = "blursday"

        with pytest.raises(CliError, match="Could not parse due date"):
            cmd_add_task(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert mock_client.mock_calls == []

    def test_cmd_add_task_GIVEN_no_matching_tasklist_THEN_raises(
        self, mock_client: Mock, config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = []
        base_args["tasklist_title"] = "NonExistent"

        with pytest.raises(CliError, match="No task list named 'NonExistent'"):
            cmd_add_task(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.add_task.assert_not_called()


class TestCmdListTasks:
    """Test the cmd_list_tasks command handler."""

    SAMPLE_TASKS = [
        {"id": "t1", "title": "Task 1", "notes": "Notes 1"},
        {"id": "t2", "title": "Task 2"},
        {"id": "t3", "title": "Task 3"},
    ]

    @pytest.fixture
    def base_args(self) -> dict:
        return {"tasklist_title": None, "limit": None, "show_ids": False}

    def test_cmd_list_tasks_GIVEN_active_list_THEN_fetches_and_shows_heading(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS

        cmd_list_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.get_tasks.assert_called_once_with("list1", None, show_completed=False)
        output = capsys.readouterr().out
        assert "Work · 3 open" in output
        assert "Task 1" in output
        assert "Notes 1" in output

    def test_cmd_list_tasks_GIVEN_cached_data_THEN_heading_says_how_old(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        mock_client.tasks_fetched_at.return_value = 1_000_000.0

        with patch("gtasks.cli.parsers.tasks_parser.time.time", return_value=1_000_000.0 + 300):
            cmd_list_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.tasks_fetched_at.assert_called_once_with("list1")
        assert "Work · 3 open · cached 5m ago" in capsys.readouterr().out

    def test_cmd_list_tasks_GIVEN_nothing_set_THEN_uses_account_default(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklist.return_value = {"id": "def", "title": "My Tasks"}
        mock_client.get_tasks.return_value = []

        cmd_list_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.get_tasks.assert_called_once_with("def", None, show_completed=False)
        assert "My Tasks · 0 open" in capsys.readouterr().out

    def test_cmd_list_tasks_GIVEN_limit_and_more_tasks_THEN_truncates_and_says_so(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        base_args["limit"] = 2

        cmd_list_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        mock_client.get_tasks.assert_called_once_with("list1", 3, show_completed=False)
        output = capsys.readouterr().out
        assert "2+ open" in output
        assert "Task 3" not in output

    def test_cmd_list_tasks_GIVEN_show_ids_THEN_includes_ids_in_output(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS
        base_args["show_ids"] = True

        cmd_list_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        output = capsys.readouterr().out
        assert "t1" in output
        assert "t2" in output

    def test_cmd_list_tasks_THEN_records_listing_for_numbered_commands(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasks.return_value = self.SAMPLE_TASKS[:2]

        cmd_list_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert ListingState.beside(active_config).rows("list1") == [
            {"id": "t1", "title": "Task 1"},
            {"id": "t2", "title": "Task 2"},
        ]

    def test_cmd_list_tasks_GIVEN_no_matching_tasklist_THEN_raises(
        self, mock_client: Mock, config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = []
        base_args["tasklist_title"] = "NonExistent"

        with pytest.raises(CliError):
            cmd_list_tasks(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.get_tasks.assert_not_called()


class TestCmdListTasklists:
    """Test the cmd_list_tasklists command handler."""

    SAMPLE_TASKLISTS = [{"id": "list1", "title": "Work"}, {"id": "list2", "title": "Personal"}]

    @pytest.fixture
    def base_args(self) -> dict:
        return {"limit": None, "show_ids": False}

    def test_cmd_list_tasklists_GIVEN_defaults_THEN_fetches_all(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS

        cmd_list_tasklists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.get_tasklists.assert_called_once_with(None)
        output = capsys.readouterr().out
        assert "Work" in output
        assert "Personal" in output

    def test_cmd_list_tasklists_GIVEN_limit_THEN_passes_to_client(
        self, mock_client: Mock, config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS
        base_args["limit"] = 5

        cmd_list_tasklists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        mock_client.get_tasklists.assert_called_once_with(5)

    def test_cmd_list_tasklists_GIVEN_active_list_THEN_marks_it(
        self, mock_client: Mock, active_config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS

        cmd_list_tasklists(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert "● Work" in capsys.readouterr().out

    def test_cmd_list_tasklists_GIVEN_active_list_renamed_THEN_refreshes_cached_title(
        self, mock_client: Mock, active_config: Config, base_args: dict
    ) -> None:
        mock_client.get_tasklists.return_value = [{"id": "list1", "title": "Job"}]

        cmd_list_tasklists(argparse.Namespace(**base_args), lambda **_: mock_client, active_config)

        assert active_config.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "Job"

    def test_cmd_list_tasklists_GIVEN_show_ids_THEN_includes_ids_in_output(
        self, mock_client: Mock, config: Config, base_args: dict, capsys: CaptureFixture
    ) -> None:
        mock_client.get_tasklists.return_value = self.SAMPLE_TASKLISTS
        base_args["show_ids"] = True

        cmd_list_tasklists(argparse.Namespace(**base_args), lambda **_: mock_client, config)

        output = capsys.readouterr().out
        assert "list1" in output
        assert "list2" in output


class TestCmdUse:
    """Test the cmd_use command handler."""

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

    def test_cmd_use_GIVEN_no_name_THEN_picks_interactively(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE, {"id": "list2", "title": "Home"}]

        with patch("builtins.input", return_value="2"):
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, config)

        assert config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list2"

    def test_cmd_use_GIVEN_picker_cancelled_THEN_raises_cancelled(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [ACTIVE, {"id": "list2", "title": "Home"}]

        with patch("builtins.input", return_value="q"), pytest.raises(Cancelled):
            cmd_use(argparse.Namespace(name=None), lambda **_: mock_client, config)

        assert config.get(ConfigKey.ACTIVE_TASKLIST_ID) is None


class TestCmdConfig:
    """Test the cmd_config command handler."""

    def test_cmd_config_GIVEN_no_args_THEN_prints_all_settings(
        self, mock_client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        cmd_config(argparse.Namespace(key=None, value=None), lambda **_: mock_client, active_config)

        output = capsys.readouterr().out
        assert "active_tasklist_id = list1" in output
        assert "active_tasklist_title = Work" in output

    def test_cmd_config_GIVEN_no_args_and_unset_THEN_prints_not_set(
        self, mock_client: Mock, config: Config, capsys: CaptureFixture
    ) -> None:
        cmd_config(argparse.Namespace(key=None, value=None), lambda **_: mock_client, config)

        assert "(not set)" in capsys.readouterr().out

    def test_cmd_config_GIVEN_key_only_THEN_prints_value(
        self, mock_client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        args = argparse.Namespace(key="active_tasklist_title", value=None)

        cmd_config(args, lambda **_: mock_client, active_config)

        assert "active_tasklist_title = Work" in capsys.readouterr().out

    def test_cmd_config_GIVEN_managed_key_and_value_THEN_refuses_and_points_to_use(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        args = argparse.Namespace(key="active_tasklist_title", value="Other")

        with pytest.raises(CliError, match="gtasks use") as exc:
            cmd_config(args, lambda **_: mock_client, active_config)

        assert exc.value.hint == "Run `gtasks use`."
        assert active_config.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "Work"

    def test_cmd_config_GIVEN_legacy_default_tasklist_key_THEN_points_to_use(
        self, mock_client: Mock, config: Config
    ) -> None:
        args = argparse.Namespace(key="default_tasklist", value="Work")

        with pytest.raises(CliError, match="replaced by the active list") as exc:
            cmd_config(args, lambda **_: mock_client, config)

        assert exc.value.hint == "Run `gtasks use <list>`."

    @pytest.mark.parametrize("value", ["on", "off"])
    def test_cmd_config_GIVEN_valid_cache_value_THEN_saved(
        self, mock_client: Mock, config: Config, value: str
    ) -> None:
        cmd_config(argparse.Namespace(key="cache", value=value), lambda **_: mock_client, config)

        assert config.get(ConfigKey.CACHE) == value

    @pytest.mark.parametrize("value", ["yes", "ON", "true", ""])
    def test_cmd_config_GIVEN_invalid_cache_value_THEN_rejected_and_not_saved(
        self, mock_client: Mock, config: Config, value: str
    ) -> None:
        args = argparse.Namespace(key="cache", value=value)

        with pytest.raises(CliError, match="isn't a valid value") as exc:
            cmd_config(args, lambda **_: mock_client, config)

        assert exc.value.hint == "Use one of: on, off"
        assert config.get(ConfigKey.CACHE) is None

    def test_cmd_config_GIVEN_invalid_key_THEN_raises(
        self, mock_client: Mock, config: Config
    ) -> None:
        with pytest.raises(CliError, match="Unknown key"):
            args = argparse.Namespace(key="nonexistent", value=None)
            cmd_config(args, lambda **_: mock_client, config)


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
        ListingState.beside(active_config).save("list1", self.SAMPLE_TASKS)
        # Elsewhere, a new task was added at the top; #1 would now be "Surprise".
        mock_client.get_tasks.return_value = [{"id": "new", "title": "Surprise"}]
        mock_client.complete_tasks.return_value = [{"id": "task1", "title": "Buy milk"}]

        cmd_done(argparse.Namespace(tasks=["1"]), lambda **_: mock_client, active_config)

        mock_client.complete_tasks.assert_called_once_with("list1", ["task1"])
        mock_client.get_tasks.assert_not_called()

    def test_cmd_done_GIVEN_same_number_twice_across_runs_THEN_second_run_raises(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        ListingState.beside(active_config).save("list1", self.SAMPLE_TASKS)
        mock_client.complete_tasks.return_value = [{"id": "task1", "title": "Buy milk"}]
        cmd_done(argparse.Namespace(tasks=["1"]), lambda **_: mock_client, active_config)

        with pytest.raises(CliError, match="already completed"):
            cmd_done(argparse.Namespace(tasks=["1"]), lambda **_: mock_client, active_config)

        mock_client.complete_tasks.assert_called_once()


class TestFreshReads:
    """`done`/`delete` decide which task a write hits, so they must never read cached data."""

    @pytest.mark.parametrize("handler", [cmd_done, cmd_delete], ids=["done", "delete"])
    def test_GIVEN_write_command_THEN_asks_for_fresh_client(
        self, handler, mock_client: Mock, active_config: Config
    ) -> None:
        mock_client.get_tasks.return_value = [{"id": "task1", "title": "Buy milk"}]
        mock_client.complete_tasks.return_value = [{"id": "task1", "title": "Buy milk"}]
        get_client = Mock(return_value=mock_client)

        handler(argparse.Namespace(tasks=["1"]), get_client, active_config)

        get_client.assert_called_once_with(fresh=True)

    def test_GIVEN_listing_THEN_uses_default_client(
        self, mock_client: Mock, active_config: Config
    ) -> None:
        mock_client.get_tasks.return_value = []
        get_client = Mock(return_value=mock_client)
        args = argparse.Namespace(tasklist_title=None, limit=None, show_ids=False)

        cmd_list_tasks(args, get_client, active_config)

        get_client.assert_called_once_with()


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
        ListingState.beside(active_config).save("list1", self.SAMPLE_TASKS)

        with pytest.raises(CliError):
            cmd_delete(argparse.Namespace(tasks=["1", "9"]), lambda **_: mock_client, active_config)

        mock_client.delete_tasks.assert_not_called()
