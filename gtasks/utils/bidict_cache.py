import json
from pathlib import Path

from bidict import bidict
from bidict._exc import DuplicationError


class BidictCache[K, V](bidict[K, V]):
    ERR_PARSE_JSON = "Failure parsing cached JSON"
    ERR_DUPLICATE_KEY_VALUE = "Duplicate key or value detected in cached JSON"

    def __init__(self, cache_path: Path | None = None) -> None:
        super().__init__()

        if cache_path is not None:
            self._cache_path: Path = cache_path.expanduser()
            self.load()

    def clear_and_update(self, items: dict[K, V]) -> None:
        self.clear()
        self.update(items)

    def save(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cache_path.open(mode="w", encoding="utf-8") as f:
            json.dump(obj=dict(self), fp=f, indent=2, ensure_ascii=False)

    def load(self):
        if not self._cache_path.exists():
            self.clear()
            return

        try:
            with self._cache_path.open(mode="r", encoding="utf-8") as f:
                self.update(json.load(fp=f))
        except (json.JSONDecodeError, OSError, TypeError) as e:
            raise ValueError(self.ERR_PARSE_JSON) from e
        except DuplicationError as e:
            raise ValueError(self.ERR_DUPLICATE_KEY_VALUE) from e
