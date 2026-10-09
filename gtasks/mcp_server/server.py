"""MCP server: Google Tasks as tools for an LLM host (Claude Code, Claude Desktop), over stdio.

A sibling of `cli/`, built on `client/` alone. Tools take and return API IDs, which a model
carries between calls without trouble, so none of the CLI's title matching, listing numbers or
prompts apply here: the model looks tasks up with `list_tasks` and acts on what it found.

Two rules keep the stdio transport intact, since stdout *is* the protocol stream:
- nothing here prints (no `cli.ui`), and
- the client is built with `allow_sign_in=False`, so the OAuth browser flow (which prints and
  blocks) never runs; a signed-out user is told to run `gtasks auth` instead.

Sync tools run on worker threads, so each call builds its own client (httplib2 connections
aren't thread-safe) under a lock (two threads mustn't refresh and rewrite the same token).
Writes act on IDs, so they're safe whatever the cache held when the model read them.
"""

import importlib.metadata
import re
import sys
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, NotRequired, TypedDict

try:
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp_types import ToolAnnotations
except ModuleNotFoundError as e:  # pragma: no cover - only without the `mcp` extra
    sys.exit(f"gtasks-mcp needs the `mcp` extra (pip install 'gtasks-cli[mcp]'): {e}")

from gtasks import defaults
from gtasks.client.client_factory import SignInRequiredError, build_client
from gtasks.client.protocol import DEFAULT_TASKLIST_ID
from gtasks.utils.config import Config, ConfigKey

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList

    from gtasks.client.protocol import ClientProvider, TasksClient


INSTRUCTIONS = """\
Read and manage the user's Google Tasks.

- Everything is addressed by ID. Find IDs with `list_tasklists` and `list_tasks`; never guess.
- "My list" / "my tasks" without a name means the list marked `is_active` (chosen with
  `gtasks use`), else the one marked `is_default`.
- Google Tasks records no creation date. To judge how old a task is, use `days_since_update`
  (or `due` for overdue tasks), and say that's what you used.
- Reads may come from a cache up to 30 minutes old; pass `refresh=true` if that matters
  (e.g. the user just changed something in another app).
- Confirm with the user before deleting tasks, and before acting on many tasks at once.
"""

_SIGN_IN_HINT = "Ask the user to run `gtasks auth` in a terminal, then retry."


class NewTask(TypedDict):
    title: str
    notes: NotRequired[str]
    due: NotRequired[str]  # YYYY-MM-DD


class TaskOut(TypedDict):
    id: str
    title: str
    status: str
    notes: NotRequired[str]
    due: NotRequired[str]
    completed: NotRequired[str]
    parent_id: NotRequired[str]
    days_since_update: NotRequired[int]


class TaskListOut(TypedDict):
    id: str
    title: str
    is_default: NotRequired[bool]
    is_active: NotRequired[bool]


class TaskListWithTasks(TypedDict):
    id: str
    title: str
    total: int  # tasks that matched, before `limit`
    tasks: list[TaskOut]


class TaskListing(TypedDict):
    today: str
    truncated: bool
    tasklists: list[TaskListWithTasks]


# --- Conversions ---------------------------------------------------------------------------

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Listings span every list and can run to hundreds of tasks: keep notes short there
# (`get_task` has them in full).
_LISTING_NOTES_CHARS = 200


def _parse_date(value: str, field: str) -> date:
    """Strict YYYY-MM-DD: a model can always produce it, and anything looser is ambiguous."""
    try:
        if _ISO_DATE.fullmatch(value):
            return date.fromisoformat(value)
    except ValueError:
        pass
    raise ToolError(f"Invalid {field} {value!r}: use YYYY-MM-DD.")


def _due_to_api(value: str) -> str:
    # The Tasks API keeps only the date of `due`, as midnight UTC.
    return f"{_parse_date(value, 'due date').isoformat()}T00:00:00.000Z"


def _task_out(task: "Task", today: date, notes_chars: int | None = None) -> TaskOut:
    """The fields a model needs, with absent ones left out to keep results small."""
    out: TaskOut = {
        "id": task.get("id", ""),
        "title": task.get("title", ""),
        "status": task.get("status", ""),
    }
    if notes := task.get("notes"):
        if notes_chars is not None and len(notes) > notes_chars:
            notes = notes[:notes_chars] + "… (truncated; get_task has the full notes)"
        out["notes"] = notes
    if due := task.get("due"):
        out["due"] = due[:10]
    if completed := task.get("completed"):
        out["completed"] = completed[:10]
    if parent := task.get("parent"):
        out["parent_id"] = parent
    if updated := task.get("updated"):
        updated_on = datetime.fromisoformat(updated).astimezone(UTC).date()
        out["days_since_update"] = (today - updated_on).days
    return out


# --- Errors --------------------------------------------------------------------------------


def _describe(e: Exception) -> str:
    """One line a model can act on, for an error raised by the client."""
    from google.auth.exceptions import RefreshError
    from googleapiclient.errors import HttpError

    if isinstance(e, SignInRequiredError):
        return f"The user isn't signed in to Google Tasks. {_SIGN_IN_HINT}"
    if isinstance(e, RefreshError):
        return f"The user's Google sign-in has expired or was revoked. {_SIGN_IN_HINT}"
    if isinstance(e, HttpError):
        status = e.resp.status
        if status == 401:
            return f"The user's Google sign-in has expired or was revoked. {_SIGN_IN_HINT}"
        if status == 404:
            # A batch error's URI ends in the task it was about.
            target = (e.uri or "").split("?")[0].rsplit("/", 1)[-1]
            return (
                f"Not found{f' ({target})' if target else ''}: the list or task may have been "
                "deleted, or the ID is wrong. Re-read with list_tasklists / list_tasks."
            )
        return f"Google Tasks API error ({status}): {e.reason}"
    return str(e) or type(e).__name__


@contextmanager
def _client_errors() -> Iterator[None]:
    """Turn the client's errors into `ToolError`s: anything else reaches the model only as
    "Error executing tool", which it can do nothing with."""
    try:
        yield
    except ToolError:
        raise
    except ExceptionGroup as eg:
        # A batch (complete/reopen/delete) in which some tasks failed; the rest went through.
        reasons = "; ".join(_describe(sub) for sub in eg.exceptions)
        raise ToolError(
            f"{len(eg.exceptions)} task(s) failed: {reasons}. The others succeeded; "
            "call list_tasks to see the current state before retrying."
        ) from eg
    except Exception as e:
        raise ToolError(_describe(e)) from e


# --- Server --------------------------------------------------------------------------------


def build_server(get_client: "ClientProvider") -> MCPServer:
    """The server with its tools, acting through `get_client` (injected so tests can mock)."""
    server = MCPServer("gtasks", instructions=INSTRUCTIONS, version=_version())

    # --- Reads -----------------------------------------------------------------------------

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    def list_tasklists(refresh: bool = False) -> list[TaskListOut]:
        """List the user's task lists, marking the default list and the active one (the list
        the user picked with `gtasks use`, which "my tasks" usually means)."""
        with _client_errors():
            client = get_client(fresh=refresh)
            default_id = client.get_tasklist(DEFAULT_TASKLIST_ID).get("id")
            active_id = Config.default().get(ConfigKey.ACTIVE_TASKLIST_ID)
            out: list[TaskListOut] = []
            for tasklist in client.get_tasklists():
                item: TaskListOut = {"id": tasklist["id"], "title": tasklist.get("title", "")}
                if tasklist["id"] == default_id:
                    item["is_default"] = True
                if tasklist["id"] == active_id:
                    item["is_active"] = True
                out.append(item)
            return out

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    def list_tasks(
        tasklist_id: str | None = None,
        include_completed: bool = False,
        due_before: str | None = None,
        not_updated_since: str | None = None,
        limit: int = 50,
        refresh: bool = False,
    ) -> TaskListing:
        """List tasks, grouped by list: one list, or every list if `tasklist_id` is omitted.

        Open tasks only unless `include_completed`. Filters (dates as YYYY-MM-DD):
        `due_before` keeps tasks due before that date (overdue: today's date), earliest due
        first; `not_updated_since` keeps tasks last changed before that date (stale or old
        tasks), least recently updated first. Otherwise tasks keep their list order.

        At most `limit` tasks are returned in all; each list's `total` counts every match, and
        `truncated` says some were left out (narrow the query, or raise `limit`). Notes are
        shortened here; `get_task` returns a task in full. `today` is the user's current date.
        """
        if limit < 1:
            raise ToolError("limit must be at least 1.")
        today = date.today()
        due_cutoff = _parse_date(due_before, "due_before") if due_before else None
        updated_cutoff = (
            _parse_date(not_updated_since, "not_updated_since") if not_updated_since else None
        )

        def keep(task: TaskOut) -> bool:
            if due_cutoff and not ("due" in task and date.fromisoformat(task["due"]) < due_cutoff):
                return False
            if updated_cutoff and task.get("days_since_update") is not None:
                return (today - updated_cutoff).days < task["days_since_update"]
            return True

        with _client_errors():
            client = get_client(fresh=refresh)
            # get_tasklist also turns "@default" into the real list, which the cache can serve.
            tasklists: list[TaskList] = (
                [client.get_tasklist(tasklist_id)] if tasklist_id else client.get_tasklists()
            )
            groups: list[TaskListWithTasks] = []
            matches: list[tuple[TaskListWithTasks, TaskOut]] = []
            for tasklist in tasklists:
                # Open tasks only is the query the cache serves; date filters apply afterwards
                # rather than as API filters, which would bypass it.
                tasks = (
                    client.get_tasks(tasklist["id"], show_completed=True, show_hidden=True)
                    if include_completed
                    else client.get_tasks(tasklist["id"], show_completed=False)
                )
                group: TaskListWithTasks = {
                    "id": tasklist["id"],
                    "title": tasklist.get("title", ""),
                    "total": 0,
                    "tasks": [],
                }
                groups.append(group)
                for task in tasks:
                    out = _task_out(task, today, notes_chars=_LISTING_NOTES_CHARS)
                    if keep(out):
                        group["total"] += 1
                        matches.append((group, out))

        # The cap applies across lists, so put what the filter asked about first.
        if updated_cutoff:
            matches.sort(key=lambda m: -m[1].get("days_since_update", 0))
        elif due_cutoff:
            matches.sort(key=lambda m: m[1].get("due", ""))
        for group, out in matches[:limit]:
            group["tasks"].append(out)
        return {
            "today": today.isoformat(),
            "truncated": len(matches) > limit,
            "tasklists": groups,
        }

    @server.tool(annotations=ToolAnnotations(read_only_hint=True))
    def get_task(tasklist_id: str, task_id: str) -> TaskOut:
        """One task in full, including notes that `list_tasks` shortens."""
        with _client_errors():
            return _task_out(get_client().get_task(tasklist_id, task_id), date.today())

    # --- Writes ----------------------------------------------------------------------------

    @server.tool()
    def add_tasks(tasklist_id: str, tasks: list[NewTask]) -> list[TaskOut]:
        """Add tasks to a list, in the given order, at the top of the list. Each task has a
        `title`, and optionally `notes` and a `due` date (YYYY-MM-DD)."""
        # Check everything before the first write, so bad input never leaves half a batch.
        if not tasks:
            raise ToolError("No tasks given.")
        dues: list[str | None] = []
        for task in tasks:
            if not task.get("title", "").strip():
                raise ToolError("Every task needs a non-empty title.")
            dues.append(_due_to_api(task["due"]) if task.get("due") else None)

        today = date.today()
        created: list[TaskOut] = []
        with _client_errors():
            client = get_client()
            try:
                for task, due in zip(tasks, dues, strict=True):
                    previous = created[-1]["id"] if created else None
                    new = client.add_task(
                        tasklist_id,
                        task["title"].strip(),
                        notes=task.get("notes"),
                        due=due,
                        previous_task_id=previous,
                    )
                    created.append(_task_out(new, today))
            except Exception as e:
                if not created:
                    raise
                # add_task isn't batched: say what's already there, so a retry can't duplicate.
                done = ", ".join(f"{t['title']!r} ({t['id']})" for t in created)
                raise ToolError(
                    f"Created {len(created)} of {len(tasks)} tasks, then failed: {_describe(e)} "
                    f"Already created, don't add again: {done}."
                ) from e
            return created

    @server.tool(annotations=ToolAnnotations(idempotent_hint=True))
    def update_task(
        tasklist_id: str,
        task_id: str,
        title: str | None = None,
        notes: str | None = None,
        due: str | None = None,
    ) -> TaskOut:
        """Change a task's title, notes or due date (YYYY-MM-DD); omitted fields are kept."""
        if title is None and notes is None and due is None:
            raise ToolError("Nothing to change: give a title, notes or due date.")
        api_due = _due_to_api(due) if due else None
        with _client_errors():
            task = get_client().update_task(
                tasklist_id, task_id, task_title=title, notes=notes, due=api_due
            )
            return _task_out(task, date.today())

    @server.tool(annotations=ToolAnnotations(idempotent_hint=True))
    def complete_tasks(tasklist_id: str, task_ids: list[str]) -> list[TaskOut]:
        """Mark tasks in one list complete."""
        with _client_errors():
            done = get_client().complete_tasks(tasklist_id, task_ids)
            return [_task_out(task, date.today()) for task in done]

    @server.tool(annotations=ToolAnnotations(idempotent_hint=True))
    def reopen_tasks(tasklist_id: str, task_ids: list[str]) -> list[TaskOut]:
        """Mark completed tasks in one list as not done again."""
        with _client_errors():
            reopened = get_client().reopen_tasks(tasklist_id, task_ids)
            return [_task_out(task, date.today()) for task in reopened]

    @server.tool(annotations=ToolAnnotations(destructive_hint=True, idempotent_hint=True))
    def delete_tasks(tasklist_id: str, task_ids: list[str]) -> list[str]:
        """Permanently delete tasks (and their subtasks) from one list. Confirm with the user
        first. Returns the deleted IDs."""
        with _client_errors():
            get_client().delete_tasks(tasklist_id, task_ids)
            return task_ids

    @server.tool()
    def move_task(
        tasklist_id: str,
        task_id: str,
        destination_tasklist_id: str | None = None,
        parent_id: str | None = None,
        previous_id: str | None = None,
    ) -> TaskOut:
        """Move a task to another list, under a parent task (making it a subtask), or after a
        sibling (`previous_id`); with none of these it moves to the top of its list."""
        with _client_errors():
            task = get_client().move_task(
                tasklist_id,
                task_id,
                parent_task_id=parent_id,
                previous_task_id=previous_id,
                destination_tasklist_id=destination_tasklist_id,
            )
            return _task_out(task, date.today())

    @server.tool()
    def create_tasklist(title: str) -> TaskListOut:
        """Create a new, empty task list."""
        if not title.strip():
            raise ToolError("The list needs a non-empty title.")
        with _client_errors():
            tasklist = get_client().add_tasklist(title.strip())
            return {"id": tasklist["id"], "title": tasklist.get("title", "")}

    return server


def _version() -> str:
    try:
        return importlib.metadata.version("gtasks-cli")
    except importlib.metadata.PackageNotFoundError:  # running from an uninstalled checkout
        return ""


def _make_client_provider() -> "ClientProvider":
    """A fresh client per call (see the module docstring), honouring `cache = off`."""
    lock = threading.Lock()

    def get_client(*, fresh: bool = False) -> "TasksClient":
        cache_off = Config.default().get(ConfigKey.CACHE) == "off"
        with lock:
            return build_client(
                fresh=fresh,
                cache_dir=None if cache_off else defaults.CACHE_DIR,
                allow_sign_in=False,
            )

    return get_client


def main() -> None:
    try:
        build_server(_make_client_provider()).run("stdio")
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
