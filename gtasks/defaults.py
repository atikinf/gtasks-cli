import os
from pathlib import Path

APP_CFG_PATH: Path = Path(
    "~/.config/gtasks-cli"
).expanduser()  # settings and sign-in only
CONFIG_FILE_NAME: str = "config.toml"

CONFIG_FILE_PATH: Path = APP_CFG_PATH / CONFIG_FILE_NAME

# Everything gtasks manages itself (cache, last listing) is disposable and lives apart.
CACHE_DIR: Path = (
    Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "gtasks-cli"
)
