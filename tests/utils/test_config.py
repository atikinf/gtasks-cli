import subprocess
import sys
from configparser import ConfigParser
from pathlib import Path

import pytest

from gtasks import defaults
from gtasks.utils.config import Config, ConfigKey

LIST_TITLE = "ToDo"
CUSTOM_SECTION = "work"


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.toml"


@pytest.fixture
def manager(config_path: Path) -> Config:
    parser = ConfigParser()
    return Config(config_path, parser)


class TestSetConfig:
    def test_set_GIVEN_default_section_THEN_stores_value(self, manager: Config) -> None:
        manager.set(ConfigKey.ACTIVE_TASKLIST_TITLE, LIST_TITLE)

        assert manager.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == LIST_TITLE

    def test_set_GIVEN_custom_section_THEN_stores_in_section(self, manager: Config) -> None:
        manager.set(ConfigKey.ACTIVE_TASKLIST_TITLE, LIST_TITLE, section=CUSTOM_SECTION)

        assert manager.get(ConfigKey.ACTIVE_TASKLIST_TITLE, section=CUSTOM_SECTION) == LIST_TITLE

    def test_set_GIVEN_existing_value_THEN_overwrites(self, manager: Config) -> None:
        manager.set(ConfigKey.ACTIVE_TASKLIST_TITLE, "old_title")
        manager.set(ConfigKey.ACTIVE_TASKLIST_TITLE, LIST_TITLE)

        assert manager.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == LIST_TITLE

    def test_set_THEN_persists_to_disk(self, manager: Config, config_path: Path) -> None:
        manager.set(ConfigKey.ACTIVE_TASKLIST_TITLE, LIST_TITLE)

        assert config_path.exists()
        assert LIST_TITLE in config_path.read_text()

    def test_set_GIVEN_nested_path_THEN_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested_path = tmp_path / "nested" / "dir" / "config.toml"
        manager = Config(nested_path, ConfigParser())

        manager.set(ConfigKey.ACTIVE_TASKLIST_TITLE, LIST_TITLE)

        assert nested_path.exists()
        assert manager.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == LIST_TITLE


class TestGetConfig:
    def test_get_GIVEN_nonexistent_section_THEN_returns_none(self, manager: Config) -> None:
        result = manager.get(ConfigKey.ACTIVE_TASKLIST_TITLE, section="nonexistent")

        assert result is None

    def test_get_GIVEN_existing_config_THEN_loads_value(self, config_path: Path) -> None:
        config_path.write_text("[DEFAULT]\nactive_tasklist_title = PreExisting\n")

        manager = Config(config_path, ConfigParser())

        assert manager.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "PreExisting"


class TestRawKeys:
    def test_get_raw_GIVEN_legacy_key_on_disk_THEN_returns_it(self, config_path: Path) -> None:
        config_path.write_text("[DEFAULT]\ndefault_tasklist = Old\n")

        manager = Config(config_path, ConfigParser())

        assert manager.get_raw("default_tasklist") == "Old"

    def test_pop_raw_GIVEN_key_present_THEN_removes_and_persists(self, config_path: Path) -> None:
        config_path.write_text("[DEFAULT]\ndefault_tasklist = Old\n")
        manager = Config(config_path, ConfigParser())

        assert manager.pop_raw("default_tasklist") == "Old"

        assert manager.get_raw("default_tasklist") is None
        assert "default_tasklist" not in config_path.read_text()

    def test_pop_raw_GIVEN_key_missing_THEN_returns_none(self, manager: Config) -> None:
        assert manager.pop_raw("default_tasklist") is None


class TestParserIsolation:
    def test_init_GIVEN_no_parser_THEN_instances_do_not_share_state(self, tmp_path: Path) -> None:
        first = Config(tmp_path / "a.toml")
        second = Config(tmp_path / "b.toml")

        first.set(ConfigKey.ACTIVE_TASKLIST_TITLE, LIST_TITLE)

        assert second.get(ConfigKey.ACTIVE_TASKLIST_TITLE) is None


class TestDefaultConfig:
    def test_default_GIVEN_legacy_config_toml_THEN_renamed_to_ini_with_contents(self) -> None:
        legacy = defaults.CONFIG_DIR / defaults.LEGACY_CONFIG_FILE_NAME
        legacy.parent.mkdir(parents=True)
        legacy.write_text("[DEFAULT]\ncache = off\n")

        config = Config.default()

        assert config.get(ConfigKey.CACHE) == "off"
        assert config.path == defaults.config_file()
        assert defaults.config_file().exists()
        assert not legacy.exists()

    def test_default_GIVEN_both_files_THEN_ini_wins_and_legacy_untouched(self) -> None:
        legacy = defaults.CONFIG_DIR / defaults.LEGACY_CONFIG_FILE_NAME
        legacy.parent.mkdir(parents=True)
        legacy.write_text("[DEFAULT]\ncache = off\n")
        defaults.config_file().write_text("[DEFAULT]\ncache = on\n")

        assert Config.default().get(ConfigKey.CACHE) == "on"
        assert legacy.exists()

    def test_default_GIVEN_no_file_THEN_empty_config_at_ini_path(self) -> None:
        config = Config.default()

        assert config.path == defaults.config_file()
        assert config.get(ConfigKey.CACHE) is None


class TestConfigDir:
    def test_GIVEN_xdg_config_home_THEN_config_dir_under_it(self, tmp_path: Path) -> None:
        # In a subprocess: the test process's `defaults` is already imported (and overridden).
        code = "from gtasks import defaults; print(defaults.CONFIG_DIR)"
        env = {"XDG_CONFIG_HOME": str(tmp_path), "HOME": str(tmp_path / "home")}
        out = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True,
            env=env,
        ).stdout.strip()

        assert out == str(tmp_path / "gtasks-cli")

