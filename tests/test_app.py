from collections.abc import Iterator
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from httplib2 import Response
from pytest import CaptureFixture

from gtasks.app import main
from gtasks.cli.errors import CliError
from gtasks.client.client_factory import SignInRequiredError


def _http_error(status: int) -> HttpError:
    return HttpError(Response({"status": status}), b"", uri="https://example")


@pytest.fixture
def mock_client(tmp_path: Path) -> Iterator[Mock]:
    """Patch out credentials and point config at a temp dir; yields the client main() gets."""
    client = Mock()
    with (
        patch("gtasks.app.build_client", return_value=client),
        patch("gtasks.app.CONFIG_FILE_PATH", tmp_path / "config.toml"),
    ):
        yield client


class TestMainErrorRouting:
    def test_main_GIVEN_cli_error_THEN_stderr_with_hint_and_exit_code(
        self, mock_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.get_tasklists.return_value = []

        code = main(["tasks", "-l", "Nope"])

        captured = capsys.readouterr()
        assert code == 1
        assert captured.out == ""
        assert "error: No task list named 'Nope'." in captured.err
        assert "hint:" in captured.err

    def test_main_GIVEN_custom_exit_code_THEN_returned(self, mock_client: Mock) -> None:
        mock_client.get_tasklist.side_effect = CliError("x", exit_code=7)

        assert main(["tasks"]) == 7

    def test_main_GIVEN_404_THEN_explains_and_suggests_use(
        self, mock_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.get_tasklist.side_effect = _http_error(404)

        code = main(["tasks"])

        assert code == 1
        assert "gtasks use" in capsys.readouterr().err

    def test_main_GIVEN_batch_failures_THEN_one_error_line_each(
        self, mock_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.get_tasklists.return_value = [{"id": "l1", "title": "W"}]
        mock_client.get_tasks.return_value = [{"id": "a", "title": "A"}, {"id": "b", "title": "B"}]
        mock_client.complete_tasks.side_effect = ExceptionGroup(
            "batch", [_http_error(500), ValueError("boom")]
        )

        code = main(["done", "1", "2", "-l", "W"])

        err_lines = [ln for ln in capsys.readouterr().err.splitlines() if ln.startswith("error:")]
        assert code == 1
        assert len(err_lines) == 2

    def test_main_GIVEN_ctrl_c_THEN_cancelled_exit_130(
        self, mock_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        mock_client.get_tasklist.side_effect = KeyboardInterrupt

        assert main(["tasks"]) == 130
        assert "Cancelled." in capsys.readouterr().err

    def test_main_GIVEN_client_construction_fails_THEN_same_error_format(
        self, tmp_path: Path, capsys: CaptureFixture[str]
    ) -> None:
        with (
            patch("gtasks.app.build_client", side_effect=FileNotFoundError("credentials.json")),
            patch("gtasks.app.CONFIG_FILE_PATH", tmp_path / "config.toml"),
        ):
            code = main(["tasks"])

        assert code == 1
        assert capsys.readouterr().err.startswith("error: credentials.json")


class TestMainClientConstruction:
    """The client (and so credentials/OAuth) is built only when a handler asks for it."""

    @pytest.fixture
    def build_client(self, tmp_path: Path) -> Iterator[Mock]:
        with (
            patch("gtasks.app.build_client") as build_client,
            patch("gtasks.app.CONFIG_FILE_PATH", tmp_path / "config.toml"),
        ):
            yield build_client

    def test_main_GIVEN_auth_on_first_run_THEN_never_builds_client(
        self, build_client: Mock
    ) -> None:
        build_client.side_effect = FileNotFoundError("credentials.json")

        with patch(
            "gtasks.cli.parsers.auth_parser.prompt_setup_credentials", return_value=None
        ):
            code = main(["auth"])

        assert code == 130  # reached auth's own prompt and the user cancelled
        build_client.assert_not_called()

    def test_main_GIVEN_config_THEN_never_builds_client(self, build_client: Mock) -> None:
        build_client.side_effect = FileNotFoundError("credentials.json")

        assert main(["config"]) == 0
        build_client.assert_not_called()

    def test_main_GIVEN_api_command_THEN_builds_client_once(self, build_client: Mock) -> None:
        build_client.return_value.get_tasklists.return_value = []

        assert main(["lists"]) == 0
        build_client.assert_called_once_with()


class TestMainSignInHint:
    """Every way of being signed out ends in the same pointer to `gtasks auth`."""

    @pytest.fixture
    def build_client(self, tmp_path: Path) -> Iterator[Mock]:
        with (
            patch("gtasks.app.build_client") as build_client,
            patch("gtasks.app.CONFIG_FILE_PATH", tmp_path / "config.toml"),
        ):
            yield build_client

    @pytest.mark.parametrize(
        "argv",
        [[], ["tasks"], ["lists"], ["add", "Milk"], ["done", "1"], ["delete", "1"], ["use", "W"]],
        ids=["bare", "tasks", "lists", "add", "done", "delete", "use"],
    )
    def test_main_GIVEN_never_signed_in_THEN_every_api_command_hints_auth(
        self, build_client: Mock, argv: list[str], capsys: CaptureFixture[str]
    ) -> None:
        build_client.side_effect = SignInRequiredError("no token, no credentials.json")

        code = main(argv)

        assert code == 1
        assert capsys.readouterr().err.splitlines() == [
            "error: You're not signed in to Google Tasks.",
            "hint: Run `gtasks auth` to sign in.",
        ]

    def test_main_GIVEN_refresh_fails_mid_request_THEN_hints_auth(
        self, build_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        build_client.return_value.get_tasklists.side_effect = RefreshError("invalid_grant")

        assert main(["lists"]) == 1
        assert "gtasks auth" in capsys.readouterr().err

    def test_main_GIVEN_401_THEN_hints_auth(
        self, build_client: Mock, capsys: CaptureFixture[str]
    ) -> None:
        build_client.return_value.get_tasklists.side_effect = _http_error(401)

        assert main(["lists"]) == 1
        assert "gtasks auth" in capsys.readouterr().err
