"""All terminal output for the CLI goes through this module.

Handlers fetch data and call these functions; they never print directly. That keeps the
look consistent across commands and leaves a single place to change it.

User-supplied strings (task and list titles, notes) are only ever wrapped in `Text`, never
interpolated into rich markup, so a title like "[urgent] pay rent" renders verbatim.
"""

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.schemas import Task, TaskList

THEME = Theme(
    {
        "muted": "dim",
        "index": "dim",
        "heading": "bold",
        "success": "green",
        "warn": "yellow",
        "error": "bold red",
        "active": "bold cyan",
        "due": "cyan",
        "due.today": "bold yellow",
        "due.overdue": "bold red",
        "done": "dim strike",
    }
)

OPEN_MARK = "○"
DONE_MARK = "✓"
ACTIVE_MARK = "●"
_NOTES_MAX = 60
# Long titles wrap at this width so the due column stays next to the titles.
_TITLE_MAX = 56
# stdout lines start one column in, matching the tables' edge padding.
_INDENT = " "

_out: Console | None = None
_err: Console | None = None


def out() -> Console:
    global _out
    if _out is None:
        _out = Console(theme=THEME, highlight=False, emoji=False)
    return _out


def err() -> Console:
    global _err
    if _err is None:
        _err = Console(theme=THEME, highlight=False, emoji=False, stderr=True)
    return _err


def use_consoles(stdout: Console | None, stderr: Console | None) -> None:
    """Swap the output consoles (for tests); None restores the lazily-built default."""
    global _out, _err
    _out, _err = stdout, stderr


# =============================================================================
# Messages
# =============================================================================


def error(message: str, hint: str | None = None) -> None:
    err().print(Text.assemble(("error: ", "error"), message))
    if hint:
        err().print(Text(f"hint: {hint}", style="muted"))


def warn(message: str, hint: str | None = None) -> None:
    err().print(Text.assemble(("warning: ", "warn"), message))
    if hint:
        err().print(Text(f"hint: {hint}", style="muted"))


def info(message: str | Text) -> None:
    out().print(Text.assemble(_INDENT, message))


def success(message: str | Text) -> None:
    out().print(Text.assemble(_INDENT, (f"{DONE_MARK} ", "success"), message))


def report_mutation(verb: str, titles: list[str], tasklist_title: str) -> None:
    """Confirm an action on one or more tasks, always naming the list it happened in.

    One task:   ✓ Completed Buy milk · Groceries
    Several:    ✓ Buy milk
                ✓ Eggs
                Completed 2 tasks · Groceries
    """
    where = Text(f" · {tasklist_title}", style="muted")
    if len(titles) == 1:
        success(Text.assemble(f"{verb} ", (titles[0], "heading"), where))
        return
    for title in titles:
        success(title)
    info(Text.assemble(f"{verb} {len(titles)} tasks", where))


# =============================================================================
# Tasks
# =============================================================================


def _short_date(d: date, today: date) -> str:
    label = f"{d.strftime('%b')} {d.day}"
    return label if d.year == today.year else f"{label}, {d.year}"


def format_due(due: str, today: date) -> tuple[str, str]:
    """Render an RFC 3339 due timestamp relative to `today`, returning (label, style).

    The Tasks API stores due dates as midnight UTC and ignores the time, so only the UTC
    date is meaningful; converting to local time would shift it a day early in western
    time zones.
    """
    try:
        d = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(timezone.utc).date()
    except ValueError:
        return due, "due"

    delta = (d - today).days
    if delta < 0:
        when = "yesterday" if delta == -1 else _short_date(d, today)
        return f"overdue · {when}", "due.overdue"
    if delta == 0:
        return "today", "due.today"
    if delta == 1:
        return "tomorrow", "due"
    if delta < 7:
        return d.strftime("%a"), "due"
    return _short_date(d, today), "due"


def _one_line(notes: str) -> str:
    """First line of `notes`, with an ellipsis if anything was cut."""
    lines = notes.strip().splitlines()
    if not lines:
        return ""
    if len(lines) == 1 and len(lines[0]) <= _NOTES_MAX:
        return lines[0]
    return lines[0][: _NOTES_MAX - 1].rstrip() + "…"


def render_tasks(
    tasks: "list[Task]",
    *,
    heading: str | None = None,
    show_ids: bool = False,
    truncated: bool = False,
    today: date | None = None,
) -> None:
    """Print a numbered task table; numbers match what `done`/`delete` accept.

    `truncated` means more tasks exist than were passed (a --limit cut the list short).
    """
    today = today or date.today()

    if heading is not None:
        open_count = sum(1 for t in tasks if t.get("status") != "completed")
        count = f"{open_count}+" if truncated else str(open_count)
        out().print(Text.assemble(_INDENT, (heading, "heading"), (f" · {count} open", "muted")))

    if not tasks:
        out().print(Text(f"{_INDENT} Nothing to do.", style="muted"))
        return

    table = Table.grid(padding=(0, 1), pad_edge=True)
    table.add_column(justify="right", style="index", no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold", max_width=_TITLE_MAX)
    if show_ids:
        table.add_column(style="muted", no_wrap=True)
    table.add_column(no_wrap=True)

    for ix, task in enumerate(tasks, 1):
        completed = task.get("status") == "completed"
        mark = Text(DONE_MARK, style="success") if completed else Text(OPEN_MARK, style="muted")
        title = Text(task.get("title") or "(untitled)", style="done" if completed else "")
        due = task.get("due")
        due_cell = Text(*format_due(due, today)) if due and not completed else Text("")

        row: list[Text] = [Text(str(ix)), mark, title]
        if show_ids:
            row.append(Text(task.get("id", "")))
        row.append(due_cell)
        table.add_row(*row)

        notes = task.get("notes")
        if notes and _one_line(notes):
            notes_row = [Text(""), Text(""), Text(_one_line(notes), style="muted")]
            notes_row += [Text("")] * (len(row) - len(notes_row))
            table.add_row(*notes_row)

    out().print(table)
    if truncated:
        hint = f"{_INDENT} More not shown. Run `gtasks tasks` to see all."
        out().print(Text(hint, style="muted"))


# =============================================================================
# Task lists
# =============================================================================


def render_tasklists(
    tasklists: "list[TaskList]",
    *,
    active_id: str | None = None,
    show_ids: bool = False,
) -> None:
    """Print a numbered list of task lists, marking the active one."""
    if not tasklists:
        out().print(Text(f"{_INDENT} No task lists.", style="muted"))
        return

    table = Table.grid(padding=(0, 1), pad_edge=True)
    table.add_column(justify="right", style="index", no_wrap=True)
    table.add_column(no_wrap=True)
    table.add_column(overflow="fold")
    if show_ids:
        table.add_column(style="muted", no_wrap=True)

    for ix, tasklist in enumerate(tasklists, 1):
        is_active = active_id is not None and tasklist.get("id") == active_id
        mark = Text(ACTIVE_MARK, style="active") if is_active else Text(" ")
        title = Text(tasklist.get("title") or "(untitled)", style="active" if is_active else "")
        row = [Text(str(ix)), mark, title]
        if show_ids:
            row.append(Text(tasklist.get("id", "")))
        table.add_row(*row)

    out().print(table)
