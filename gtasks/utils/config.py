from configparser import ConfigParser
from enum import Enum
from pathlib import Path

DEFAULT_SECTION: str = "DEFAULT"


class ConfigKey(Enum):
    ACTIVE_TASKLIST_ID = "active_tasklist_id"
    ACTIVE_TASKLIST_TITLE = "active_tasklist_title"


# Pre-ID versions stored the active list by title under this key. Read once and migrated
# by tasklist_resolution; never written.
LEGACY_DEFAULT_TASKLIST_KEY = "default_tasklist"


class Config:
    """Simple config file manager."""

    def __init__(
        self,
        config_path: Path,
        parser: ConfigParser | None = None,
    ) -> None:
        self._config_path: Path = config_path.expanduser()
        self._parser: ConfigParser = parser if parser is not None else ConfigParser()

        if self._config_path.exists():
            self._parser.read(self._config_path)

    @property
    def path(self) -> Path:
        return self._config_path

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

    def get_raw(self, name: str, section: str = DEFAULT_SECTION) -> str | None:
        """Read a key that isn't (or is no longer) a ConfigKey."""
        if section not in self._parser:
            return None
        return self._parser[section].get(name)

    def pop_raw(self, name: str, section: str = DEFAULT_SECTION) -> str | None:
        """Remove and return a key that isn't (or is no longer) a ConfigKey."""
        if section not in self._parser or name not in self._parser[section]:
            return None
        value = self._parser[section].pop(name)
        self._save()
        return value

    def _save(self) -> None:
        """Write current config to disk."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w") as f:
            self._parser.write(f)
