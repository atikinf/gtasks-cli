import argparse
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from gtasks import defaults
from gtasks.cli import completion
from gtasks.client.cache_store import DEFAULT_TTL_SECONDS, CacheStore, account_key
from gtasks.utils.config import Config, ConfigKey

LISTS = [{"id": "L1", "title": "Groceries"}, {"id": "L2", "title": "Work"}]
GROCERIES = [
    {"id": "t1", "title": "Buy milk"},
    {"id": "t2", "title": "buy oat milk"},
    {"id": "t3", "title": "Call dentist"},
]
WORK = [{"id": "w1", "title": "Budget review"}]


@pytest.fixture
def store() -> CacheStore:
    """A warm cache for one account, in the tmp CACHE_DIR set up by conftest."""
    store = CacheStore(defaults.CACHE_DIR, account_key("client", "token"))
    store.write_tasklists(LISTS)
    store.write_default(LISTS[0])
    store.write_tasks("L1", GROCERIES)
    store.write_tasks("L2", WORK)
    return store


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    path = tmp_path / "config.toml"
    monkeypatch.setattr(defaults, "CONFIG_FILE_PATH", path)
    return Config(path)


def _args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**{"tasklist_title": None, "tasks": [], **kwargs})


class TestCompleteTasklists:
    def test_GIVEN_prefix_any_case_THEN_matching_list_titles(self, store: CacheStore) -> None:
        assert completion.complete_tasklists("gro") == ["Groceries"]
        assert completion.complete_tasklists("") == ["Groceries", "Work"]

    def test_GIVEN_nothing_cached_THEN_nothing(self) -> None:
        assert completion.complete_tasklists("") == []

    def test_GIVEN_cache_expired_THEN_nothing(self) -> None:
        expired = time.time() - DEFAULT_TTL_SECONDS - 1
        CacheStore(defaults.CACHE_DIR, account_key("c", "r"), now=lambda: expired).write_tasklists(
            LISTS
        )

        assert completion.complete_tasklists("") == []


class TestCompleteTasks:
    def test_GIVEN_active_list_THEN_its_titles_by_prefix(
        self, store: CacheStore, config: Config
    ) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "L2")

        assert list(completion.complete_tasks("bu", _args())) == ["Budget review"]

    def test_GIVEN_no_active_list_THEN_default_list(
        self, store: CacheStore, config: Config
    ) -> None:
        assert list(completion.complete_tasks("BU", _args())) == ["Buy milk", "buy oat milk"]

    def test_GIVEN_list_flag_typed_THEN_that_list(self, store: CacheStore, config: Config) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "L1")

        assert list(completion.complete_tasks("", _args(tasklist_title="wor"))) == ["Budget review"]

    def test_GIVEN_env_list_THEN_that_list(
        self, store: CacheStore, config: Config, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GTASKS_LIST", "Work")

        assert list(completion.complete_tasks("", _args())) == ["Budget review"]

    def test_GIVEN_ambiguous_or_unknown_list_flag_THEN_nothing(
        self, store: CacheStore, config: Config
    ) -> None:
        assert list(completion.complete_tasks("", _args(tasklist_title="r"))) == []  # both lists
        assert list(completion.complete_tasks("", _args(tasklist_title="Gym"))) == []

    def test_GIVEN_titles_already_typed_THEN_not_offered_again(
        self, store: CacheStore, config: Config
    ) -> None:
        assert list(completion.complete_tasks("", _args(tasks=["buy MILK"]))) == [
            "buy oat milk",
            "Call dentist",
        ]

    def test_GIVEN_list_not_cached_THEN_nothing(self, store: CacheStore, config: Config) -> None:
        config.set(ConfigKey.ACTIVE_TASKLIST_ID, "L9")

        assert list(completion.complete_tasks("", _args())) == []

    def test_GIVEN_unexpected_error_THEN_nothing_rather_than_traceback(
        self, store: CacheStore, config: Config
    ) -> None:
        with patch.object(CacheStore, "read_tasks", side_effect=RuntimeError("boom")):
            assert list(completion.complete_tasks("", _args())) == []


class TestTaskDescriptions:
    def test_GIVEN_due_dates_THEN_described_by_relative_due(
        self, store: CacheStore, config: Config
    ) -> None:
        tomorrow = (date.today() + timedelta(days=1)).isoformat() + "T00:00:00.000Z"
        store.write_tasks(
            "L1",
            [{"id": "a", "title": "Buy milk", "due": tomorrow}, {"id": "b", "title": "Bread"}],
        )

        assert completion.complete_tasks("b", _args()) == {"Buy milk": "tomorrow", "Bread": ""}

    def test_GIVEN_duplicate_titles_THEN_first_tasks_description(
        self, store: CacheStore, config: Config
    ) -> None:
        store.write_tasks(
            "L1",
            [
                {"id": "a", "title": "Pay rent", "due": "2020-01-01T00:00:00.000Z"},
                {"id": "b", "title": "Pay rent"},
            ],
        )

        assert list(completion.complete_tasks("", _args()).values()) == ["overdue · Jan 1, 2020"]


class TestCompletionCommand:
    def test_zsh_snippet_THEN_case_insensitive_for_gtasks_only(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from gtasks.cli.parsers.completion_parser import cmd_completion

        cmd_completion(argparse.Namespace(shell="zsh"), lambda **_: None, None)

        out = capsys.readouterr().out
        assert out.startswith("#compdef gtasks")
        assert out.rstrip().endswith(
            "zstyle ':completion:*:*:gtasks:*' matcher-list 'm:{a-z}={A-Za-z}'"
        )

    @pytest.mark.parametrize("shell", ["bash", "fish"])
    def test_other_shells_THEN_no_zsh_settings(
        self, shell: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from gtasks.cli.parsers.completion_parser import cmd_completion

        cmd_completion(argparse.Namespace(shell=shell), lambda **_: None, None)

        assert "zstyle" not in capsys.readouterr().out


class TestCompleteConfig:
    def test_keys_and_values(self) -> None:
        assert completion.complete_config_keys("ca") == ["cache"]
        assert completion.complete_config_values("o", argparse.Namespace(key="cache")) == [
            "on",
            "off",
        ]
        assert completion.complete_config_values("", argparse.Namespace(key="nope")) == []


# --- End to end, through a real shell completion request -----------------------------------

_PROBE = """
import json, sys
from gtasks.app import main
try:
    main([])
finally:
    heavy = {"google", "googleapiclient", "google_auth_oauthlib", "httplib2", "dateparser"}
    loaded = sorted({m.split(".")[0] for m in sys.modules} & heavy)
    print(json.dumps(loaded), file=sys.stderr)
"""


def _complete(line: str, tmp_path: Path, shell: str = "bash") -> tuple[list[str], list[str]]:
    """Ask gtasks for completions the way the shell does; returns (candidates, heavy imports)."""
    out = tmp_path / "completions.txt"
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "XDG_CACHE_HOME": str(tmp_path / "xdg"),
        "_ARGCOMPLETE": "1",
        "_ARGCOMPLETE_SHELL": shell,
        "_ARGCOMPLETE_IFS": "\n",
        "_ARGCOMPLETE_STDOUT_FILENAME": str(out),
        "COMP_LINE": line,
        "COMP_POINT": str(len(line)),
    }
    env.pop("GTASKS_LIST", None)
    result = subprocess.run([sys.executable, "-c", _PROBE], env=env, capture_output=True, text=True)
    # A single match ends with a space so the shell moves on to the next word; ignore it here.
    raw = out.read_text().split("\n") if out.exists() else []
    candidates = [c.rstrip(" ") for c in raw if c]
    loaded = json.loads(result.stderr.strip().splitlines()[-1]) if result.stderr.strip() else []
    return candidates, loaded


@pytest.fixture
def warm_subprocess_cache(tmp_path: Path) -> None:
    store = CacheStore(tmp_path / "xdg" / "gtasks-cli", account_key("client", "token"))
    store.write_tasklists(LISTS)
    store.write_default(LISTS[0])
    store.write_tasks("L1", GROCERIES)


class TestShellCompletion:
    def test_GIVEN_task_prefix_THEN_titles_quoted_and_no_heavy_imports(
        self, tmp_path: Path, warm_subprocess_cache: None
    ) -> None:
        candidates, loaded = _complete("gtasks done bu", tmp_path)

        assert candidates == ["Buy\\ milk", "buy\\ oat\\ milk"]
        assert loaded == []

    def test_GIVEN_zsh_THEN_titles_with_descriptions(
        self, tmp_path: Path, warm_subprocess_cache: None
    ) -> None:
        candidates, _ = _complete("gtasks done bu", tmp_path, shell="zsh")

        # zsh receives "completion:description"; spaces and colons in titles are escaped.
        assert candidates == ["Buy\\ milk:", "buy\\ oat\\ milk:"]

    def test_GIVEN_list_flag_prefix_THEN_list_titles(
        self, tmp_path: Path, warm_subprocess_cache: None
    ) -> None:
        candidates, _ = _complete("gtasks -l G", tmp_path)

        assert candidates == ["Groceries"]

    def test_GIVEN_new_task_title_THEN_no_file_names_or_flags(
        self, tmp_path: Path, warm_subprocess_cache: None
    ) -> None:
        (tmp_path / "home").mkdir(exist_ok=True)

        candidates, _ = _complete("gtasks add ", tmp_path)

        assert candidates == []

    def test_GIVEN_subcommand_prefix_THEN_subcommands(self, tmp_path: Path) -> None:
        candidates, _ = _complete("gtasks de", tmp_path)

        assert candidates == ["delete"]

    def test_GIVEN_dash_typed_THEN_flags_offered(self, tmp_path: Path) -> None:
        candidates, _ = _complete("gtasks delete --y", tmp_path)

        assert candidates == ["--yes"]


class TestCompletionWithoutArgcomplete:
    def test_GIVEN_argcomplete_missing_THEN_exits_without_running_a_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A Tab press must never run `gtasks` (e.g. list tasks) inside the shell."""
        from gtasks.app import main

        monkeypatch.setenv("_ARGCOMPLETE", "1")
        monkeypatch.setitem(sys.modules, "argcomplete", None)  # makes the import fail
        with patch("gtasks.app.build_client") as build_client:
            assert main([]) == 0

        build_client.assert_not_called()
