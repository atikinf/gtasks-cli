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
        service.tasks().list.assert_called_with(tasklist=self.TASKLIST_ID, showCompleted=True)

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

    def test_get_tasks_GIVEN_show_completed_false_THEN_passes_to_api(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().list().execute.return_value = {"items": []}

        api_client.get_tasks(self.TASKLIST_ID, show_completed=False)

        service.tasks().list.assert_called_with(
            tasklist=self.TASKLIST_ID, showCompleted=False
        )

    def test_get_tasks_GIVEN_completed_min_THEN_passes_to_api(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        cutoff = "2026-04-22T00:00:00+00:00"
        service.tasks().list().execute.return_value = {"items": []}

        api_client.get_tasks(self.TASKLIST_ID, completed_min=cutoff)

        service.tasks().list.assert_called_with(
            tasklist=self.TASKLIST_ID, showCompleted=True, completedMin=cutoff
        )

    def test_get_tasks_GIVEN_no_completed_min_THEN_omits_from_api(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().list().execute.return_value = {"items": []}

        api_client.get_tasks(self.TASKLIST_ID)

        call_kwargs = service.tasks().list.call_args.kwargs
        assert "completedMin" not in call_kwargs


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

    def test_add_task_GIVEN_parent_and_previous_THEN_passes_to_insert_kwargs(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().insert().execute.return_value = {"id": "task1"}

        api_client.add_task(
            self.TASKLIST_ID,
            self.TASK_TITLE,
            parent_task_id="parent1",
            previous_task_id="prev1",
        )

        service.tasks().insert.assert_called_with(
            tasklist=self.TASKLIST_ID,
            body={"title": self.TASK_TITLE},
            parent="parent1",
            previous="prev1",
        )


class TestDeleteTasks:
    TASKLIST_ID = "tasklist123"
    TASK_IDS = ["task1", "task2", "task3"]

    def test_delete_tasks_GIVEN_multiple_ids_THEN_batches_deletes(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        batch_mock = MagicMock()
        service.new_batch_http_request.return_value = batch_mock

        api_client.delete_tasks(self.TASKLIST_ID, self.TASK_IDS)

        service.new_batch_http_request.assert_called_once()
        assert batch_mock.add.call_count == 3
        batch_mock.execute.assert_called_once()

    def test_delete_tasks_GIVEN_batch_error_THEN_raises_exception_group(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        def fake_execute_with_error():
            cb = service.new_batch_http_request.call_args.kwargs.get("callback")
            if cb:
                cb("0", None, Exception("API error"))

        batch_mock = MagicMock()
        batch_mock.execute.side_effect = fake_execute_with_error
        service.new_batch_http_request.return_value = batch_mock

        with pytest.raises(ExceptionGroup):
            api_client.delete_tasks(self.TASKLIST_ID, self.TASK_IDS[:1])


class TestCompleteTasks:
    TASKLIST_ID = "tasklist123"
    TASK_IDS = ["task1", "task2"]

    def test_complete_tasks_GIVEN_multiple_ids_THEN_batches_patches(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        batch_mock = MagicMock()
        service.new_batch_http_request.return_value = batch_mock

        api_client.complete_tasks(self.TASKLIST_ID, self.TASK_IDS)

        service.new_batch_http_request.assert_called_once()
        assert batch_mock.add.call_count == 2
        batch_mock.execute.assert_called_once()
        service.tasks().patch.assert_any_call(
            tasklist=self.TASKLIST_ID, task="task1", body={"status": "completed"}
        )

    def test_complete_tasks_GIVEN_callback_receives_responses_THEN_returns_them(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        completed_tasks = [
            {"id": "task1", "status": "completed"},
            {"id": "task2", "status": "completed"},
        ]

        def fake_execute_with_callbacks():
            cb = service.new_batch_http_request.call_args.kwargs.get("callback")
            if cb:
                cb("0", completed_tasks[0], None)
                cb("1", completed_tasks[1], None)

        batch_mock = MagicMock()
        batch_mock.execute.side_effect = fake_execute_with_callbacks
        service.new_batch_http_request.return_value = batch_mock

        results = api_client.complete_tasks(self.TASKLIST_ID, self.TASK_IDS)

        assert results == completed_tasks

    def test_complete_tasks_GIVEN_batch_error_THEN_raises_exception_group(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        def fake_execute_with_error():
            cb = service.new_batch_http_request.call_args.kwargs.get("callback")
            if cb:
                cb("0", None, Exception("API error"))

        batch_mock = MagicMock()
        batch_mock.execute.side_effect = fake_execute_with_error
        service.new_batch_http_request.return_value = batch_mock

        with pytest.raises(ExceptionGroup):
            api_client.complete_tasks(self.TASKLIST_ID, self.TASK_IDS[:1])


class TestGetTasklist:
    TASKLIST_ID = "tasklist123"

    def test_get_tasklist_GIVEN_valid_id_THEN_returns_tasklist(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        expected_tasklist = {"id": self.TASKLIST_ID, "title": "Work"}
        service.tasklists().get(
            tasklist=self.TASKLIST_ID
        ).execute.return_value = expected_tasklist

        result = api_client.get_tasklist(self.TASKLIST_ID)

        assert result == expected_tasklist
        service.tasklists().get.assert_called_with(tasklist=self.TASKLIST_ID)


class TestAddTasklist:
    TASKLIST_TITLE = "Groceries"

    def test_add_tasklist_GIVEN_title_THEN_creates_tasklist(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        expected_tasklist = {"id": "list1", "title": self.TASKLIST_TITLE}
        service.tasklists().insert(
            body={"title": self.TASKLIST_TITLE}
        ).execute.return_value = expected_tasklist

        result = api_client.add_tasklist(self.TASKLIST_TITLE)

        assert result == expected_tasklist
        service.tasklists().insert.assert_called_with(body={"title": self.TASKLIST_TITLE})


class TestRenameTasklist:
    TASKLIST_ID = "tasklist123"
    NEW_TITLE = "Renamed"

    def test_rename_tasklist_GIVEN_new_title_THEN_patches_title(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        expected_tasklist = {"id": self.TASKLIST_ID, "title": self.NEW_TITLE}
        service.tasklists().patch(
            tasklist=self.TASKLIST_ID, body={"title": self.NEW_TITLE}
        ).execute.return_value = expected_tasklist

        result = api_client.rename_tasklist(self.TASKLIST_ID, self.NEW_TITLE)

        assert result == expected_tasklist
        service.tasklists().patch.assert_called_with(
            tasklist=self.TASKLIST_ID, body={"title": self.NEW_TITLE}
        )


class TestDeleteTasklist:
    TASKLIST_ID = "tasklist123"

    def test_delete_tasklist_GIVEN_valid_id_THEN_deletes(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        api_client.delete_tasklist(self.TASKLIST_ID)

        service.tasklists().delete.assert_called_with(tasklist=self.TASKLIST_ID)


class TestGetTask:
    TASKLIST_ID = "tasklist123"
    TASK_ID = "task1"

    def test_get_task_GIVEN_valid_ids_THEN_returns_task(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        expected_task = {"id": self.TASK_ID, "title": "Buy milk"}
        service.tasks().get(
            tasklist=self.TASKLIST_ID, task=self.TASK_ID
        ).execute.return_value = expected_task

        result = api_client.get_task(self.TASKLIST_ID, self.TASK_ID)

        assert result == expected_task
        service.tasks().get.assert_called_with(
            tasklist=self.TASKLIST_ID, task=self.TASK_ID
        )


class TestUpdateTask:
    TASKLIST_ID = "tasklist123"
    TASK_ID = "task1"

    def test_update_task_GIVEN_title_only_THEN_patches_title(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().patch().execute.return_value = {"id": self.TASK_ID}

        api_client.update_task(self.TASKLIST_ID, self.TASK_ID, task_title="New title")

        service.tasks().patch.assert_called_with(
            tasklist=self.TASKLIST_ID, task=self.TASK_ID, body={"title": "New title"}
        )

    def test_update_task_GIVEN_notes_and_due_THEN_patches_both(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().patch().execute.return_value = {"id": self.TASK_ID}

        api_client.update_task(
            self.TASKLIST_ID, self.TASK_ID, notes="Updated notes", due="2026-02-01T00:00:00.000Z"
        )

        service.tasks().patch.assert_called_with(
            tasklist=self.TASKLIST_ID,
            task=self.TASK_ID,
            body={"notes": "Updated notes", "due": "2026-02-01T00:00:00.000Z"},
        )

    def test_update_task_GIVEN_no_fields_THEN_raises_value_error(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        with pytest.raises(ValueError):
            api_client.update_task(self.TASKLIST_ID, self.TASK_ID)


class TestMoveTask:
    TASKLIST_ID = "tasklist123"
    TASK_ID = "task1"

    def test_move_task_GIVEN_no_optional_params_THEN_omits_from_api(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().move().execute.return_value = {"id": self.TASK_ID}

        api_client.move_task(self.TASKLIST_ID, self.TASK_ID)

        call_kwargs = service.tasks().move.call_args.kwargs
        assert call_kwargs == {"tasklist": self.TASKLIST_ID, "task": self.TASK_ID}

    def test_move_task_GIVEN_all_optional_params_THEN_passes_to_api(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        service.tasks().move().execute.return_value = {"id": self.TASK_ID}

        api_client.move_task(
            self.TASKLIST_ID,
            self.TASK_ID,
            parent_task_id="parent1",
            previous_task_id="prev1",
            destination_tasklist_id="otherlist",
        )

        service.tasks().move.assert_called_with(
            tasklist=self.TASKLIST_ID,
            task=self.TASK_ID,
            parent="parent1",
            previous="prev1",
            destinationTasklist="otherlist",
        )


class TestReopenTasks:
    TASKLIST_ID = "tasklist123"
    TASK_IDS = ["task1", "task2"]

    def test_reopen_tasks_GIVEN_multiple_ids_THEN_batches_patches_with_needs_action_status(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        batch_mock = MagicMock()
        service.new_batch_http_request.return_value = batch_mock

        api_client.reopen_tasks(self.TASKLIST_ID, self.TASK_IDS)

        service.new_batch_http_request.assert_called_once()
        assert batch_mock.add.call_count == 2
        batch_mock.execute.assert_called_once()
        service.tasks().patch.assert_any_call(
            tasklist=self.TASKLIST_ID, task="task1", body={"status": "needsAction"}
        )

    def test_reopen_tasks_GIVEN_batch_error_THEN_raises_exception_group(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        def fake_execute_with_error():
            cb = service.new_batch_http_request.call_args.kwargs.get("callback")
            if cb:
                cb("0", None, Exception("API error"))

        batch_mock = MagicMock()
        batch_mock.execute.side_effect = fake_execute_with_error
        service.new_batch_http_request.return_value = batch_mock

        with pytest.raises(ExceptionGroup):
            api_client.reopen_tasks(self.TASKLIST_ID, self.TASK_IDS[:1])


class TestClearCompletedTasks:
    TASKLIST_ID = "tasklist123"

    def test_clear_completed_tasks_GIVEN_valid_id_THEN_clears(
        self, service: MagicMock, api_client: ApiClient
    ) -> None:
        api_client.clear_completed_tasks(self.TASKLIST_ID)

        service.tasks().clear.assert_called_with(tasklist=self.TASKLIST_ID)
