"""Remembers the last task listing shown, so display numbers stay stable.

`gtasks done 3` must act on the task that was 3rd when the user last looked, not the 3rd
task in whatever the API returns now (another device may have added or completed tasks
since). `gtasks tasks` records the (id, title) of each row it printed; `done`/`delete`
resolve numbers against that record and mark the rows they consume so a repeated
`delete 1` fails clearly instead of hitting a stale ID.

Stored as JSON next to config.toml. This is app-managed state, not user configuration.
"""

import json
from pathlib import Path
from typing import TypedDict

from gtasks.utils.config import Config

STATE_FILE_NAME = "state.json"


class ListingRow(TypedDict):
    id: str
    title: str


class ListingState:
    def __init__(self, path: Path) -> None:
        self._path = path

    @classmethod
    def beside(cls, cfg: Config) -> "ListingState":
        """The state file that lives in the same directory as `cfg`."""
        return cls(cfg.path.parent / STATE_FILE_NAME)

    def save(self, tasklist_id: str, tasks: list) -> None:
        rows = [{"id": t["id"], "title": t.get("title", "")} for t in tasks if t.get("id")]
        self._write({"last_listing": {"tasklist_id": tasklist_id, "rows": rows}})

    def rows(self, tasklist_id: str) -> list[ListingRow | None] | None:
        """Rows of the last listing of `tasklist_id`, or None if it wasn't the last one shown.

        A consumed row (already completed/deleted via its number) is None.
        """
        listing = self._read().get("last_listing")
        if not listing or listing.get("tasklist_id") != tasklist_id:
            return None
        return listing.get("rows", [])

    def consume(self, tasklist_id: str, task_ids: list[str]) -> None:
        """Mark rows whose task was just completed or deleted."""
        data = self._read()
        listing = data.get("last_listing")
        if not listing or listing.get("tasklist_id") != tasklist_id:
            return
        gone = set(task_ids)
        listing["rows"] = [None if r and r["id"] in gone else r for r in listing["rows"]]
        self._write(data)

    def _read(self) -> dict:
        try:
            return json.loads(self._path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(data))
