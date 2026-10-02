import argparse
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli.cli import build_parser
from gtasks.cli.errors import Cancelled, CliError
from gtasks.cli.tasklist_resolution import (
    ENV_VAR,
    TargetList,
    choose_tasklist,
    resolve_target_tasklist,
)
from gtasks.utils.config import LEGACY_DEFAULT_TASKLIST_KEY, Config, ConfigKey

WORK = {"id": "list1", "title": "Work"}
WORK_DUPE = {"id": "list2", "title": "Work"}
DEFAULT = {"id": "default-id", "title": "My Tasks"}


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(tmp_path / "config.toml", ConfigParser())


@pytest.fixture
def mock_client() -> Mock:
    client = Mock()
    client.get_tasklist.return_value = DEFAULT
    return client


def _args(tasklist_title: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(tasklist_title=tasklist_title)


class TestResolveTargetTasklist:
    def test_GIVEN_flag_THEN_resolves_title_with_canonical_casing(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.resolve_tasklist_from_title.return_value = [WORK]

        result = resolve_target_tasklist(_args("work"), mock_client, config, environ={})

        assert result == TargetList("list1", "Work")
        mock_client.resolve_tasklist_from_title.assert_called_once_with("work")

    def test_GIVEN_flag_and_env_and_active_THEN_flag_wins(
        self, mock_client: Mock, config: Config
    ) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "active-id")
        mock_client.resolve_tasklist_from_title.return_value = [WORK]

        resolve_target_tasklist(_args("Work"), mock_client, config, environ={ENV_VAR: "Home"})

        mock_client.resolve_tasklist_from_title.assert_called_once_with("Work")

    def test_GIVEN_env_and_active_THEN_env_wins(self, mock_client: Mock, config: Config) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "active-id")
        mock_client.resolve_tasklist_from_title.return_value = [WORK]

        result = resolve_target_tasklist(_args(), mock_client, config, environ={ENV_VAR: "Work"})

        assert result.id == "list1"

    def test_GIVEN_active_list_THEN_uses_stored_id_without_api_call(
        self, mock_client: Mock, config: Config
    ) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "active-id")
        config.set(ConfigKey.ACTIVE_TASKLIST_TITLE, "Groceries")

        result = resolve_target_tasklist(_args(), mock_client, config, environ={})

        assert result == TargetList("active-id", "Groceries")
        assert mock_client.mock_calls == []

    def test_GIVEN_nothing_set_THEN_falls_back_to_account_default(
        self, mock_client: Mock, config: Config
    ) -> None:
        result = resolve_target_tasklist(_args(), mock_client, config, environ={})

        assert result == TargetList("default-id", "My Tasks")
        mock_client.get_tasklist.assert_called_once_with("@default")

    def test_GIVEN_unknown_title_THEN_raises_cli_error(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.resolve_tasklist_from_title.return_value = []

        with pytest.raises(CliError, match="No task list named 'Nope'"):
            resolve_target_tasklist(_args("Nope"), mock_client, config, environ={})


class TestLegacyMigration:
    @pytest.fixture
    def legacy_config(self, tmp_path: Path) -> Config:
        path = tmp_path / "config.toml"
        path.write_text(f"[DEFAULT]\n{LEGACY_DEFAULT_TASKLIST_KEY} = work\n")
        return Config(path, ConfigParser())

    def test_GIVEN_legacy_title_THEN_stores_id_and_drops_legacy_key(
        self, mock_client: Mock, legacy_config: Config
    ) -> None:
        mock_client.resolve_tasklist_from_title.return_value = [WORK]

        result = resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert result == TargetList("list1", "Work")
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list1"
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "Work"
        assert legacy_config.get_raw(LEGACY_DEFAULT_TASKLIST_KEY) is None

    def test_GIVEN_legacy_title_no_longer_exists_THEN_warns_and_uses_default(
        self, mock_client: Mock, legacy_config: Config, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.resolve_tasklist_from_title.return_value = []

        result = resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert result.id == "default-id"
        assert "no longer exists" in capsys.readouterr().err
        assert legacy_config.get_raw(LEGACY_DEFAULT_TASKLIST_KEY) is None
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_ID) is None

    def test_GIVEN_legacy_title_is_ambiguous_THEN_prompts_once_and_stores_choice(
        self, mock_client: Mock, legacy_config: Config
    ) -> None:
        mock_client.resolve_tasklist_from_title.return_value = [WORK, WORK_DUPE]

        with patch("builtins.input", return_value="2") as mock_input:
            resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})
            resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert mock_input.call_count == 1
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list2"

    def test_GIVEN_ambiguous_legacy_prompt_cancelled_THEN_keeps_legacy_key(
        self, mock_client: Mock, legacy_config: Config
    ) -> None:
        mock_client.resolve_tasklist_from_title.return_value = [WORK, WORK_DUPE]

        with patch("builtins.input", return_value="q"), pytest.raises(Cancelled):
            resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert legacy_config.get_raw(LEGACY_DEFAULT_TASKLIST_KEY) == "work"


class TestChooseTasklist:
    def test_GIVEN_single_match_THEN_returns_without_prompting(self) -> None:
        mock_input = Mock()

        assert choose_tasklist([WORK], "Work", mock_input) == WORK
        mock_input.assert_not_called()

    def test_GIVEN_duplicates_THEN_prompts(self) -> None:
        assert choose_tasklist([WORK, WORK_DUPE], "Work", Mock(return_value="2")) == WORK_DUPE

    def test_GIVEN_duplicates_and_cancel_THEN_raises_cancelled(self) -> None:
        with pytest.raises(Cancelled):
            choose_tasklist([WORK, WORK_DUPE], "Work", Mock(return_value="q"))


class TestTasklistOption:
    @pytest.mark.parametrize(
        "argv",
        [
            ["-l", "Work", "done", "1"],
            ["done", "1", "-l", "Work"],
            ["done", "1", "--list", "Work"],
            ["-l", "Work"],
        ],
        ids=["before-subcommand", "after-subcommand", "long-form", "bare"],
    )
    def test_GIVEN_list_flag_anywhere_THEN_parsed(self, argv: list[str]) -> None:
        assert build_parser().parse_args(argv).tasklist_title == "Work"

    def test_GIVEN_no_list_flag_THEN_none(self) -> None:
        assert build_parser().parse_args(["done", "1"]).tasklist_title is None
