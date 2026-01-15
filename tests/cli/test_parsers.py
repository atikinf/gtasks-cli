"""Tests for CLI argument parsing and command handlers."""

import argparse
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli.cli import build_parser
from gtasks.cli.parsers.add_parser import cmd_add_task
from gtasks.cli.parsers.lists_parser import cmd_list_tasklists
from gtasks.cli.parsers.tasks_parser import cmd_list_tasks
from gtasks.utils.config import Config

# =============================================================================
# Shared Fixtures
# =============================================================================


@pytest.fixture
def config(tmp_path: Path) -> Config:
    """Provide a Config instance backed by a temp file."""
    return Config(tmp_path / "config.toml", ConfigParser())


@pytest.fixture
def mock_client() -> Mock:
    """Provide a mocked API client."""
    return Mock()


@pytest.fixture
def parser(mock_client: Mock, config: Config) -> argparse.ArgumentParser:
    """Provide a fully-built argument parser."""
    return build_parser(mock_client, config)


# =============================================================================
# Argument Parsing Tests
# =============================================================================


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
            parser.parse_args(["add", "-t", "abc123"])

    def test_add_GIVEN_both_tasklist_flags_THEN_exits(
        self, parser: argparse.ArgumentParser
    ) -> None:
        with pytest.raises(SystemExit):
            parser.parse_args(["add", "Task", "-t", "id1", "-l", "Work"])


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


class TestSetDefaultParserArgs:
    """Test argument parsing for the 'set-default' subcommand."""

    def test_set_default_GIVEN_no_args_THEN_parses(
        self, parser: argparse.ArgumentParser
    ) -> None:
        args = parser.parse_args(["set-default"])

        assert args.command == "set-default"
        assert hasattr(args, "func")


# =============================================================================
# Command Handler Tests
# =============================================================================


class TestCmdAddTask:
    """Test the cmd_add_task command handler."""

    @pytest.fixture
    def base_args(self) -> dict:
        """Base arguments for add command."""
        return {
            "tasklist_title": None,
            "title": "Test Task",
            "notes": None,
            "due": None,
        }

    @pytest.fixture
    def sample_tasklists(self) -> list[dict]:
        """Sample tasklist data for testing."""
        return [
            {"id": "list1", "title": "Work"},
            {"id": "list2", "title": "Personal"},
        ]

    def test_cmd_add_task_GIVEN_tasklist_title_THEN_resolves_and_calls(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasklists: list[dict],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        mock_client.add_task.return_value = {"title": "Test Task"}
        base_args["tasklist_title"] = "Work"
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.add_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = "list1"
            cmd_add_task(args, mock_client, config)

        mock_client.add_task.assert_called_once_with(
            tasklist_id="list1",
            title="Test Task",
            notes=None,
            due=None,
        )

    def test_cmd_add_task_GIVEN_no_title_but_config_default_THEN_uses_config(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasklists: list[dict],
    ) -> None:
        config.set_tasklist_title("Work")
        mock_client.get_tasklists.return_value = sample_tasklists
        mock_client.add_task.return_value = {"title": "Test Task"}
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.add_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = "list1"
            cmd_add_task(args, mock_client, config)

        mock_client.add_task.assert_called_once()

    def test_cmd_add_task_GIVEN_no_tasklist_and_no_config_THEN_exits(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        capsys: CaptureFixture[str],
    ) -> None:
        args = argparse.Namespace(**base_args)

        with pytest.raises(SystemExit) as exc:
            cmd_add_task(args, mock_client, config)

        assert exc.value.code == 1
        output = capsys.readouterr().out
        assert "tasklist-title" in output or "default tasklist" in output

    def test_cmd_add_task_GIVEN_all_options_THEN_passes_to_client(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasklists: list[dict],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        mock_client.add_task.return_value = {"title": "Task"}
        base_args.update(
            tasklist_title="Work",
            notes="Important notes",
            due="2026-01-20T00:00:00Z",
        )
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.add_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = "list1"
            cmd_add_task(args, mock_client, config)
        mock_client.add_task.assert_called_once_with(
            tasklist_id="list1",
            title="Test Task",
            notes="Important notes",
            due="2026-01-20T00:00:00Z",
        )

    def test_cmd_add_task_GIVEN_no_matching_tasklist_THEN_prints_error(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasklists: list[dict],
        capsys: CaptureFixture[str],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        base_args["tasklist_title"] = "NonExistent"
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.add_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = None
            cmd_add_task(args, mock_client, config)

        output = capsys.readouterr().out
        assert "Couldn't find" in output


class TestCmdListTasks:
    """Test the cmd_list_tasks command handler."""

    @pytest.fixture
    def base_args(self) -> dict:
        """Base arguments for tasks command."""
        return {
            "tasklist_title": None,
            "limit": None,
            "show_ids": False,
        }

    @pytest.fixture
    def sample_tasks(self) -> list[dict]:
        """Sample task data for testing."""
        return [
            {"id": "t1", "title": "Task 1", "notes": "Notes 1"},
            {"id": "t2", "title": "Task 2", "due": "2026-01-20"},
            {"id": "t3", "title": "Task 3"},
        ]

    @pytest.fixture
    def sample_tasklists(self) -> list[dict]:
        """Sample tasklist data for testing."""
        return [
            {"id": "list1", "title": "Work"},
            {"id": "list2", "title": "Personal"},
        ]

    def test_cmd_list_tasks_GIVEN_tasklist_title_THEN_fetches_tasks(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasks: list[dict],
        sample_tasklists: list[dict],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        mock_client.get_tasks.return_value = sample_tasks
        base_args["tasklist_title"] = "Work"
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.tasks_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = "list1"
            cmd_list_tasks(args, mock_client, config)

        mock_client.get_tasks.assert_called_once_with("list1", None)

    def test_cmd_list_tasks_GIVEN_no_title_but_config_default_THEN_uses_config(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasks: list[dict],
        sample_tasklists: list[dict],
    ) -> None:
        config.set_tasklist_title("Work")
        mock_client.get_tasklists.return_value = sample_tasklists
        mock_client.get_tasks.return_value = sample_tasks
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.tasks_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = "list1"
            cmd_list_tasks(args, mock_client, config)

        mock_client.get_tasks.assert_called_once()

    def test_cmd_list_tasks_GIVEN_show_ids_THEN_includes_ids_in_output(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasks: list[dict],
        sample_tasklists: list[dict],
        capsys: CaptureFixture[str],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        mock_client.get_tasks.return_value = sample_tasks
        base_args["tasklist_title"] = "Work"
        base_args["show_ids"] = True
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.tasks_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = "list1"
            cmd_list_tasks(args, mock_client, config)

        output = capsys.readouterr().out
        assert "[t1]" in output
        assert "[t2]" in output

    def test_cmd_list_tasks_GIVEN_tasks_with_notes_and_due_THEN_formats_output(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasks: list[dict],
        sample_tasklists: list[dict],
        capsys: CaptureFixture[str],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        mock_client.get_tasks.return_value = sample_tasks
        base_args["tasklist_title"] = "Work"
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.tasks_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = "list1"
            cmd_list_tasks(args, mock_client, config)

        output = capsys.readouterr().out
        assert "Task 1" in output
        assert "Notes: Notes 1" in output
        assert "Due: 2026-01-20" in output

    def test_cmd_list_tasks_GIVEN_no_tasklist_and_no_config_THEN_exits(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        capsys: CaptureFixture[str],
    ) -> None:
        args = argparse.Namespace(**base_args)

        with pytest.raises(SystemExit) as exc:
            cmd_list_tasks(args, mock_client, config)

        assert exc.value.code == 1
        output = capsys.readouterr().out
        assert "tasklist-title" in output or "default tasklist" in output

    def test_cmd_list_tasks_GIVEN_no_matching_tasklist_THEN_prints_error(
        self,
        mock_client: Mock,
        config: Config,
        base_args: dict,
        sample_tasklists: list[dict],
        capsys: CaptureFixture[str],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        base_args["tasklist_title"] = "NonExistent"
        args = argparse.Namespace(**base_args)

        with patch(
            "gtasks.cli.parsers.tasks_parser.prompt_choose_tasklist_id"
        ) as mock_prompt:
            mock_prompt.return_value = None
            cmd_list_tasks(args, mock_client, config)

        output = capsys.readouterr().out
        assert "Couldn't find" in output


class TestCmdListTasklists:
    """Test the cmd_list_tasklists command handler."""

    @pytest.fixture
    def base_args(self) -> dict:
        """Base arguments for lists command."""
        return {"limit": None, "show_ids": False}

    @pytest.fixture
    def sample_tasklists(self) -> list[dict]:
        """Sample tasklist data for testing."""
        return [
            {"id": "list1", "title": "Work"},
            {"id": "list2", "title": "Personal"},
        ]

    def test_cmd_list_tasklists_GIVEN_defaults_THEN_fetches_all(
        self,
        mock_client: Mock,
        base_args: dict,
        sample_tasklists: list[dict],
        capsys: CaptureFixture[str],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        args = argparse.Namespace(**base_args)

        cmd_list_tasklists(args, mock_client)

        mock_client.get_tasklists.assert_called_once_with(None)
        output = capsys.readouterr().out
        assert "Work" in output
        assert "Personal" in output

    def test_cmd_list_tasklists_GIVEN_limit_THEN_passes_to_client(
        self,
        mock_client: Mock,
        base_args: dict,
        sample_tasklists: list[dict],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        base_args["limit"] = 5
        args = argparse.Namespace(**base_args)

        cmd_list_tasklists(args, mock_client)

        mock_client.get_tasklists.assert_called_once_with(5)

    def test_cmd_list_tasklists_GIVEN_show_ids_THEN_includes_ids_in_output(
        self,
        mock_client: Mock,
        base_args: dict,
        sample_tasklists: list[dict],
        capsys: CaptureFixture[str],
    ) -> None:
        mock_client.get_tasklists.return_value = sample_tasklists
        base_args["show_ids"] = True
        args = argparse.Namespace(**base_args)

        cmd_list_tasklists(args, mock_client)

        output = capsys.readouterr().out
        assert "[list1]" in output
        assert "[list2]" in output
