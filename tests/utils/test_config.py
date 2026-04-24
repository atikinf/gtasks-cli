from configparser import ConfigParser
from pathlib import Path

import pytest

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
        manager.set(ConfigKey.DEFAULT_TASKLIST_TITLE, LIST_TITLE)

        assert manager.get(ConfigKey.DEFAULT_TASKLIST_TITLE) == LIST_TITLE

    def test_set_GIVEN_custom_section_THEN_stores_in_section(self, manager: Config) -> None:
        manager.set(ConfigKey.DEFAULT_TASKLIST_TITLE, LIST_TITLE, section=CUSTOM_SECTION)

        assert manager.get(ConfigKey.DEFAULT_TASKLIST_TITLE, section=CUSTOM_SECTION) == LIST_TITLE

    def test_set_GIVEN_existing_value_THEN_overwrites(self, manager: Config) -> None:
        manager.set(ConfigKey.DEFAULT_TASKLIST_TITLE, "old_title")
        manager.set(ConfigKey.DEFAULT_TASKLIST_TITLE, LIST_TITLE)

        assert manager.get(ConfigKey.DEFAULT_TASKLIST_TITLE) == LIST_TITLE

    def test_set_THEN_persists_to_disk(self, manager: Config, config_path: Path) -> None:
        manager.set(ConfigKey.DEFAULT_TASKLIST_TITLE, LIST_TITLE)

        assert config_path.exists()
        assert LIST_TITLE in config_path.read_text()

    def test_set_GIVEN_nested_path_THEN_creates_parent_dirs(self, tmp_path: Path) -> None:
        nested_path = tmp_path / "nested" / "dir" / "config.toml"
        manager = Config(nested_path, ConfigParser())

        manager.set(ConfigKey.DEFAULT_TASKLIST_TITLE, LIST_TITLE)

        assert nested_path.exists()
        assert manager.get(ConfigKey.DEFAULT_TASKLIST_TITLE) == LIST_TITLE


class TestGetConfig:
    def test_get_GIVEN_nonexistent_section_THEN_returns_none(self, manager: Config) -> None:
        result = manager.get(ConfigKey.DEFAULT_TASKLIST_TITLE, section="nonexistent")

        assert result is None

    def test_get_GIVEN_existing_config_THEN_loads_value(self, config_path: Path) -> None:
        config_path.write_text("[DEFAULT]\ndefault_tasklist = PreExisting\n")

        manager = Config(config_path, ConfigParser())

        assert manager.get(ConfigKey.DEFAULT_TASKLIST_TITLE) == "PreExisting"


class TestGetAll:
    def test_get_all_GIVEN_no_values_set_THEN_all_none(self, manager: Config) -> None:
        result = manager.get_all()

        assert result == {ConfigKey.DEFAULT_TASKLIST_TITLE: None}

    def test_get_all_GIVEN_value_set_THEN_returns_it(self, manager: Config) -> None:
        manager.set(ConfigKey.DEFAULT_TASKLIST_TITLE, LIST_TITLE)

        result = manager.get_all()

        assert result[ConfigKey.DEFAULT_TASKLIST_TITLE] == LIST_TITLE
