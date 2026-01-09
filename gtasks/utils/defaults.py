from pathlib import Path

# Default config directory: ~/.config/gtasks-cli/
CONFIG_PATH: Path = Path("~/.config/gtasks-cli").expanduser()
CACHE_FILE_NAME: str = "config.toml"

CACHE_PATH: Path = CONFIG_PATH / CACHE_FILE_NAME
