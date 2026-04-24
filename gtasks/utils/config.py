from configparser import ConfigParser
from enum import Enum
from pathlib import Path

DEFAULT_SECTION: str = "DEFAULT"


class ConfigKey(Enum):
    DEFAULT_TASKLIST_TITLE = "default_tasklist"


class Config:
    """Simple config file manager."""

    def __init__(
        self,
        config_path: Path,
        parser: ConfigParser = ConfigParser(),
    ) -> None:
        self._config_path: Path = config_path.expanduser()
        self._parser: ConfigParser = parser

        if self._config_path.exists():
            self._parser.read(self._config_path)

    def get(self, key: ConfigKey, section: str = DEFAULT_SECTION) -> str | None:
        if section not in self._parser:
            return None
        return self._parser[section].get(key.value)

    def set(self, key: ConfigKey, value: str, section: str = DEFAULT_SECTION) -> None:
        if section not in self._parser:
            self._parser[section] = {}
        self._parser[section][key.value] = value
        self._save()

    def get_all(self, section: str = DEFAULT_SECTION) -> dict[ConfigKey, str | None]:
        return {key: self.get(key, section) for key in ConfigKey}

    def _save(self) -> None:
        """Write current config to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w") as f:
            self._parser.write(f)
