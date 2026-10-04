import os
from pathlib import Path

APP_CFG_PATH: Path = Path(
    "~/.config/gtasks-cli"
).expanduser()  # config, sign-in token and listing state
CONFIG_FILE_NAME: str = "config.toml"

CONFIG_FILE_PATH: Path = APP_CFG_PATH / CONFIG_FILE_NAME

# Disposable data (safe to delete) lives apart from config and the sign-in token.
CACHE_DIR: Path = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "gtasks-cli"
)
