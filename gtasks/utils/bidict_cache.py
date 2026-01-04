import json
from pathlib import Path

from bidict import bidict
from bidict._exc import DuplicationError

# Default config directory: ~/.config/gtasks-cli/
CONFIG_DIR: Path = Path("~/.config/gtasks-cli").expanduser()


class BidictCache[K, V]:
    ERR_PARSE_JSON = "Failure parsing cached JSON"
    ERR_DUPLICATE_KEY_VALUE = "Duplicate key or value detected in cached JSON"

    def __init__(
        self,
        cache_path: Path = CONFIG_DIR / "cache.json",
    ) -> None:
        self._bidict: bidict[K, V] = bidict()
        self._cache_path: Path = cache_path.expanduser()
        self.load()

    def get_forward(self, key: K) -> V:
        return self._bidict[key]

    def get_backward(self, val: V) -> K:
        return self._bidict.inv[val]

    def update_from_items(self, items: dict[K, V]) -> None:
        self._bidict.update(items)

    def save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cache_path.open(mode="w", encoding="utf-8") as f:
            json.dump(obj=dict(self._bidict), fp=f, indent=2, ensure_ascii=False)

    def load(self):
        if not self._cache_path.exists():
            self.clear()
            return

        try:
            with self._cache_path.open(mode="r", encoding="utf-8") as f:
                self._bidict: bidict[str, str] = bidict(json.load(fp=f))
        except (json.JSONDecodeError, OSError, TypeError) as e:
            raise ValueError(self.ERR_PARSE_JSON) from e
        except DuplicationError as e:
            raise ValueError(self.ERR_DUPLICATE_KEY_VALUE) from e

    def clear(self) -> None:
        self._bidict: bidict[K, V] = bidict()
        self.save()

    def __len__(self) -> int:
        return len(self._bidict)
