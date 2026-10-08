"""The `config` command."""

import argparse
from unittest.mock import Mock

import pytest
from pytest import CaptureFixture

from gtasks.cli.errors import CliError
from gtasks.cli.parsers.config_parser import cmd_config
from gtasks.utils.config import Config, ConfigKey

ACTIVE = {"id": "list1", "title": "Work"}


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
