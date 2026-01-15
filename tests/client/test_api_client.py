from unittest.mock import MagicMock

import pytest

from gtasks.client.api_client import ApiClient


@pytest.fixture
def service() -> MagicMock:
    return MagicMock()


@pytest.fixture
def api_client(service: MagicMock) -> ApiClient:
    return ApiClient(service)


class TestGetTasklists:
    MAX_TASKLISTS = 3
    PAGE1_ITEMS = [{"id": "list1", "title": "My Tasks"}]
    PAGE2_ITEMS = [{"id": "list2", "title": "Work"}]
    PAGE3_ITEMS = [{"id": "list3", "title": "Personal"}]

    def _mock_paginated_list(self, **kwargs) -> MagicMock:
        mock = MagicMock()
        page_token = kwargs.get("pageToken")
        if page_token is None:
            mock.execute.return_value = {
                "items": self.PAGE1_ITEMS,
                "nextPageToken": "token1",
            }
        elif page_token == "token1":
            mock.execute.return_value = {
                "items": self.PAGE2_ITEMS,
                "nextPageToken": "token2",
            }
        else:
            mock.execute.return_value = {"items": self.PAGE3_ITEMS}
        return mock

    def test_get_tasklists_GIVEN_items_in_response_THEN_returns_items(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        expected_tasklists = [
            {"id": "list1", "title": "My Tasks"},
            {"id": "list2", "title": "Work"},
        ]
        service.tasklists().list().execute.return_value = {"items": expected_tasklists}

        result = api_client.get_tasklists()

        assert result == expected_tasklists
        service.tasklists().list().execute.assert_called_once()

    def test_get_tasklists_GIVEN_empty_items_THEN_returns_empty_list(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasklists().list().execute.return_value = {"items": []}

        result = api_client.get_tasklists()

        assert result == []

    def test_get_tasklists_GIVEN_no_items_key_THEN_returns_empty_list(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasklists().list().execute.return_value = {}

        result = api_client.get_tasklists()

        assert result == []

    def test_get_tasklists_GIVEN_multiple_pages_THEN_returns_all_items(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasklists().list.side_effect = self._mock_paginated_list

        result = api_client.get_tasklists()

        assert result == self.PAGE1_ITEMS + self.PAGE2_ITEMS + self.PAGE3_ITEMS
        assert service.tasklists().list.call_count == 3

    def test_get_tasklists_GIVEN_max_results_THEN_returns_limited_items(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasklists().list.side_effect = self._mock_paginated_list

        result = api_client.get_tasklists(max_results=2)

        assert result == self.PAGE1_ITEMS + self.PAGE2_ITEMS
        assert len(result) == 2
        assert service.tasklists().list.call_count == 2  # page 3 not reached


class TestGetTasks:
    TASKLIST_ID = "tasklist123"
    MAX_TASKS = 3
    PAGE1_ITEMS = [{"id": "task1", "title": "Buy groceries"}]
    PAGE2_ITEMS = [{"id": "task2", "title": "Call mom"}]
    PAGE3_ITEMS = [{"id": "task3", "title": "Exercise"}]

    def _mock_paginated_list(self, **kwargs) -> MagicMock:
        mock = MagicMock()
        page_token = kwargs.get("pageToken")
        if page_token is None:
            mock.execute.return_value = {
                "items": self.PAGE1_ITEMS,
                "nextPageToken": "token1",
            }
        elif page_token == "token1":
            mock.execute.return_value = {
                "items": self.PAGE2_ITEMS,
                "nextPageToken": "token2",
            }
        else:
            mock.execute.return_value = {"items": self.PAGE3_ITEMS}
        return mock

    def test_get_tasks_GIVEN_items_in_response_THEN_returns_items(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        expected_tasks = [
            {"id": "task1", "title": "Buy groceries"},
            {"id": "task2", "title": "Call mom"},
        ]
        service.tasks().list(tasklist=self.TASKLIST_ID).execute.return_value = {
            "items": expected_tasks
        }

        result = api_client.get_tasks(self.TASKLIST_ID)

        assert result == expected_tasks
        service.tasks().list.assert_called_with(tasklist=self.TASKLIST_ID)

    def test_get_tasks_GIVEN_empty_items_THEN_returns_empty_list(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().list(tasklist=self.TASKLIST_ID).execute.return_value = {
            "items": []
        }

        result = api_client.get_tasks(self.TASKLIST_ID)

        assert result == []

    def test_get_tasks_GIVEN_no_items_key_THEN_returns_empty_list(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().list(tasklist=self.TASKLIST_ID).execute.return_value = {}

        result = api_client.get_tasks(self.TASKLIST_ID)

        assert result == []

    def test_get_tasks_GIVEN_multiple_pages_THEN_returns_all_items(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().list.side_effect = self._mock_paginated_list

        result = api_client.get_tasks(self.TASKLIST_ID)

        assert result == self.PAGE1_ITEMS + self.PAGE2_ITEMS + self.PAGE3_ITEMS
        assert service.tasks().list.call_count == 3

    def test_get_tasks_GIVEN_max_results_THEN_returns_limited_items(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().list.side_effect = self._mock_paginated_list

        result = api_client.get_tasks(self.TASKLIST_ID, max_results=2)

        assert result == self.PAGE1_ITEMS + self.PAGE2_ITEMS
        assert len(result) == 2
        assert service.tasks().list.call_count == 2  # page 3 not reached


class TestAddTask:
    TASKLIST_ID = "tasklist123"
    TASK_TITLE = "New task"

    def test_add_task_GIVEN_title_only_THEN_creates_task_with_title(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        expected_task = {"id": "task1", "title": self.TASK_TITLE}
        service.tasks().insert(
            tasklist=self.TASKLIST_ID, body={"title": self.TASK_TITLE}
        ).execute.return_value = expected_task

        result = api_client.add_task(self.TASKLIST_ID, self.TASK_TITLE)

        assert result == expected_task
        service.tasks().insert.assert_called_with(
            tasklist=self.TASKLIST_ID, body={"title": self.TASK_TITLE}
        )

    def test_add_task_GIVEN_title_and_notes_THEN_creates_task_with_notes(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        notes = "Important details"
        expected_task = {"id": "task1", "title": self.TASK_TITLE, "notes": notes}
        service.tasks().insert(
            tasklist=self.TASKLIST_ID, body={"title": self.TASK_TITLE, "notes": notes}
        ).execute.return_value = expected_task

        result = api_client.add_task(self.TASKLIST_ID, self.TASK_TITLE, notes=notes)

        assert result == expected_task
        service.tasks().insert.assert_called_with(
            tasklist=self.TASKLIST_ID, body={"title": self.TASK_TITLE, "notes": notes}
        )

    def test_add_task_GIVEN_title_and_due_THEN_creates_task_with_due_date(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        due = "2026-01-15T00:00:00.000Z"
        expected_task = {"id": "task1", "title": self.TASK_TITLE, "due": due}
        service.tasks().insert(
            tasklist=self.TASKLIST_ID, body={"title": self.TASK_TITLE, "due": due}
        ).execute.return_value = expected_task

        result = api_client.add_task(self.TASKLIST_ID, self.TASK_TITLE, due=due)

        assert result == expected_task
        service.tasks().insert.assert_called_with(
            tasklist=self.TASKLIST_ID, body={"title": self.TASK_TITLE, "due": due}
        )

    def test_add_task_GIVEN_all_params_THEN_creates_task_with_all_fields(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        notes = "Important details"
        due = "2026-01-15T00:00:00.000Z"
        expected_body = {"title": self.TASK_TITLE, "notes": notes, "due": due}
        expected_task = {"id": "task1", **expected_body}
        service.tasks().insert(
            tasklist=self.TASKLIST_ID, body=expected_body
        ).execute.return_value = expected_task

        result = api_client.add_task(
            self.TASKLIST_ID, self.TASK_TITLE, notes=notes, due=due
        )

        assert result == expected_task
        service.tasks().insert.assert_called_with(
            tasklist=self.TASKLIST_ID, body=expected_body
        )


class TestDeleteTask:
    TASKLIST_ID = "tasklist123"
    TASK_ID = "task456"

    def test_delete_task_GIVEN_valid_ids_THEN_calls_delete(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        api_client.delete_task(self.TASKLIST_ID, self.TASK_ID)

        service.tasks().delete.assert_called_with(
            tasklist=self.TASKLIST_ID, task=self.TASK_ID
        )
        service.tasks().delete(
            tasklist=self.TASKLIST_ID, task=self.TASK_ID
        ).execute.assert_called_once()
