import argparse
from configparser import ConfigParser
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pytest import CaptureFixture

from gtasks.cli.cli import build_parser
from gtasks.cli.errors import Cancelled, CliError
from gtasks.cli.title_id_resolution import (
    ENV_VAR,
    TargetList,
    choose_tasklist,
    match_title,
    resolve_target_tasklist,
    resolve_tasks_from_inputs,
)
from gtasks.utils.config import LEGACY_DEFAULT_TASKLIST_KEY, Config, ConfigKey
from gtasks.utils.listing_state import ListingState

WORK = {"id": "list1", "title": "Work"}
WORK_DUPE = {"id": "list2", "title": "Work"}
HOME = {"id": "list3", "title": "Home"}
DEFAULT = {"id": "default-id", "title": "My Tasks"}


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(tmp_path / "config.toml", ConfigParser())


@pytest.fixture
def mock_client() -> Mock:
    client = Mock()
    client.get_tasklist.return_value = DEFAULT
    client.get_tasklists.return_value = [DEFAULT, WORK, HOME]
    return client


def _args(tasklist_title: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(tasklist_title=tasklist_title)


class TestResolveTargetTasklist:
    def test_GIVEN_flag_THEN_resolves_title_with_canonical_casing(
        self, mock_client: Mock, config: Config
    ) -> None:
        result = resolve_target_tasklist(_args("work"), mock_client, config, environ={})

        assert result == TargetList("list1", "Work")

    def test_GIVEN_flag_and_env_and_active_THEN_flag_wins(
        self, mock_client: Mock, config: Config
    ) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "active-id")

        result = resolve_target_tasklist(
            _args("Work"), mock_client, config, environ={ENV_VAR: "Home"}
        )

        assert result.id == "list1"

    def test_GIVEN_env_and_active_THEN_env_wins(self, mock_client: Mock, config: Config) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "active-id")

        result = resolve_target_tasklist(_args(), mock_client, config, environ={ENV_VAR: "Work"})

        assert result.id == "list1"

    def test_GIVEN_active_list_THEN_uses_stored_id_without_api_call(
        self, mock_client: Mock, config: Config
    ) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "active-id")
        config.set(ConfigKey.ACTIVE_TASKLIST_TITLE, "Groceries")

        result = resolve_target_tasklist(_args(), mock_client, config, environ={})

        assert result == TargetList("active-id", "Groceries")
        assert mock_client.mock_calls == []

    def test_GIVEN_nothing_set_THEN_falls_back_to_account_default(
        self, mock_client: Mock, config: Config
    ) -> None:
        result = resolve_target_tasklist(_args(), mock_client, config, environ={})

        assert result == TargetList("default-id", "My Tasks")
        mock_client.get_tasklist.assert_called_once_with("@default")

    def test_GIVEN_unknown_title_THEN_raises_cli_error(
        self, mock_client: Mock, config: Config
    ) -> None:
        with pytest.raises(CliError, match="No task list named 'Nope'"):
            resolve_target_tasklist(_args("Nope"), mock_client, config, environ={})

    def test_GIVEN_unknown_title_THEN_hint_refreshes_the_cached_lists(
        self, mock_client: Mock, config: Config
    ) -> None:
        """Lookups use cached lists, so the hint must lead to a fresh fetch (one created
        elsewhere in the last 30 minutes wouldn't appear in a cached `gtasks lists`)."""
        mock_client.get_tasklists.return_value = []

        with pytest.raises(CliError) as exc:
            resolve_target_tasklist(_args("New"), mock_client, config, environ={})

        assert exc.value.hint is not None and "gtasks lists --refresh" in exc.value.hint


class TestLegacyMigration:
    @pytest.fixture
    def legacy_config(self, tmp_path: Path) -> Config:
        path = tmp_path / "config.toml"
        path.write_text(f"[DEFAULT]\n{LEGACY_DEFAULT_TASKLIST_KEY} = work\n")
        return Config(path, ConfigParser())

    def test_GIVEN_legacy_title_THEN_stores_id_and_drops_legacy_key(
        self, mock_client: Mock, legacy_config: Config
    ) -> None:
        result = resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert result == TargetList("list1", "Work")
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list1"
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_TITLE) == "Work"
        assert legacy_config.get_raw(LEGACY_DEFAULT_TASKLIST_KEY) is None

    def test_GIVEN_legacy_title_no_longer_exists_THEN_warns_and_uses_default(
        self, mock_client: Mock, legacy_config: Config, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.get_tasklists.return_value = [DEFAULT]

        result = resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert result.id == "default-id"
        assert "no longer exists" in capsys.readouterr().err
        assert legacy_config.get_raw(LEGACY_DEFAULT_TASKLIST_KEY) is None
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_ID) is None

    def test_GIVEN_legacy_title_is_ambiguous_THEN_prompts_once_and_stores_choice(
        self, mock_client: Mock, legacy_config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [WORK, WORK_DUPE]

        with patch("builtins.input", return_value="2") as mock_input:
            resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})
            resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert mock_input.call_count == 1
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_ID) == "list2"

    def test_GIVEN_ambiguous_legacy_prompt_cancelled_THEN_keeps_legacy_key(
        self, mock_client: Mock, legacy_config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [WORK, WORK_DUPE]

        with patch("builtins.input", return_value="q"), pytest.raises(Cancelled):
            resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert legacy_config.get_raw(LEGACY_DEFAULT_TASKLIST_KEY) == "work"


class TestChooseTasklist:
    def test_GIVEN_single_match_THEN_returns_without_prompting(self) -> None:
        mock_input = Mock()

        assert choose_tasklist([WORK], "Work", mock_input) == WORK
        mock_input.assert_not_called()

    def test_GIVEN_duplicates_THEN_prompts(self) -> None:
        assert choose_tasklist([WORK, WORK_DUPE], "Work", Mock(return_value="2")) == WORK_DUPE

    def test_GIVEN_duplicates_and_cancel_THEN_raises_cancelled(self) -> None:
        with pytest.raises(Cancelled):
            choose_tasklist([WORK, WORK_DUPE], "Work", Mock(return_value="q"))


class TestTasklistOption:
    @pytest.mark.parametrize(
        "argv",
        [
            ["-l", "Work", "done", "1"],
            ["done", "1", "-l", "Work"],
            ["done", "1", "--list", "Work"],
            ["-l", "Work"],
        ],
        ids=["before-subcommand", "after-subcommand", "long-form", "bare"],
    )
    def test_GIVEN_list_flag_anywhere_THEN_parsed(self, argv: list[str]) -> None:
        assert build_parser().parse_args(argv).tasklist_title == "Work"

    def test_GIVEN_no_list_flag_THEN_none(self) -> None:
        assert build_parser().parse_args(["done", "1"]).tasklist_title is None


class TestMatchTitle:
    def test_match_title_GIVEN_different_case_THEN_matches(self) -> None:
        assert match_title([WORK, HOME], "wORK") == [WORK]

    def test_match_title_GIVEN_no_match_THEN_returns_empty(self) -> None:
        assert match_title([WORK, HOME], "Gym") == []

    def test_match_title_GIVEN_prefix_only_THEN_does_not_match(self) -> None:
        assert match_title([WORK], "Wor") == []

    def test_match_title_GIVEN_duplicates_THEN_returns_all(self) -> None:
        dupe = {"id": "list4", "title": "work"}

        assert match_title([WORK, HOME, dupe], "Work") == [WORK, dupe]

    def test_match_title_GIVEN_item_without_id_THEN_skips_it(self) -> None:
        assert match_title([{"title": "Work"}, WORK], "Work") == [WORK]


class TestResolveTasksFromInputs:
    SAMPLE_TASKS = [
        {"id": "task1", "title": "Buy milk", "status": "needsAction"},
        {"id": "task2", "title": "Walk dog", "status": "needsAction"},
        {"id": "task3", "title": "Call dentist", "status": "needsAction"},
    ]

    @pytest.fixture
    def mock_client(self) -> Mock:
        client = Mock()
        client.get_tasks.return_value = self.SAMPLE_TASKS
        return client

    def test_GIVEN_single_index_THEN_resolves_to_task_object(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["1"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0]]
        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)

    def test_GIVEN_multiple_indices_THEN_resolves_all(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["1", "3"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0], self.SAMPLE_TASKS[2]]

    def test_GIVEN_title_input_THEN_matches_against_open_tasks_only(
        self, mock_client: Mock
    ) -> None:
        resolve_tasks_from_inputs(["Walk dog"], mock_client, "list1")

        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)

    def test_GIVEN_title_input_THEN_returns_task_object(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["Walk dog"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[1]]

    def test_GIVEN_title_in_different_case_THEN_matches(self, mock_client: Mock) -> None:
        result = resolve_tasks_from_inputs(["WALK DOG"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[1]]

    def test_GIVEN_out_of_range_index_THEN_raises(self, mock_client: Mock) -> None:
        with pytest.raises(CliError, match="no task #99"):
            resolve_tasks_from_inputs(["99"], mock_client, "list1")

    def test_GIVEN_mixed_index_and_title_THEN_resolves_both(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["1", "Call dentist"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0], self.SAMPLE_TASKS[2]]
        mock_client.get_tasks.assert_called_once()

    def test_GIVEN_unresolvable_title_THEN_raises(self, mock_client: Mock) -> None:
        with pytest.raises(CliError, match="No task named 'Nonexistent'"):
            resolve_tasks_from_inputs(["Nonexistent"], mock_client, "list1")

    def test_GIVEN_bad_input_after_good_one_THEN_raises_before_returning_any(
        self, mock_client: Mock
    ) -> None:
        with pytest.raises(CliError):
            resolve_tasks_from_inputs(["1", "99"], mock_client, "list1")

    def test_GIVEN_same_task_twice_THEN_returned_once(self, mock_client: Mock) -> None:
        result = resolve_tasks_from_inputs(["1", "Buy milk", "1"], mock_client, "list1")

        assert result == [self.SAMPLE_TASKS[0]]

    def test_GIVEN_duplicate_titles_THEN_prompts(self, mock_client: Mock) -> None:
        dupes = [{"id": "a", "title": "Same"}, {"id": "b", "title": "Same"}]
        mock_client.get_tasks.return_value = dupes

        with patch("builtins.input", return_value="2"):
            result = resolve_tasks_from_inputs(["Same"], mock_client, "list1")

        assert result == [dupes[1]]


class TestResolveAgainstLastListing:
    """Numbers resolve against what the user was last shown, not the current list."""

    SHOWN = [{"id": "task1", "title": "Buy milk"}, {"id": "task2", "title": "Walk dog"}]

    @pytest.fixture
    def listing(self, tmp_path: Path) -> ListingState:
        listing = ListingState(tmp_path)
        listing.save("list1", self.SHOWN)
        return listing

    def test_GIVEN_listing_for_list_THEN_uses_it_without_fetching(
        self, listing: ListingState
    ) -> None:
        client = Mock()

        result = resolve_tasks_from_inputs(["2"], client, "list1", listing)

        assert result == [self.SHOWN[1]]
        client.get_tasks.assert_not_called()

    def test_GIVEN_listing_for_other_list_THEN_falls_back_to_fetch(
        self, listing: ListingState
    ) -> None:
        client = Mock()
        client.get_tasks.return_value = [{"id": "x", "title": "Other"}]

        result = resolve_tasks_from_inputs(["1"], client, "list2", listing)

        assert result == [{"id": "x", "title": "Other"}]

    def test_GIVEN_index_past_listing_THEN_raises_with_count(
        self, listing: ListingState
    ) -> None:
        with pytest.raises(CliError, match="showed 2"):
            resolve_tasks_from_inputs(["3"], Mock(), "list1", listing)

    def test_GIVEN_consumed_row_THEN_raises_already_done(self, listing: ListingState) -> None:
        listing.consume("list1", ["task1"])

        with pytest.raises(CliError, match="already completed or deleted"):
            resolve_tasks_from_inputs(["1"], Mock(), "list1", listing)
