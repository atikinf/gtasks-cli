from pathlib import Path

APP_CFG_PATH: Path = Path(
    "~/.config/gtasks-cli"
).expanduser()  # everything sits in here
CACHE_FILE_NAME: str = "cache.json"
CONFIG_FILE_NAME: str = "config.toml"

CACHE_FILE_PATH: Path = APP_CFG_PATH / CACHE_FILE_NAME
CONFIG_FILE_PATH: Path = APP_CFG_PATH / CONFIG_FILE_NAME
