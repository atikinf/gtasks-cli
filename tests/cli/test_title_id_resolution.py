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
    ResolvedTasks,
    TargetList,
    choose_tasklist,
    resolve_target_tasklist,
    resolve_tasks_from_inputs,
)
from gtasks.cli.title_matching import match_titles
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

        assert choose_tasklist(match_titles([WORK], "Work"), "Work", mock_input) == WORK
        mock_input.assert_not_called()

    def test_GIVEN_duplicates_THEN_prompts(self) -> None:
        match = match_titles([WORK, WORK_DUPE], "Work")

        assert choose_tasklist(match, "Work", Mock(return_value="2")) == WORK_DUPE

    def test_GIVEN_duplicates_and_cancel_THEN_raises_cancelled(self) -> None:
        with pytest.raises(Cancelled):
            choose_tasklist(match_titles([WORK, WORK_DUPE], "Work"), "Work", Mock(return_value="q"))


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


class TestFindTasklistMatching:
    """List lookups (-l, $GTASKS_LIST, `use NAME`) accept a fragment: switching is reversible."""

    @pytest.mark.parametrize(
        "typed", ["wor", "WORK", "  work "], ids=["fragment", "case", "spacing"]
    )
    def test_GIVEN_unique_match_THEN_resolves_without_prompt(
        self, mock_client: Mock, config: Config, typed: str
    ) -> None:
        with patch("builtins.input") as mock_input:
            result = resolve_target_tasklist(_args(typed), mock_client, config, environ={})

        assert result.id == "list1"
        mock_input.assert_not_called()

    def test_GIVEN_exact_title_also_contained_in_another_THEN_exact_wins(
        self, mock_client: Mock, config: Config
    ) -> None:
        mock_client.get_tasklists.return_value = [{"id": "x", "title": "Work trips"}, WORK]

        assert resolve_target_tasklist(_args("work"), mock_client, config, environ={}).id == "list1"

    def test_GIVEN_fragment_of_several_THEN_picker_says_match(
        self, mock_client: Mock, config: Config, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.get_tasklists.return_value = [WORK, {"id": "x", "title": "Homework"}]

        with patch("builtins.input", return_value="2"):
            result = resolve_target_tasklist(_args("wor"), mock_client, config, environ={})

        assert result.id == "x"
        assert "Several task lists match 'wor':" in capsys.readouterr().out

    def test_GIVEN_typo_THEN_error_suggests_close_title(
        self, mock_client: Mock, config: Config
    ) -> None:
        with pytest.raises(CliError) as exc:
            resolve_target_tasklist(_args("Wrok"), mock_client, config, environ={})

        assert exc.value.hint is not None
        assert exc.value.hint.startswith("Did you mean 'Work'?")

    def test_GIVEN_near_miss_in_stale_cache_THEN_hint_still_offers_refresh(
        self, mock_client: Mock, config: Config
    ) -> None:
        """A list created elsewhere ("Camping") isn't in the cached lists yet; the near-miss
        suggestion may be wrong, so the refresh advice must survive."""
        mock_client.get_tasklists.return_value = [{"id": "x", "title": "Clamping"}]

        with pytest.raises(CliError) as exc:
            resolve_target_tasklist(_args("Camping"), mock_client, config, environ={})

        assert exc.value.hint is not None
        assert "Did you mean 'Clamping'?" in exc.value.hint
        assert "gtasks lists --refresh" in exc.value.hint

    def test_GIVEN_legacy_title_only_partially_matching_THEN_not_migrated(
        self, mock_client: Mock, tmp_path: Path
    ) -> None:
        """Migration must never guess: a legacy "Wor" doesn't become "Work"."""
        path = tmp_path / "config.toml"
        path.write_text(f"[DEFAULT]\n{LEGACY_DEFAULT_TASKLIST_KEY} = Wor\n")
        legacy_config = Config(path, ConfigParser())

        result = resolve_target_tasklist(_args(), mock_client, legacy_config, environ={})

        assert result.id == "default-id"
        assert legacy_config.get(ConfigKey.ACTIVE_TASKLIST_ID) is None


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

        assert result.tasks == [self.SAMPLE_TASKS[0]]
        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)

    def test_GIVEN_index_and_no_listing_THEN_counts_in_displayed_order(
        self, mock_client: Mock
    ) -> None:
        mock_client.get_tasks.return_value = [
            {"id": "later", "title": "B", "position": "00000000000000000001"},
            {"id": "first", "title": "A", "position": "00000000000000000000"},
        ]

        result = resolve_tasks_from_inputs(["1"], mock_client, "list1")

        assert [t["id"] for t in result.tasks] == ["first"]

    def test_GIVEN_multiple_indices_THEN_resolves_all(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["1", "3"], mock_client, "list1")

        assert result.tasks == [self.SAMPLE_TASKS[0], self.SAMPLE_TASKS[2]]

    def test_GIVEN_title_input_THEN_matches_against_open_tasks_only(
        self, mock_client: Mock
    ) -> None:
        resolve_tasks_from_inputs(["Walk dog"], mock_client, "list1")

        mock_client.get_tasks.assert_called_once_with("list1", show_completed=False)

    def test_GIVEN_title_input_THEN_returns_task_object(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["Walk dog"], mock_client, "list1")

        assert result.tasks == [self.SAMPLE_TASKS[1]]

    def test_GIVEN_out_of_range_index_THEN_raises(self, mock_client: Mock) -> None:
        with pytest.raises(CliError, match="no task #99"):
            resolve_tasks_from_inputs(["99"], mock_client, "list1")

    def test_GIVEN_mixed_index_and_title_THEN_resolves_both(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["1", "Call dentist"], mock_client, "list1")

        assert result.tasks == [self.SAMPLE_TASKS[0], self.SAMPLE_TASKS[2]]
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

        assert result.tasks == [self.SAMPLE_TASKS[0]]

    def test_GIVEN_duplicate_titles_THEN_prompts(self, mock_client: Mock) -> None:
        dupes = [{"id": "a", "title": "Same"}, {"id": "b", "title": "Same"}]
        mock_client.get_tasks.return_value = dupes

        with patch("builtins.input", return_value="2"):
            result = resolve_tasks_from_inputs(["Same"], mock_client, "list1")

        assert result.tasks == [dupes[1]]


class TestPartialTaskMatching:
    TASKS = [
        {"id": "t1", "title": "Buy milk"},
        {"id": "t2", "title": "Buy oat milk"},
        {"id": "t3", "title": "Call dentist"},
    ]

    @pytest.fixture
    def mock_client(self) -> Mock:
        client = Mock()
        client.get_tasks.return_value = self.TASKS
        return client

    def test_GIVEN_unique_fragment_THEN_resolved_and_flagged_partial(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["dent"], mock_client, "l1")

        assert result == ResolvedTasks(tasks=[self.TASKS[2]], partial=[self.TASKS[2]])

    def test_GIVEN_exact_title_and_number_THEN_nothing_flagged_partial(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["buy MILK", "3"], mock_client, "l1")

        assert result.tasks == [self.TASKS[0], self.TASKS[2]]
        assert result.partial == []

    def test_GIVEN_fragment_of_several_THEN_prompts_and_choice_not_flagged(
        self, mock_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        """Picking from the numbered list is explicit: `delete` mustn't ask a second time."""
        with patch("builtins.input", return_value="2"):
            result = resolve_tasks_from_inputs(["milk"], mock_client, "l1")

        assert result.tasks == [self.TASKS[1]]
        assert result.partial == []
        assert "Several tasks match 'milk':" in capsys.readouterr().out

    def test_GIVEN_typo_THEN_did_you_mean(self, mock_client: Mock) -> None:
        with pytest.raises(CliError) as exc:
            resolve_tasks_from_inputs(["Call dnetist"], mock_client, "l1")

        assert exc.value.hint is not None
        assert exc.value.hint.startswith("Did you mean 'Call dentist'?")

    def test_GIVEN_same_task_by_fragment_and_number_THEN_once_still_partial(
        self, mock_client: Mock
    ) -> None:
        result = resolve_tasks_from_inputs(["3", "dent"], mock_client, "l1")

        assert result.tasks == [self.TASKS[2]]
        assert result.partial == [self.TASKS[2]]


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

        assert result.tasks == [self.SHOWN[1]]
        client.get_tasks.assert_not_called()

    def test_GIVEN_listing_for_other_list_THEN_falls_back_to_fetch(
        self, listing: ListingState
    ) -> None:
        client = Mock()
        client.get_tasks.return_value = [{"id": "x", "title": "Other"}]

        result = resolve_tasks_from_inputs(["1"], client, "list2", listing)

        assert result.tasks == [{"id": "x", "title": "Other"}]

    def test_GIVEN_index_past_listing_THEN_raises_with_count(
        self, listing: ListingState
    ) -> None:
        with pytest.raises(CliError, match="showed 2"):
            resolve_tasks_from_inputs(["3"], Mock(), "list1", listing)

    def test_GIVEN_consumed_row_THEN_raises_already_done(self, listing: ListingState) -> None:
        listing.consume("list1", ["task1"])

        with pytest.raises(CliError, match="already completed or deleted"):
            resolve_tasks_from_inputs(["1"], Mock(), "list1", listing)
