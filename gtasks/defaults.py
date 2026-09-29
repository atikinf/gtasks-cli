from pathlib import Path

APP_CFG_PATH: Path = Path(
    "~/.config/gtasks-cli"
).expanduser()  # everything sits in here
CONFIG_FILE_NAME: str = "config.toml"

CONFIG_FILE_PATH: Path = APP_CFG_PATH / CONFIG_FILE_NAME
