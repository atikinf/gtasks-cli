from configparser import ConfigParser
from pathlib import Path

import pytest

from gtasks.utils.config import Config

LIST_TITLE = "ToDo"
CUSTOM_SECTION = "work"


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    return tmp_path / "config.toml"


@pytest.fixture
def manager(config_path: Path) -> Config:
    parser = ConfigParser()
    return Config(config_path, parser)


class TestSetTasklist:
    def test_set_tasklist_title_GIVEN_default_section_THEN_stores_title(
        self, manager: Config
    ) -> None:
        manager.set_tasklist_title(LIST_TITLE)

        assert manager.get_tasklist_title() == LIST_TITLE

    def test_set_tasklist_title_GIVEN_custom_section_THEN_stores_in_section(
        self, manager: Config
    ) -> None:
        manager.set_tasklist_title(LIST_TITLE, section=CUSTOM_SECTION)

        assert manager.get_tasklist_title(section=CUSTOM_SECTION) == LIST_TITLE

    def test_set_tasklist_title_GIVEN_existing_value_THEN_overwrites(
        self, manager: Config
    ) -> None:
        manager.set_tasklist_title("old_title")
        manager.set_tasklist_title(LIST_TITLE)

        assert manager.get_tasklist_title() == LIST_TITLE

    def test_set_tasklist_title_THEN_persists_to_disk(
        self, manager: Config, config_path: Path
    ) -> None:
        manager.set_tasklist_title(LIST_TITLE)

        assert config_path.exists()
        content = config_path.read_text()
        assert LIST_TITLE in content


class TestGetTasklist:
    def test_get_tasklist_title_GIVEN_nonexistent_section_THEN_returns_none(
        self, manager: Config
    ) -> None:
        result = manager.get_tasklist_title(section="nonexistent")

        assert result is None

    def test_get_tasklist_title_GIVEN_existing_config_THEN_loads_value(
        self, config_path: Path
    ) -> None:
        # Pre-populate config file
        config_path.write_text("[DEFAULT]\ndefault_tasklist_title = PreExisting\n")

        manager = Config(config_path, ConfigParser())

        assert manager.get_tasklist_title() == "PreExisting"

    def test_set_tasklist_title_GIVEN_nested_path_THEN_creates_parent_dirs(
        self, tmp_path: Path
    ) -> None:
        nested_path = tmp_path / "nested" / "dir" / "config.toml"
        manager = Config(nested_path, ConfigParser())

        manager.set_tasklist_title(LIST_TITLE)

        assert nested_path.exists()
        assert manager.get_tasklist_title() == LIST_TITLE


# class TestSaveConfig:
#     def test_save_GIVEN_valid_path_THEN_creates_parent_dirs_and_writes(
#         self, tmp_path: Path
#     ):
#         config_path = tmp_path / "nested" / "dir" / "config.toml"
#         parser = ConfigParser()
#         prompter = Prompter()
#         manager = Config(config_path, parser, prompter)
#         manager._parser["section"] = {"key": "value"}

#         manager._save()

#         assert config_path.exists()
#         saved_content = config_path.read_text()
#         assert "[section]" in saved_content
#         assert "key = value" in saved_content
