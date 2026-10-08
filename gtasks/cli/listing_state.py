"""Remembers the last task listing shown, so display numbers stay stable.

`gtasks done 3` must act on the task that was 3rd when the user last looked, not the 3rd
task in whatever the API returns now (another device may have added or completed tasks
since). `gtasks tasks` records the (id, title) of each row it printed; `done`/`delete`
resolve numbers against that record and mark the rows they consume so a repeated
`delete 1` fails clearly instead of hitting a stale ID.

Deliberately separate from the cache (`client/cache_store.py`): the cache tracks what's
current and changes under writes, refetches and expiry, while this freezes what was shown.
It shares the cache's folder and file conventions (`utils/json_files.py`) and is cleared with
it. Not per account: it's keyed by list ID, and IDs never match across accounts.
"""

from pathlib import Path
from typing import Any, TypedDict, TypeIs, cast

from gtasks import defaults
from gtasks.utils.json_files import read_json, write_json

SCHEMA_VERSION = "1.0.0"
LISTING_FILE_NAME = "listing.json"


class ListingRow(TypedDict):
    id: str
    title: str


def _is_row(row: object) -> bool:
    """A recorded row, or None for one already consumed."""
    if row is None:
        return True
    return isinstance(row, dict) and isinstance(cast(dict[str, object], row).get("id"), str)


def _is_rows(value: object) -> TypeIs[list[ListingRow | None]]:
    return isinstance(value, list) and all(_is_row(row) for row in value)


class ListingState:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._path = root / LISTING_FILE_NAME

    @classmethod
    def default(cls) -> "ListingState":
        """The listing in the cache folder (read at call time, so tests can redirect it)."""
        return cls(defaults.CACHE_DIR)

    def save(self, tasklist_id: str, tasks: list) -> None:
        rows = [{"id": t["id"], "title": t.get("title", "")} for t in tasks if t.get("id")]
        self._write(tasklist_id, rows)

    def rows(self, tasklist_id: str) -> list[ListingRow | None] | None:
        """Rows of the last listing of `tasklist_id`, or None if it wasn't the last one shown.

        A consumed row (already completed/deleted via its number) is None.
        """
        doc = read_json(self._path, SCHEMA_VERSION)
        rows = doc.get("rows")
        if doc.get("tasklist_id") != tasklist_id or not _is_rows(rows):
            return None
        return rows

    def consume(self, tasklist_id: str, task_ids: list[str]) -> None:
        """Mark rows whose task was just completed or deleted."""
        rows = self.rows(tasklist_id)
        if rows is None:
            return
        gone = set(task_ids)
        self._write(tasklist_id, [None if r and r["id"] in gone else r for r in rows])

    def _write(self, tasklist_id: str, rows: list[Any]) -> None:
        write_json(
            self._path, {"tasklist_id": tasklist_id, "rows": rows}, SCHEMA_VERSION, root=self._root
        )
