from configparser import ConfigParser
from pathlib import Path

from gtasks.utils.prompter import Prompter


class ConfigManager:
    def __init__(
        self,
        config_path: Path,
        parser: ConfigParser,
        prompter: Prompter,
    ) -> None:
        assert config_path is not None
        assert parser is not None
        assert prompter is not None

        self._config_path: Path = config_path.expanduser()
        self._parser: ConfigParser = parser
        self._prompter: Prompter = prompter

        if self._config_path.exists():
            self._parser.read(self._config_path)

    def set_default_tasklist(self, available_lists: list[dict]) -> str | None:
        """Interactively set a default task list and persist it to config.

        Args:
            available_lists: List of tasklist dicts with 'id' and 'title' keys.

        Returns:
            The selected tasklist ID, or None if aborted.
        """
        if not available_lists:
            print("No task lists available.")
            return None

        current_default_title: str | None = None
        if self._parser.has_option("defaults", "default_tasklist_title"):
            current_default_title = self._parser.get(
                "defaults", "default_tasklist_title"
            )

        print("Available task lists:")
        for idx, tlist in enumerate(available_lists, start=1):
            title: str = tlist.get("title", "<untitled>")
            marker: str = " [current]" if title == current_default_title else ""
            print(f"  {idx}. {title}{marker}")

        choice_idx: int | None = self._prompter.prompt_index_choice(
            len(available_lists),
            "Select a default task list (number, or 'q' to quit): ",
        )

        if choice_idx is None:
            print("Aborted setting default task list.")
            return None

        selected = available_lists[choice_idx]
        selected_id: str = selected["id"]
        selected_title: str = selected.get("title", "")

        if "defaults" not in self._parser:
            self._parser["defaults"] = {}

        self._parser["defaults"]["default_tasklist_title"] = selected_title

        self._save()

        print(f"Default task list set to '{selected_title}'.")
        return selected_id

    def get_default_tasklist(self) -> str:
        raise NotImplementedError()

    def _save(self) -> None:
        """Write current config to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w") as f:
            self._parser.write(f)
