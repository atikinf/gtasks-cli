from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp_types import CallToolResult, ToolAnnotations

from gtasks.client.client_factory import SignInRequiredError
from gtasks.mcp_server import server as server_module
from gtasks.mcp_server.server import build_server
from gtasks.utils.config import Config, ConfigKey

pytestmark = pytest.mark.anyio

TODAY = date(2026, 10, 4)


class FixedDate(date):
    @classmethod
    def today(cls) -> "FixedDate":
        return cls(TODAY.year, TODAY.month, TODAY.day)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def client() -> MagicMock:
    client = MagicMock()
    client.get_tasklist.side_effect = lambda tasklist_id: {
        "@default": {"id": "L1", "title": "My Tasks"},
        "L1": {"id": "L1", "title": "My Tasks"},
        "L2": {"id": "L2", "title": "Russian Vocab"},
    }[tasklist_id]
    client.get_tasklists.return_value = [
        {"id": "L1", "title": "My Tasks"},
        {"id": "L2", "title": "Russian Vocab"},
    ]
    client.get_tasks.return_value = []
    return client


@pytest.fixture
def config_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "config.toml"
    monkeypatch.setattr(server_module, "CONFIG_FILE_PATH", path)
    return path


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(server_module, "date", FixedDate)


@pytest.fixture
def call(client: MagicMock, config_path: Path):
    server = build_server(lambda **_: client)

    async def call(name: str, **arguments: Any) -> Any:
        result = await server.call_tool(name, arguments)
        assert isinstance(result, CallToolResult)
        content = result.structured_content
        # Non-object results (lists) are wrapped by the SDK.
        return content["result"] if content and set(content) == {"result"} else content

    return call


def _http_error(status: int, uri: str = "https://example") -> HttpError:
    return HttpError(Response({"status": status}), b"", uri=uri)


class TestListTasklists:
    async def test_list_tasklists_GIVEN_default_and_active_THEN_both_marked(
        self, call, config_path: Path
    ) -> None:
        Config(config_path).set(ConfigKey.ACTIVE_TASKLIST_ID, "L2")

        result = await call("list_tasklists")

        assert result == [
            {"id": "L1", "title": "My Tasks", "is_default": True},
            {"id": "L2", "title": "Russian Vocab", "is_active": True},
        ]

    async def test_list_tasklists_GIVEN_refresh_THEN_fresh_client(
        self, client: MagicMock, config_path: Path
    ) -> None:
        get_client = MagicMock(return_value=client)

        await build_server(get_client).call_tool("list_tasklists", {"refresh": True})

        get_client.assert_called_once_with(fresh=True)


class TestListTasks:
    async def test_list_tasks_GIVEN_list_id_THEN_open_tasks_of_that_list_trimmed(
        self, call, client: MagicMock
    ) -> None:
        client.get_tasks.return_value = [
            {
                "id": "t1",
                "title": "привет",
                "status": "needsAction",
                "notes": "hello",
                "due": "2026-10-10T00:00:00.000Z",
                "updated": "2026-09-01T12:00:00.000Z",
                "etag": "ignored",
                "selfLink": "ignored",
            }
        ]

        result = await call("list_tasks", tasklist_id="L2")

        client.get_tasks.assert_called_once_with("L2", show_completed=False)
        assert result == {
            "today": "2026-10-04",
            "truncated": False,
            "tasklists": [
                {
                    "id": "L2",
                    "title": "Russian Vocab",
                    "total": 1,
                    "tasks": [
                        {
                            "id": "t1",
                            "title": "привет",
                            "status": "needsAction",
                            "notes": "hello",
                            "due": "2026-10-10",
                            "days_since_update": 33,
                        }
                    ],
                }
            ],
        }

    async def test_list_tasks_GIVEN_default_alias_THEN_reads_the_real_list(
        self, call, client: MagicMock
    ) -> None:
        await call("list_tasks", tasklist_id="@default")

        # The real ID, which the cache can serve; "@default" itself never is.
        client.get_tasks.assert_called_once_with("L1", show_completed=False)

    async def test_list_tasks_GIVEN_no_list_THEN_every_list(
        self, call, client: MagicMock
    ) -> None:
        result = await call("list_tasks")

        assert [g["id"] for g in result["tasklists"]] == ["L1", "L2"]

    async def test_list_tasks_GIVEN_include_completed_THEN_hidden_completed_too(
        self, call, client: MagicMock
    ) -> None:
        await call("list_tasks", tasklist_id="L1", include_completed=True)

        client.get_tasks.assert_called_once_with("L1", show_completed=True, show_hidden=True)

    async def test_list_tasks_GIVEN_not_updated_since_THEN_only_older_tasks(
        self, call, client: MagicMock
    ) -> None:
        client.get_tasks.return_value = [
            {"id": "old", "title": "a", "updated": "2026-06-01T00:00:00.000Z"},
            {"id": "edge", "title": "b", "updated": "2026-09-01T08:00:00.000Z"},
            {"id": "new", "title": "c", "updated": "2026-10-01T00:00:00.000Z"},
        ]

        result = await call("list_tasks", tasklist_id="L1", not_updated_since="2026-09-01")

        assert [t["id"] for t in result["tasklists"][0]["tasks"]] == ["old"]

    async def test_list_tasks_GIVEN_due_before_THEN_only_tasks_due_earlier(
        self, call, client: MagicMock
    ) -> None:
        client.get_tasks.return_value = [
            {"id": "overdue", "title": "a", "due": "2026-10-01T00:00:00.000Z"},
            {"id": "today", "title": "b", "due": "2026-10-04T00:00:00.000Z"},
            {"id": "undated", "title": "c"},
        ]

        result = await call("list_tasks", tasklist_id="L1", due_before="2026-10-04")

        assert [t["id"] for t in result["tasklists"][0]["tasks"]] == ["overdue"]

    async def test_list_tasks_GIVEN_more_than_limit_across_lists_THEN_oldest_kept_with_totals(
        self, call, client: MagicMock
    ) -> None:
        client.get_tasks.side_effect = lambda tasklist_id, **_: {
            "L1": [
                {"id": "a", "title": "a", "updated": "2026-08-01T00:00:00.000Z"},
                {"id": "b", "title": "b", "updated": "2026-01-01T00:00:00.000Z"},
            ],
            "L2": [{"id": "c", "title": "c", "updated": "2026-05-01T00:00:00.000Z"}],
        }[tasklist_id]

        result = await call("list_tasks", not_updated_since="2026-09-01", limit=2)

        assert result["truncated"] is True
        assert [(g["total"], [t["id"] for t in g["tasks"]]) for g in result["tasklists"]] == [
            (2, ["b"]),
            (1, ["c"]),
        ]

    async def test_list_tasks_GIVEN_long_notes_THEN_shortened_but_get_task_has_them_in_full(
        self, call, client: MagicMock
    ) -> None:
        long_task = {"id": "t1", "title": "recipe", "notes": "x" * 500}
        client.get_tasks.return_value = [long_task]
        client.get_task.return_value = long_task

        listed = await call("list_tasks", tasklist_id="L1")
        full = await call("get_task", tasklist_id="L1", task_id="t1")

        assert listed["tasklists"][0]["tasks"][0]["notes"].startswith("x" * 200 + "…")
        assert full["notes"] == "x" * 500

    @pytest.mark.parametrize("bad", ["next week", "2026-13-01", "20261004"])
    async def test_list_tasks_GIVEN_loose_date_THEN_tool_error_before_any_read(
        self, call, client: MagicMock, bad: str
    ) -> None:
        with pytest.raises(ToolError, match="YYYY-MM-DD"):
            await call("list_tasks", due_before=bad)

        client.get_tasks.assert_not_called()


class TestAddTasks:
    async def test_add_tasks_GIVEN_several_THEN_added_in_order_with_due_dates(
        self, call, client: MagicMock
    ) -> None:
        client.add_task.side_effect = [
            {"id": "n1", "title": "один", "status": "needsAction"},
            {"id": "n2", "title": "два", "status": "needsAction"},
        ]

        result = await call(
            "add_tasks",
            tasklist_id="L2",
            tasks=[{"title": " один ", "due": "2026-10-05"}, {"title": "два", "notes": "two"}],
        )

        assert client.add_task.call_args_list[0].args == ("L2", "один")
        assert client.add_task.call_args_list[0].kwargs == {
            "notes": None,
            "due": "2026-10-05T00:00:00.000Z",
            "previous_task_id": None,
        }
        # Each goes after the one before, so the list reads in the order given.
        assert client.add_task.call_args_list[1].kwargs["previous_task_id"] == "n1"
        assert [t["id"] for t in result] == ["n1", "n2"]

    async def test_add_tasks_GIVEN_one_bad_due_date_THEN_nothing_added(
        self, call, client: MagicMock
    ) -> None:
        with pytest.raises(ToolError, match="YYYY-MM-DD"):
            await call(
                "add_tasks",
                tasklist_id="L1",
                tasks=[{"title": "fine"}, {"title": "bad", "due": "tomorrow"}],
            )

        client.add_task.assert_not_called()

    async def test_add_tasks_GIVEN_failure_midway_THEN_error_names_tasks_already_created(
        self, call, client: MagicMock
    ) -> None:
        client.add_task.side_effect = [
            {"id": "n1", "title": "один", "status": "needsAction"},
            _http_error(500),
        ]

        with pytest.raises(ToolError, match=r"Created 1 of 2.*'один' \(n1\)"):
            await call("add_tasks", tasklist_id="L1", tasks=[{"title": "один"}, {"title": "два"}])


class TestOtherWrites:
    async def test_complete_tasks_GIVEN_ids_THEN_completed_in_one_call(
        self, call, client: MagicMock
    ) -> None:
        client.complete_tasks.return_value = [{"id": "t1", "title": "a", "status": "completed"}]

        result = await call("complete_tasks", tasklist_id="L1", task_ids=["t1"])

        client.complete_tasks.assert_called_once_with("L1", ["t1"])
        assert result[0]["status"] == "completed"

    async def test_update_task_GIVEN_nothing_to_change_THEN_tool_error(
        self, call, client: MagicMock
    ) -> None:
        with pytest.raises(ToolError, match="Nothing to change"):
            await call("update_task", tasklist_id="L1", task_id="t1")

        client.update_task.assert_not_called()

    async def test_move_task_GIVEN_destination_THEN_passed_through(
        self, call, client: MagicMock
    ) -> None:
        client.move_task.return_value = {"id": "t1", "title": "a", "status": "needsAction"}

        await call("move_task", tasklist_id="L1", task_id="t1", destination_tasklist_id="L2")

        client.move_task.assert_called_once_with(
            "L1", "t1", parent_task_id=None, previous_task_id=None, destination_tasklist_id="L2"
        )


class TestErrors:
    @pytest.mark.parametrize(
        "error",
        [SignInRequiredError("no token"), RefreshError("invalid_grant"), _http_error(401)],
    )
    async def test_GIVEN_signed_out_THEN_tool_error_says_gtasks_auth(
        self, call, client: MagicMock, error: Exception
    ) -> None:
        client.get_tasklists.side_effect = error

        with pytest.raises(ToolError, match="gtasks auth") as exc_info:
            await call("list_tasks")

        assert not isinstance(exc_info.value, UnexpectedToolError)

    async def test_GIVEN_partial_batch_failure_THEN_tool_error_names_failed_task(
        self, call, client: MagicMock
    ) -> None:
        client.delete_tasks.side_effect = ExceptionGroup(
            "batch delete_tasks failed",
            [_http_error(404, uri="https://tasks/v1/lists/L1/tasks/t2?alt=json")],
        )

        with pytest.raises(ToolError, match=r"1 task\(s\) failed: Not found \(t2\)"):
            await call("delete_tasks", tasklist_id="L1", task_ids=["t1", "t2"])


class TestToolAnnotations:
    async def test_list_tools_THEN_reads_read_only_and_delete_destructive(
        self, client: MagicMock
    ) -> None:
        tools = await build_server(lambda **_: client).list_tools()
        hints = {t.name: t.annotations or ToolAnnotations() for t in tools}

        assert hints["list_tasks"].read_only_hint
        assert hints["list_tasklists"].read_only_hint
        assert hints["delete_tasks"].destructive_hint


class TestClientProvider:
    @pytest.fixture(autouse=True)
    def no_config(self, config_path: Path) -> None:
        pass

    def test_get_client_THEN_never_starts_sign_in(self) -> None:
        with patch.object(server_module, "build_client") as build:
            server_module._make_client_provider()(fresh=True)

        assert build.call_args.kwargs["allow_sign_in"] is False
        assert build.call_args.kwargs["fresh"] is True

    def test_get_client_GIVEN_cache_off_THEN_no_cache_dir(self, config_path: Path) -> None:
        Config(config_path).set(ConfigKey.CACHE, "off")

        with patch.object(server_module, "build_client") as build:
            server_module._make_client_provider()()

        assert build.call_args.kwargs["cache_dir"] is None
