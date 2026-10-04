"""On-disk cache of Google Tasks data: plain JSON files, one per task list.

Deliberately free of Google imports so it stays cheap to load (e.g. for shell completion,
which must not sign in or import the API client).

Layout under `<root>/<account key>/`:

    tasklists.json                 every list, plus the list `@default` resolved to
    lists/<sha256(id)[:32]>.json   one list's open (needsAction) tasks, in API order

Files follow the shared conventions in `utils/json_files.py` (semver schema, atomic private
writes, never raising into a command); stale data is a miss too.
"""

import hashlib
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeIs

from gtasks.utils.json_files import read_json, unlink_quietly, write_json

SCHEMA_VERSION = "1.0.0"
DEFAULT_TTL_SECONDS = 30 * 60
# A timestamp this far in the future (clock moved back, files copied between machines) is
# treated as stale rather than trusted for up to a TTL past "now".
_FUTURE_SLACK_SECONDS = 60

_TASKLISTS_FILE = "tasklists.json"
_LISTS_DIR = "lists"
_CURRENT_FILE = "current"

Tasks = list[dict[str, Any]]


def account_key(client_id: str | None, refresh_token: str | None) -> str:
    """A stable, non-reversible directory name for the signed-in account.

    Signing in as someone else (via `gtasks auth` or a `credentials.json` flow) yields a new
    refresh token, hence a new directory, so one account never sees another's cached data.
    """
    raw = f"{client_id or ''}\0{refresh_token or ''}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]


def clear_cache(root: Path) -> None:
    """Remove every account's cached data under `root`; a no-op if there is none."""
    shutil.rmtree(root, ignore_errors=True)


def _is_task_list(value: object) -> TypeIs[Tasks]:
    return isinstance(value, list) and all(isinstance(item, dict) for item in value)


class CacheStore:
    def __init__(
        self,
        root: Path,
        account: str,
        *,
        ttl: float = DEFAULT_TTL_SECONDS,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._root = root
        self._account = account
        self._dir = root / account
        self._ttl = ttl
        self._now = now
        self._pointed = False

    @classmethod
    def for_current_account(cls, root: Path) -> "CacheStore | None":
        """The store of the account that last wrote to the cache, found without credentials.

        For readers that must not sign in (shell completion). None if nothing was cached yet
        or the record is unreadable or malformed.
        """
        try:
            account = (root / _CURRENT_FILE).read_text().strip()
        except OSError:
            return None
        # It names a directory under `root`: accept only what account_key() produces.
        if not account or not all(c in "0123456789abcdef" for c in account):
            return None
        return cls(root, account)

    # --- Task lists ------------------------------------------------------------------------

    def read_tasklists(self) -> tuple[Tasks, float] | None:
        """Fresh task lists and when they were fetched, or None on any miss."""
        entry = self._fresh_entry("lists")
        items = entry.get("items")
        if not _is_task_list(items):
            return None
        return items, float(entry["fetched_at"])

    def write_tasklists(self, items: Tasks) -> None:
        self._update_tasklists_doc("lists", {"fetched_at": self._now(), "items": items})

    def read_default(self) -> dict[str, Any] | None:
        """The list `@default` last resolved to, if fresh."""
        item = self._fresh_entry("default").get("item")
        return item if isinstance(item, dict) and isinstance(item.get("id"), str) else None

    def write_default(self, tasklist: dict[str, Any]) -> None:
        self._update_tasklists_doc("default", {"fetched_at": self._now(), "item": tasklist})

    def drop_tasklists(self) -> None:
        unlink_quietly(self._dir / _TASKLISTS_FILE)

    # --- Tasks in one list -----------------------------------------------------------------

    def read_tasks(self, tasklist_id: str) -> tuple[Tasks, float] | None:
        """Fresh open tasks for a list and when they were fetched, or None on any miss."""
        doc = self._read(self._tasks_path(tasklist_id))
        if doc.get("tasklist_id") != tasklist_id:  # also guards against hash collisions
            return None
        fetched_at = self._fresh_time(doc.get("fetched_at"))
        tasks = doc.get("tasks")
        if fetched_at is None or not _is_task_list(tasks):
            return None
        return tasks, fetched_at

    def write_tasks(self, tasklist_id: str, tasks: Tasks) -> None:
        """Store a full fetch; this is the only way the list's timestamp moves forward."""
        self._write_tasks_doc(tasklist_id, tasks, self._now())

    def update_tasks(self, tasklist_id: str, change: Callable[[Tasks], Tasks | None]) -> None:
        """Apply a write-through edit, keeping the original fetch time.

        Edits must not reset the TTL, or a list edited often would never be refetched.
        `change` returns None when it can't edit safely; the cached copy is then dropped.
        """
        cached = self.read_tasks(tasklist_id)
        if cached is None:
            return
        tasks, fetched_at = cached
        changed = change(tasks)
        if changed is None:
            self.drop_tasks(tasklist_id)
        else:
            self._write_tasks_doc(tasklist_id, changed, fetched_at)

    def drop_tasks(self, tasklist_id: str) -> None:
        unlink_quietly(self._tasks_path(tasklist_id))

    # --- Internals -------------------------------------------------------------------------

    def _tasks_path(self, tasklist_id: str) -> Path:
        # IDs are base64-like and may contain `/` or `+`, so never use them as filenames.
        digest = hashlib.sha256(tasklist_id.encode()).hexdigest()[:32]
        return self._dir / _LISTS_DIR / f"{digest}.json"

    def _fresh_entry(self, key: str) -> dict[str, Any]:
        """A section of tasklists.json (`lists`, `default`) if it's fresh, else empty."""
        entry = self._read(self._dir / _TASKLISTS_FILE).get(key)
        if not isinstance(entry, dict) or self._fresh_time(entry.get("fetched_at")) is None:
            return {}
        return entry

    def _fresh_time(self, fetched_at: object) -> float | None:
        """`fetched_at` as a float if it's a valid timestamp within the TTL, else None."""
        if isinstance(fetched_at, bool) or not isinstance(fetched_at, (int, float)):
            return None
        now = self._now()
        if fetched_at > now + _FUTURE_SLACK_SECONDS or now - fetched_at >= self._ttl:
            return None
        return float(fetched_at)

    def _write_tasks_doc(self, tasklist_id: str, tasks: Tasks, fetched_at: float) -> None:
        self._write(
            self._tasks_path(tasklist_id),
            {"tasklist_id": tasklist_id, "fetched_at": fetched_at, "tasks": tasks},
        )

    def _update_tasklists_doc(self, key: str, entry: dict[str, Any]) -> None:
        path = self._dir / _TASKLISTS_FILE
        doc = self._read(path)
        doc[key] = entry
        self._write(path, doc)

    def _read(self, path: Path) -> dict[str, Any]:
        return read_json(path, SCHEMA_VERSION)

    def _write(self, path: Path, doc: dict[str, Any]) -> None:
        if write_json(path, doc, SCHEMA_VERSION, root=self._root):
            self._point_at_account()

    def _point_at_account(self) -> None:
        """Record the active account so readers without credentials (completion) find it."""
        if self._pointed:
            return
        current = self._root / _CURRENT_FILE
        try:
            if not current.exists() or current.read_text() != self._account:
                current.write_text(self._account)
                current.chmod(0o600)
            self._pointed = True
        except OSError:
            pass
