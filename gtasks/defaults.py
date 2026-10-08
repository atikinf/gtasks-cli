"""Where gtasks keeps its files, and the environment settings it reads.

Read the directories as `defaults.CONFIG_DIR` / `defaults.CACHE_DIR` (or through the functions
below) at call time, never `from gtasks.defaults import ...`: `tests/conftest.py` overrides
both, so no test touches the real ~/.config or ~/.cache.
"""

import os
from pathlib import Path

# Names the list to act on for one shell (overridden by -l, overrides the active list).
ENV_VAR = "GTASKS_LIST"


def _app_dir(xdg_var: str, fallback: str) -> Path:
    return Path(os.environ.get(xdg_var) or Path.home() / fallback) / "gtasks-cli"


# Settings and sign-in: configuration the user would back up.
CONFIG_DIR: Path = _app_dir("XDG_CONFIG_HOME", ".config")
# Everything gtasks manages itself (cache, last listing): disposable.
CACHE_DIR: Path = _app_dir("XDG_CACHE_HOME", ".cache")

CONFIG_FILE_NAME = "config.ini"
# What the config file was called before; renamed on first use (`Config.default`).
LEGACY_CONFIG_FILE_NAME = "config.toml"


def config_file() -> Path:
    return CONFIG_DIR / CONFIG_FILE_NAME


def token_file() -> Path:
    """The saved Google sign-in, in Google's authorized-user JSON format."""
    return CONFIG_DIR / "token.json"


def credentials_file() -> Path:
    """User-supplied OAuth client secrets (optional; `gtasks auth` takes them inline)."""
    return CONFIG_DIR / "credentials.json"
