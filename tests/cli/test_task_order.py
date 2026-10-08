from gtasks.cli.task_order import display_order


def _task(id: str, position: int, parent: str | None = None) -> dict:
    task = {"id": id, "title": id, "position": f"{position:020d}"}
    if parent is not None:
        task["parent"] = parent
    return task


def _ids(tasks: list[dict]) -> list[str]:
    return [t["id"] for t in tasks]


class TestDisplayOrder:
    def test_display_order_GIVEN_updated_order_THEN_sorted_by_position(self) -> None:
        tasks = [_task("c", 2), _task("a", 0), _task("b", 1)]

        assert _ids(display_order(tasks)) == ["a", "b", "c"]

    def test_display_order_GIVEN_subtasks_THEN_under_parent_by_position(self) -> None:
        tasks = [
            _task("a2", 1, parent="a"),
            _task("b", 1),
            _task("a1", 0, parent="a"),
            _task("a", 0),
        ]

        # Subtask positions count among siblings, so they can equal top-level ones.
        assert _ids(display_order(tasks)) == ["a", "a1", "a2", "b"]

    def test_display_order_GIVEN_parent_not_listed_THEN_subtask_is_top_level(self) -> None:
        tasks = [_task("b", 1), _task("orphan", 0, parent="completed-parent")]

        assert _ids(display_order(tasks)) == ["orphan", "b"]

    def test_display_order_GIVEN_no_positions_THEN_keeps_given_order(self) -> None:
        tasks = [{"id": "x"}, {"id": "y"}]

        assert _ids(display_order(tasks)) == ["x", "y"]

    def test_display_order_GIVEN_empty_THEN_empty(self) -> None:
        assert display_order([]) == []
