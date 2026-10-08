"""What `done` and `delete` share: fresh reads and partial-title handling."""

import argparse
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli.errors import Cancelled
from gtasks.cli.parsers.delete_parser import cmd_delete
from gtasks.cli.parsers.done_parser import cmd_done
from gtasks.cli.parsers.tasks_parser import cmd_tasks
from gtasks.utils.config import Config


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

        cmd_tasks(args, get_client, active_config)

        get_client.assert_called_once_with()


class TestPartialTitleCommands:
    """A fragment of a title works on Enter; `delete` confirms it first, `done` doesn't."""

    TASKS = [
        {"id": "t1", "title": "Buy milk"},
        {"id": "t2", "title": "Call dentist"},
    ]

    @pytest.fixture
    def client(self, mock_client: Mock) -> Mock:
        mock_client.get_tasks.return_value = self.TASKS
        mock_client.complete_tasks.return_value = [self.TASKS[0]]
        return mock_client

    def test_done_GIVEN_fragment_THEN_completes_without_prompt(
        self, client: Mock, active_config: Config, capsys: CaptureFixture
    ) -> None:
        with patch("builtins.input") as mock_input:
            cmd_done(argparse.Namespace(tasks=["milk"]), lambda **_: client, active_config)

        mock_input.assert_not_called()
        client.complete_tasks.assert_called_once_with("list1", ["t1"])
        assert "✓ Completed Buy milk · Work" in capsys.readouterr().out

    def test_delete_GIVEN_fragment_and_yes_answer_THEN_asks_then_deletes(
        self, client: Mock, active_config: Config
    ) -> None:
        with patch("builtins.input", return_value="y") as mock_input:
            cmd_delete(
                argparse.Namespace(tasks=["milk"], yes=False), lambda **_: client, active_config
            )

        assert mock_input.call_args.args[0] == "Delete 'Buy milk' from Work? [y/N] "
        client.delete_tasks.assert_called_once_with("list1", ["t1"])

    @pytest.mark.parametrize("answer", ["", "n", "no", "nope"])
    def test_delete_GIVEN_fragment_and_not_yes_THEN_cancelled_nothing_deleted(
        self, client: Mock, active_config: Config, answer: str
    ) -> None:
        args = argparse.Namespace(tasks=["milk"], yes=False)

        with patch("builtins.input", return_value=answer), pytest.raises(Cancelled):
            cmd_delete(args, lambda **_: client, active_config)

        client.delete_tasks.assert_not_called()

    def test_delete_GIVEN_fragment_and_yes_flag_THEN_no_prompt(
        self, client: Mock, active_config: Config
    ) -> None:
        with patch("builtins.input") as mock_input:
            cmd_delete(
                argparse.Namespace(tasks=["milk"], yes=True), lambda **_: client, active_config
            )

        mock_input.assert_not_called()
        client.delete_tasks.assert_called_once()

    def test_delete_GIVEN_exact_title_THEN_no_prompt(
        self, client: Mock, active_config: Config
    ) -> None:
        with patch("builtins.input") as mock_input:
            cmd_delete(
                argparse.Namespace(tasks=["buy milk"], yes=False), lambda **_: client, active_config
            )

        mock_input.assert_not_called()

    def test_delete_GIVEN_batch_with_one_fragment_THEN_one_prompt_listing_all(
        self, client: Mock, active_config: Config
    ) -> None:
        args = argparse.Namespace(tasks=["Buy milk", "dent"], yes=False)

        with patch("builtins.input", return_value="yes") as mock_input:
            cmd_delete(args, lambda **_: client, active_config)

        mock_input.assert_called_once_with(
            "Delete 2 tasks (Buy milk, Call dentist) from Work? [y/N] "
        )

    def test_delete_GIVEN_eof_at_prompt_THEN_cancelled_exit_130(
        self, tmp_path: Path, capsys: CaptureFixture
    ) -> None:
        """End to end through main(): EOF (e.g. piped input) cancels, nothing is deleted."""
        from gtasks.app import main

        client = Mock()
        client.get_tasklist.return_value = {"id": "list1", "title": "Work"}
        client.get_tasks.return_value = self.TASKS
        with (
            patch("gtasks.app.build_client", return_value=client),
            patch("builtins.input", side_effect=EOFError),
        ):
            assert main(["delete", "milk"]) == 130

        client.delete_tasks.assert_not_called()
