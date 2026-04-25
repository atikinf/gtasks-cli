import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task


class TasksCache:
    """Per-tasklist cache storing full task objects as JSON arrays on disk.

    One file per tasklist: {cache_dir}/{tasklist_id}.json
    Cache always stores ALL tasks (completed + needsAction); callers filter client-side.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._data: dict[str, list["Task"]] = {}
        self._load_all()

    def get(self, tasklist_id: str) -> list["Task"] | None:
        return self._data.get(tasklist_id)

    def set(self, tasklist_id: str, tasks: list["Task"]) -> None:
        self._data[tasklist_id] = tasks
        self._save(tasklist_id)

    def invalidate(self, tasklist_id: str) -> None:
        self._data.pop(tasklist_id, None)
        self._cache_path(tasklist_id).unlink(missing_ok=True)

    def clear(self) -> None:
        self._data.clear()
        if self._cache_dir.exists():
            for path in self._cache_dir.glob("*.json"):
                path.unlink()

    def _load_all(self) -> None:
        if not self._cache_dir.exists():
            return
        for path in self._cache_dir.glob("*.json"):
            try:
                with path.open(encoding="utf-8") as f:
                    self._data[path.stem] = json.load(f)
            except (json.JSONDecodeError, OSError):
                path.unlink(missing_ok=True)

    def _save(self, tasklist_id: str) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        with self._cache_path(tasklist_id).open("w", encoding="utf-8") as f:
            json.dump(self._data[tasklist_id], f, indent=2, ensure_ascii=False)

    def _cache_path(self, tasklist_id: str) -> Path:
        return self._cache_dir / f"{tasklist_id}.json"
