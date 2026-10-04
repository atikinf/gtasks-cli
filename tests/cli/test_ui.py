from collections.abc import Iterator
from datetime import date
from io import StringIO

import pytest
from rich.console import Console

from gtasks.cli import ui

TODAY = date(2026, 10, 2)  # a Friday


def _console(**kwargs) -> Console:
    return Console(
        file=StringIO(), width=100, theme=ui.THEME, highlight=False, emoji=False, **kwargs
    )


@pytest.fixture
def consoles() -> Iterator[tuple[Console, Console]]:
    out, err = _console(color_system=None), _console(color_system=None)
    ui.use_consoles(out, err)
    yield out, err
    ui.use_consoles(None, None)


def _text(console: Console) -> str:
    file = console.file
    assert isinstance(file, StringIO)
    return file.getvalue()


class TestFormatDue:
    @pytest.mark.parametrize(
        "due, expected",
        [
            ("2026-10-02T00:00:00.000Z", ("today", "due.today")),
            ("2026-10-03T00:00:00.000Z", ("tomorrow", "due")),
            ("2026-10-06T00:00:00.000Z", ("Tue", "due")),
            ("2026-10-14T00:00:00.000Z", ("Oct 14", "due")),
            ("2027-01-05T00:00:00.000Z", ("Jan 5, 2027", "due")),
            ("2026-10-01T00:00:00.000Z", ("overdue · yesterday", "due.overdue")),
            ("2026-04-22T00:00:00.000Z", ("overdue · Apr 22", "due.overdue")),
        ],
        ids=["today", "tomorrow", "this-week", "later", "next-year", "yesterday", "overdue"],
    )
    def test_format_due_GIVEN_date_THEN_relative_label_and_style(
        self, due: str, expected: tuple[str, str]
    ) -> None:
        assert ui.format_due(due, TODAY) == expected

    def test_format_due_GIVEN_unparseable_THEN_returns_raw(self) -> None:
        assert ui.format_due("someday", TODAY) == ("someday", "due")


class TestRenderTasks:
    def test_render_tasks_GIVEN_heading_THEN_shows_list_and_open_count(
        self, consoles: tuple[Console, Console]
    ) -> None:
        tasks = [{"id": "t1", "title": "Buy milk"}, {"id": "t2", "title": "Eggs"}]

        ui.render_tasks(tasks, heading="Groceries", today=TODAY)

        output = _text(consoles[0])
        assert "Groceries · 2 open" in output
        assert "1 ○ Buy milk" in output
        assert "2 ○ Eggs" in output

    def test_render_tasks_GIVEN_truncated_THEN_marks_count_and_hints(
        self, consoles: tuple[Console, Console]
    ) -> None:
        ui.render_tasks([{"id": "t1", "title": "A"}], heading="L", truncated=True, today=TODAY)

        output = _text(consoles[0])
        assert "1+ open" in output
        assert "gtasks tasks" in output

    @pytest.mark.parametrize(
        "age, note",
        [(None, None), (59, None), (60, "cached 1m ago"), (12 * 60 + 30, "cached 12m ago")],
        ids=["live", "under-a-minute", "one-minute", "twelve-minutes"],
    )
    def test_render_tasks_GIVEN_cached_age_THEN_note_only_from_a_minute(
        self, consoles: tuple[Console, Console], age: float | None, note: str | None
    ) -> None:
        ui.render_tasks([], heading="Groceries", cached_age=age, today=TODAY)

        heading = _text(consoles[0]).splitlines()[0]
        if note is None:
            assert "cached" not in heading
        else:
            assert heading.endswith(f"Groceries · 0 open · {note}")

    def test_render_tasks_GIVEN_no_tasks_THEN_says_nothing_to_do(
        self, consoles: tuple[Console, Console]
    ) -> None:
        ui.render_tasks([], heading="Groceries", today=TODAY)

        assert "Nothing to do." in _text(consoles[0])

    def test_render_tasks_GIVEN_due_and_notes_THEN_renders_both(
        self, consoles: tuple[Console, Console]
    ) -> None:
        tasks = [{"id": "t1", "title": "Task", "due": "2026-10-03T00:00:00.000Z", "notes": "n1"}]

        ui.render_tasks(tasks, today=TODAY)

        output = _text(consoles[0])
        assert "tomorrow" in output
        assert "n1" in output

    def test_render_tasks_GIVEN_multiline_notes_THEN_first_line_with_ellipsis(
        self, consoles: tuple[Console, Console]
    ) -> None:
        tasks = [{"id": "t1", "title": "Task", "notes": "first\nsecond"}]

        ui.render_tasks(tasks, today=TODAY)

        output = _text(consoles[0])
        assert "first…" in output
        assert "second" not in output

    def test_render_tasks_GIVEN_markup_like_title_THEN_renders_verbatim(
        self, consoles: tuple[Console, Console]
    ) -> None:
        tasks = [{"id": "t1", "title": "[urgent] call :bank:"}]

        ui.render_tasks(tasks, today=TODAY)

        assert "[urgent] call :bank:" in _text(consoles[0])

    def test_render_tasks_GIVEN_show_ids_THEN_includes_ids(
        self, consoles: tuple[Console, Console]
    ) -> None:
        ui.render_tasks([{"id": "t1", "title": "Task"}], show_ids=True, today=TODAY)

        assert "t1" in _text(consoles[0])

    def test_render_tasks_GIVEN_completed_task_THEN_check_mark_strikethrough_and_no_due(
        self,
    ) -> None:
        out = _console(force_terminal=True, color_system="standard")
        ui.use_consoles(out, _console())
        try:
            tasks = [{"title": "Done", "status": "completed", "due": "2026-04-22T00:00:00Z"}]
            ui.render_tasks(tasks, today=TODAY)
        finally:
            ui.use_consoles(None, None)

        output = _text(out)
        assert ui.DONE_MARK in output
        assert "9m" in output  # SGR 9: strikethrough
        assert "overdue" not in output


class TestRenderTasklists:
    def test_render_tasklists_GIVEN_active_id_THEN_marks_only_that_list(
        self, consoles: tuple[Console, Console]
    ) -> None:
        tasklists = [{"id": "l1", "title": "Work"}, {"id": "l2", "title": "Home"}]

        ui.render_tasklists(tasklists, active_id="l2")

        lines = _text(consoles[0]).splitlines()
        assert ui.ACTIVE_MARK not in lines[0]
        assert f"{ui.ACTIVE_MARK} Home" in lines[1]

    def test_render_tasklists_GIVEN_show_ids_THEN_includes_ids(
        self, consoles: tuple[Console, Console]
    ) -> None:
        ui.render_tasklists([{"id": "l1", "title": "Work"}], show_ids=True)

        assert "l1" in _text(consoles[0])


class TestMessages:
    def test_report_mutation_GIVEN_one_title_THEN_single_line_naming_list(
        self, consoles: tuple[Console, Console]
    ) -> None:
        ui.report_mutation("Completed", ["Buy milk"], "Groceries")

        assert _text(consoles[0]).strip() == "✓ Completed Buy milk · Groceries"

    def test_report_mutation_GIVEN_several_titles_THEN_lists_each_and_summarises(
        self, consoles: tuple[Console, Console]
    ) -> None:
        ui.report_mutation("Deleted", ["A", "B"], "Groceries")

        assert _text(consoles[0]).splitlines() == [" ✓ A", " ✓ B", " Deleted 2 tasks · Groceries"]

    def test_error_GIVEN_hint_THEN_both_go_to_stderr(
        self, consoles: tuple[Console, Console]
    ) -> None:
        ui.error("bad thing", hint="do this")

        assert _text(consoles[0]) == ""
        assert _text(consoles[1]).splitlines() == ["error: bad thing", "hint: do this"]
