from configparser import ConfigParser
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from pytest import CaptureFixture

from gtasks.utils.config_manager import ConfigManager
from gtasks.utils.prompter import Prompter


class TestInitConfigManager:
    def test_init_GIVEN_valid_path_THEN_success(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        parser = ConfigParser()
        prompter = Prompter()

        ConfigManager(config_path, parser, prompter)

    def test_init_GIVEN_existing_config_THEN_loads_config(self, tmp_path: Path):
        config_path = tmp_path / "config.toml"
        config_path.write_text("[defaults]\ndefault_tasklist_title = My Tasks\n")
        parser: ConfigParser = create_autospec(
            ConfigParser, spec_set=True, instance=True
        )
        prompter = Prompter()

        ConfigManager(config_path, parser, prompter)

        parser.read.assert_called_once_with(config_path)

    def test_init_GIVEN_tilde_path_THEN_expands_user(self):
        parser = ConfigParser()
        prompter = Prompter()
        config_path = Path("~/config.toml")

        manager = ConfigManager(config_path, parser, prompter)

        assert "~" not in str(manager._config_path)
        assert manager._config_path == config_path.expanduser()


class TestSetDefaultTasklist:
    LIST1_ID = "list1"
    LIST2_ID = "list2"
    LIST3_ID = "list3"
    LIST2_TITLE = "Personal"
    LIST1_TITLE = "ToDo"
    LIST3_TITLE = "Shopping"

    @pytest.fixture
    def manager(self, tmp_path: Path) -> ConfigManager:
        config_path: Path = tmp_path / "config.toml"
        parser = ConfigParser()
        prompter: Prompter = create_autospec(Prompter, spec_set=True, instance=True)
        prompter.prompt_index_choice.return_value = 0
        return ConfigManager(config_path, parser, prompter)

    @pytest.fixture
    def available_lists(self) -> list[dict]:
        return [
            {"id": self.LIST1_ID, "title": self.LIST1_TITLE},
            {"id": self.LIST2_ID, "title": self.LIST2_TITLE},
            {"id": self.LIST3_ID, "title": self.LIST3_TITLE},
        ]

    def test_set_default_tasklist_GIVEN_empty_lists_THEN_returns_none(
        self, manager: ConfigManager, capsys: CaptureFixture[str]
    ):
        result: str | None = manager.set_default_tasklist([])

        assert result is None
        captured = capsys.readouterr()
        assert "No task lists available" in captured.out

    def test_set_default_tasklist_GIVEN_user_quits_THEN_returns_none(
        self, tmp_path: Path, available_lists: list[dict], capsys: CaptureFixture[str]
    ):
        config_path = tmp_path / "config.toml"
        parser = ConfigParser()
        prompter: Prompter = create_autospec(Prompter, spec_set=True, instance=True)
        prompter.prompt_index_choice.return_value = None
        manager = ConfigManager(config_path, parser, prompter)

        result: str | None = manager.set_default_tasklist(available_lists)

        assert result is None
        captured = capsys.readouterr()
        assert "Aborted" in captured.out

    def test_set_default_tasklist_GIVEN_valid_selection_THEN_saves_and_returns_id(
        self, tmp_path: Path, available_lists: list[dict], capsys: CaptureFixture[str]
    ):
        config_path = tmp_path / "config.toml"
        parser = ConfigParser()
        prompter: Prompter = create_autospec(Prompter, spec_set=True, instance=True)
        prompter.prompt_index_choice.return_value = 1
        manager = ConfigManager(config_path, parser, prompter)

        result: str | None = manager.set_default_tasklist(available_lists)

        assert result == self.LIST2_ID
        assert (
            manager._parser.get("defaults", "default_tasklist_title")
            == self.LIST2_TITLE
        )
        captured = capsys.readouterr()
        assert f"Default task list set to '{self.LIST2_TITLE}'" in captured.out

    def test_set_default_tasklist_GIVEN_valid_selection_THEN_persists_to_file(
        self, tmp_path: Path, available_lists: list[dict]
    ):
        config_path = tmp_path / "subdir" / "config.toml"
        parser = ConfigParser()
        prompter: Prompter = create_autospec(Prompter, spec_set=True, instance=True)
        prompter.prompt_index_choice.return_value = 0
        manager = ConfigManager(config_path, parser, prompter)

        manager.set_default_tasklist(available_lists)

        assert config_path.exists()
        saved_content = config_path.read_text()
        assert f"default_tasklist_title = {self.LIST1_TITLE}" in saved_content

    def test_set_default_tasklist_GIVEN_existing_default_THEN_shows_current_marker(
        self, tmp_path: Path, available_lists: list[dict], capsys: CaptureFixture[str]
    ):
        config_path = tmp_path / "config.toml"
        config_path.write_text(
            f"[defaults]\ndefault_tasklist_title = {self.LIST2_TITLE}\n"
        )
        parser = ConfigParser()
        prompter: Prompter = create_autospec(Prompter, spec_set=True, instance=True)
        prompter.prompt_index_choice.return_value = 0
        manager = ConfigManager(config_path, parser, prompter)

        manager.set_default_tasklist(available_lists)

        captured = capsys.readouterr()
        assert f"{self.LIST2_TITLE} [current]" in captured.out

    def test_set_default_tasklist_GIVEN_list_without_title_THEN_uses_untitled(
        self, tmp_path: Path, capsys: CaptureFixture[str]
    ):
        config_path = tmp_path / "config.toml"
        parser = ConfigParser()
        prompter: Prompter = create_autospec(Prompter, spec_set=True, instance=True)
        prompter.prompt_index_choice.return_value = 0
        manager = ConfigManager(config_path, parser, prompter)
        lists_with_missing_title = [{"id": self.LIST1_ID}]

        result = manager.set_default_tasklist(lists_with_missing_title)

        assert result == self.LIST1_ID
        captured = capsys.readouterr()
        assert "<untitled>" in captured.out


class TestSaveConfigManager:
    def test_save_GIVEN_valid_path_THEN_creates_parent_dirs_and_writes(
        self, tmp_path: Path
    ):
        config_path = tmp_path / "nested" / "dir" / "config.toml"
        parser = ConfigParser()
        prompter = Prompter()
        manager = ConfigManager(config_path, parser, prompter)
        manager._parser["section"] = {"key": "value"}

        manager._save()

        assert config_path.exists()
        saved_content = config_path.read_text()
        assert "[section]" in saved_content
        assert "key = value" in saved_content
