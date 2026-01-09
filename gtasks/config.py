from configparser import ConfigParser
from pathlib import Path

DEFAULT_SECTION: str = "DEFAULT"
DEFAULT_TASKLIST_TITLE: str = "default_tasklist_title"


class Config:
    def __init__(
        self,
        config_path: Path,
        parser: ConfigParser = ConfigParser(),
    ) -> None:
        self._config_path: Path = config_path.expanduser()
        self._parser: ConfigParser = parser

        if self._config_path.exists():
            self._parser.read(self._config_path)

    def set_tasklist_title(
        self, tasklist_title: str, section: str = DEFAULT_SECTION
    ) -> None:
        if section not in self._parser:
            self._parser[section] = {}

        self._parser[section][DEFAULT_TASKLIST_TITLE] = tasklist_title

        self._save()

    def get_tasklist_title(self, section: str = DEFAULT_SECTION) -> str | None:
        if section not in self._parser:
            return None

        return self._parser[section][DEFAULT_TASKLIST_TITLE]

    def _save(self) -> None:
        """Write current config to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w") as f:
            self._parser.write(f)
