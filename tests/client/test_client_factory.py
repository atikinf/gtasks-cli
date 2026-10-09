import json
import pickle
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.auth import _helpers
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from gtasks.client.api_client import ApiClient
from gtasks.client.cache_store import account_key
from gtasks.client.caching_client import CachingClient
from gtasks.client.client_factory import (
    SignInRequiredError,
    auth_from_file,
    build_client,
    build_tasks_resource,
    read_creds_from_file,
    write_creds_to_file,
)


def _creds(token: str = "access", *, expired: bool = False) -> Credentials:
    # google-auth compares expiry against a naive UTC "now".
    offset = timedelta(hours=-1 if expired else 1)
    return Credentials(
        token=token,
        refresh_token="refresh",
        client_id="client-id",
        client_secret="client-secret",
        token_uri="https://oauth2.googleapis.com/token",
        expiry=_helpers.utcnow() + offset,
    )


def _refreshed(self: Credentials, request: object) -> None:
    self.token = "refreshed"
    self.expiry = _helpers.utcnow() + timedelta(hours=1)


@pytest.fixture
def token_path(tmp_path: Path) -> Path:
    return tmp_path / "token.json"


@pytest.fixture
def creds_path(tmp_path: Path) -> Path:
    return tmp_path / "credentials.json"


@pytest.fixture
def flow_class():
    """InstalledAppFlow, signing in as a new valid token."""
    with patch("google_auth_oauthlib.flow.InstalledAppFlow") as flow_class:
        flow_class.from_client_secrets_file.return_value.run_local_server.return_value = (
            _creds("signed-in")
        )
        yield flow_class


def _saved_token(token_path: Path) -> str | None:
    return json.loads(token_path.read_text()).get("token")


class TestTokenFile:
    def test_write_then_read_GIVEN_creds_THEN_same_account_and_expiry(
        self, token_path: Path
    ) -> None:
        creds = _creds()

        write_creds_to_file(creds, token_path)
        loaded = read_creds_from_file(token_path)

        assert loaded is not None
        assert (loaded.client_id, loaded.refresh_token, loaded.token) == (
            "client-id",
            "refresh",
            "access",
        )
        assert loaded.valid  # expiry survives, so no refresh is needed on every run

    def test_write_creds_to_file_THEN_owner_only(self, token_path: Path) -> None:
        write_creds_to_file(_creds(), token_path)

        assert token_path.stat().st_mode & 0o777 == 0o600

    def test_write_creds_to_file_GIVEN_nested_path_THEN_creates_parent_dirs(
        self, tmp_path: Path
    ) -> None:
        nested = tmp_path / "nested" / "dir" / "token.json"

        write_creds_to_file(_creds(), nested)

        assert read_creds_from_file(nested) is not None

    def test_write_creds_to_file_THEN_no_temp_files_left(self, token_path: Path) -> None:
        write_creds_to_file(_creds(), token_path)

        assert [p.name for p in token_path.parent.iterdir()] == ["token.json"]

    @pytest.mark.parametrize(
        "content", ["", "not json", "[]", json.dumps({"token": "no refresh token"})]
    )
    def test_read_creds_from_file_GIVEN_unusable_file_THEN_none(
        self, token_path: Path, content: str
    ) -> None:
        token_path.write_text(content)

        assert read_creds_from_file(token_path) is None

    def test_read_creds_from_file_GIVEN_no_file_THEN_none(self, token_path: Path) -> None:
        assert read_creds_from_file(token_path) is None


class TestLegacyPickleMigration:
    def test_GIVEN_legacy_pickle_THEN_migrated_to_json_and_removed(
        self, token_path: Path
    ) -> None:
        legacy = token_path.with_suffix(".pickle")
        legacy.write_bytes(pickle.dumps(_creds()))

        creds = read_creds_from_file(token_path)

        assert creds is not None and creds.refresh_token == "refresh"
        assert _saved_token(token_path) == "access"
        assert not legacy.exists()

    def test_GIVEN_unloadable_legacy_pickle_THEN_none_and_left_in_place(
        self, token_path: Path
    ) -> None:
        """E.g. pickled by another google-auth version: that install may still read it."""
        legacy = token_path.with_suffix(".pickle")
        legacy.write_bytes(b"\x80\x04not a pickle")

        assert read_creds_from_file(token_path) is None
        assert legacy.exists()
        assert not token_path.exists()

    def test_GIVEN_json_and_legacy_pickle_THEN_json_wins(self, token_path: Path) -> None:
        write_creds_to_file(_creds("from-json"), token_path)
        token_path.with_suffix(".pickle").write_bytes(pickle.dumps(_creds("from-pickle")))

        creds = read_creds_from_file(token_path)

        assert creds is not None and creds.token == "from-json"


class TestLoadCredentials:
    def test_GIVEN_valid_saved_token_THEN_used_without_signing_in(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        write_creds_to_file(_creds(), token_path)

        result = auth_from_file(token_path, creds_path)

        assert result.token == "access"
        flow_class.from_client_secrets_file.assert_not_called()

    def test_GIVEN_expired_token_THEN_refreshed_and_saved(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        write_creds_to_file(_creds(expired=True), token_path)

        with patch.object(Credentials, "refresh", autospec=True, side_effect=_refreshed):
            result = auth_from_file(token_path, creds_path)

        assert result.token == "refreshed"
        assert _saved_token(token_path) == "refreshed"
        flow_class.from_client_secrets_file.assert_not_called()

    def test_GIVEN_no_saved_token_THEN_signs_in_and_saves(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        result = auth_from_file(token_path, creds_path)

        flow_class.from_client_secrets_file.assert_called_once_with(
            str(creds_path), ["https://www.googleapis.com/auth/tasks"]
        )
        assert result.token == "signed-in"
        assert _saved_token(token_path) == "signed-in"

    def test_GIVEN_corrupt_token_THEN_signs_in_and_replaces_it(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        token_path.write_text("{ not json")

        result = auth_from_file(token_path, creds_path)

        assert result.token == "signed-in"
        assert _saved_token(token_path) == "signed-in"

    def test_GIVEN_refresh_fails_THEN_signs_in_again(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        write_creds_to_file(_creds(expired=True), token_path)

        with patch.object(Credentials, "refresh", side_effect=RefreshError("invalid_grant")):
            result = auth_from_file(token_path, creds_path)

        assert result.token == "signed-in"
        assert _saved_token(token_path) == "signed-in"  # the new sign-in is saved

    def test_GIVEN_legacy_pickle_only_THEN_used_without_signing_in(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        token_path.with_suffix(".pickle").write_bytes(pickle.dumps(_creds()))

        result = auth_from_file(token_path, creds_path)

        assert result.token == "access"
        flow_class.from_client_secrets_file.assert_not_called()


class TestSignInRequired:
    def test_GIVEN_no_token_and_no_credentials_file_THEN_sign_in_required(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        flow_class.from_client_secrets_file.side_effect = FileNotFoundError(str(creds_path))

        with pytest.raises(SignInRequiredError):
            auth_from_file(token_path, creds_path)

    def test_GIVEN_refresh_fails_and_no_credentials_file_THEN_sign_in_required(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        write_creds_to_file(_creds(expired=True), token_path)
        flow_class.from_client_secrets_file.side_effect = FileNotFoundError(str(creds_path))

        with (
            patch.object(Credentials, "refresh", side_effect=RefreshError("invalid_grant")),
            pytest.raises(SignInRequiredError),
        ):
            auth_from_file(token_path, creds_path)

    def test_GIVEN_no_token_and_sign_in_not_allowed_THEN_no_flow(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        with pytest.raises(SignInRequiredError):
            auth_from_file(token_path, creds_path, allow_sign_in=False)

        flow_class.from_client_secrets_file.assert_not_called()

    def test_GIVEN_refresh_fails_and_sign_in_not_allowed_THEN_no_flow(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        write_creds_to_file(_creds(expired=True), token_path)

        with (
            patch.object(Credentials, "refresh", side_effect=RefreshError("invalid_grant")),
            pytest.raises(SignInRequiredError),
        ):
            auth_from_file(token_path, creds_path, allow_sign_in=False)

        flow_class.from_client_secrets_file.assert_not_called()

    def test_GIVEN_corrupt_token_and_sign_in_not_allowed_THEN_sign_in_required(
        self, token_path: Path, creds_path: Path, flow_class: MagicMock
    ) -> None:
        token_path.write_text("{ not json")

        with pytest.raises(SignInRequiredError):
            auth_from_file(token_path, creds_path, allow_sign_in=False)

        flow_class.from_client_secrets_file.assert_not_called()


class TestBuildClient:
    @pytest.fixture
    def creds(self) -> MagicMock:
        return MagicMock(client_id="client", refresh_token="token")

    @pytest.fixture(autouse=True)
    def patched(self, creds: MagicMock):
        self.creds = creds
        with (
            patch("gtasks.client.client_factory.auth_from_file", return_value=creds),
            patch("gtasks.client.client_factory.build_tasks_resource") as build_resource,
        ):
            self.build_resource = build_resource
            yield

    def test_build_client_GIVEN_no_cache_dir_THEN_plain_api_client(self) -> None:
        assert isinstance(build_client(), ApiClient)

    def test_build_client_GIVEN_cache_dir_THEN_caching_client_for_this_account(
        self, tmp_path: Path, creds: MagicMock
    ) -> None:
        client = build_client(cache_dir=tmp_path)

        assert isinstance(client, CachingClient)
        client._store.write_tasklists([])  # where it writes identifies the account
        assert (tmp_path / account_key("client", "token")).is_dir()

    def test_build_client_THEN_refetch_client_has_own_connection_with_timeout(
        self, tmp_path: Path, creds: MagicMock
    ) -> None:
        client = build_client(cache_dir=tmp_path)
        assert isinstance(client, CachingClient)

        assert client._make_refresher is not None
        refresher = client._make_refresher()  # what a concurrent refetch would use

        assert isinstance(refresher, ApiClient)
        self.build_resource.assert_called_once()
        assert self.build_resource.call_args.args == (creds,)
        assert self.build_resource.call_args.kwargs["timeout"] > 0

    def test_build_client_GIVEN_cache_dir_THEN_api_client_built_only_when_needed(
        self, tmp_path: Path
    ) -> None:
        """A command served from the cache never builds (or imports) the Google client."""
        client = build_client(cache_dir=tmp_path)
        self.build_resource.assert_not_called()

        assert isinstance(client, CachingClient)
        assert isinstance(client._inner(), ApiClient)
        self.build_resource.assert_called_once_with(self.creds)

    def test_build_client_GIVEN_fresh_THEN_passed_to_caching_client(
        self, tmp_path: Path
    ) -> None:
        client = build_client(fresh=True, cache_dir=tmp_path)

        assert isinstance(client, CachingClient)
        assert client._fresh is True


class TestBuildTasksResource:
    @patch("googleapiclient.discovery.build")
    def test_GIVEN_no_timeout_THEN_default_connection(self, mock_build: MagicMock) -> None:
        creds = MagicMock()

        build_tasks_resource(creds)

        mock_build.assert_called_once_with(
            "tasks", "v1", credentials=creds, cache_discovery=False
        )

    @patch("googleapiclient.discovery.build")
    @patch("httplib2.Http")
    @patch("google_auth_httplib2.AuthorizedHttp")
    def test_GIVEN_timeout_THEN_new_connection_with_that_timeout(
        self, mock_authed: MagicMock, mock_http: MagicMock, mock_build: MagicMock
    ) -> None:
        creds = MagicMock()

        build_tasks_resource(creds, timeout=10)

        mock_http.assert_called_once_with(timeout=10)
        mock_authed.assert_called_once_with(creds, http=mock_http.return_value)
        mock_build.assert_called_once_with(
            "tasks", "v1", http=mock_authed.return_value, cache_discovery=False
        )
