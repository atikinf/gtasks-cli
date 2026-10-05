from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest
from google.auth.exceptions import RefreshError

from gtasks.client.api_client import ApiClient
from gtasks.client.cache_store import account_key
from gtasks.client.caching_client import CachingClient
from gtasks.client.client_factory import (
    SignInRequiredError,
    auth_from_file,
    build_client,
    build_tasks_resource,
)


class TestLoadCredentials:
    @pytest.fixture
    def token_path(self) -> Path:
        return Path("/fake/token.pickle")

    @pytest.fixture
    def creds_path(self) -> Path:
        return Path("/fake/credentials.json")

    @pytest.fixture
    def valid_creds(self) -> MagicMock:
        creds = MagicMock()
        creds.valid = True
        creds.expired = False
        creds.refresh_token = None
        return creds

    @pytest.fixture
    def expired_creds_with_refresh_token(self) -> MagicMock:
        creds = MagicMock()
        creds.valid = False
        creds.expired = True
        creds.refresh_token = "refresh_token_value"
        return creds

    @patch("gtasks.client.client_factory.pickle")
    def test_load_credentials_GIVEN_valid_cached_token_THEN_returns_cached_creds(
        self,
        mock_pickle: MagicMock,
        token_path: Path,
        creds_path: Path,
        valid_creds: MagicMock,
    ) -> None:
        mock_pickle.load.return_value = valid_creds

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
        ):
            result = auth_from_file(token_path, creds_path)

        assert result == valid_creds
        mock_pickle.dump.assert_not_called()  # Valid creds don't need re-saving

    @patch("gtasks.client.client_factory.pickle")
    def test_load_credentials_GIVEN_expired_creds_with_refresh_token_THEN_refreshes_and_saves(
        self,
        mock_pickle: MagicMock,
        token_path: Path,
        creds_path: Path,
        expired_creds_with_refresh_token: MagicMock,
    ) -> None:
        mock_pickle.load.return_value = expired_creds_with_refresh_token

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
            patch.object(Path, "mkdir"),
        ):
            result = auth_from_file(token_path, creds_path)

        expired_creds_with_refresh_token.refresh.assert_called_once()
        mock_pickle.dump.assert_called_once()
        assert result == expired_creds_with_refresh_token

    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    @patch("gtasks.client.client_factory.pickle")
    def test_load_credentials_GIVEN_no_cached_token_THEN_runs_oauth_flow(
        self,
        mock_pickle: MagicMock,
        mock_flow_class: MagicMock,
        token_path: Path,
        creds_path: Path,
    ) -> None:
        new_creds = MagicMock()
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        with (
            patch.object(Path, "exists", return_value=False),
            patch.object(Path, "open", mock_open()),
            patch.object(Path, "mkdir"),
        ):
            result = auth_from_file(token_path, creds_path)

        mock_flow_class.from_client_secrets_file.assert_called_once_with(
            str(creds_path),
            ["https://www.googleapis.com/auth/tasks"],
        )
        mock_flow.run_local_server.assert_called_once()
        mock_pickle.dump.assert_called_once()
        assert result == new_creds

    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    @patch("gtasks.client.client_factory.pickle")
    def test_load_credentials_GIVEN_invalid_cached_creds_THEN_runs_oauth_flow(
        self,
        mock_pickle: MagicMock,
        mock_flow_class: MagicMock,
        token_path: Path,
        creds_path: Path,
    ) -> None:
        invalid_creds = MagicMock()
        invalid_creds.valid = False
        invalid_creds.expired = False
        invalid_creds.refresh_token = None
        mock_pickle.load.return_value = invalid_creds

        new_creds = MagicMock()
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
            patch.object(Path, "mkdir"),
        ):
            result = auth_from_file(token_path, creds_path)

        mock_flow.run_local_server.assert_called_once()
        assert result == new_creds

    @patch("gtasks.client.client_factory.pickle")
    def test_load_credentials_GIVEN_nested_token_path_THEN_creates_parent_dirs(
        self, mock_pickle: MagicMock, creds_path: Path
    ) -> None:
        nested_token_path = Path("/nested/dir/token.pickle")
        expired_creds = MagicMock()
        expired_creds.valid = False
        expired_creds.expired = True
        expired_creds.refresh_token = "refresh_token"
        mock_pickle.load.return_value = expired_creds

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
            patch.object(Path, "mkdir") as mock_mkdir,
        ):
            auth_from_file(nested_token_path, creds_path)

        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("gtasks.client.client_factory.pickle")
    def test_load_credentials_GIVEN_refreshed_creds_THEN_persists_to_file(
        self,
        mock_pickle: MagicMock,
        token_path: Path,
        creds_path: Path,
        expired_creds_with_refresh_token: MagicMock,
    ) -> None:
        mock_pickle.load.return_value = expired_creds_with_refresh_token

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
            patch.object(Path, "mkdir"),
        ):
            auth_from_file(token_path, creds_path)

        # Verify pickle.dump was called with the creds and the file handle
        mock_pickle.dump.assert_called_once()
        assert mock_pickle.dump.call_args[0][0] == expired_creds_with_refresh_token


class TestSignInRequired:
    @pytest.fixture
    def token_path(self) -> Path:
        return Path("/fake/token.pickle")

    @pytest.fixture
    def creds_path(self) -> Path:
        return Path("/fake/credentials.json")

    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    def test_auth_from_file_GIVEN_no_token_and_no_credentials_file_THEN_raises_sign_in_required(
        self, mock_flow_class: MagicMock, token_path: Path, creds_path: Path
    ) -> None:
        mock_flow_class.from_client_secrets_file.side_effect = FileNotFoundError(str(creds_path))

        with (
            patch.object(Path, "exists", return_value=False),
            pytest.raises(SignInRequiredError),
        ):
            auth_from_file(token_path, creds_path)

    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    @patch("gtasks.client.client_factory.pickle")
    def test_auth_from_file_GIVEN_refresh_fails_THEN_signs_in_again(
        self,
        mock_pickle: MagicMock,
        mock_flow_class: MagicMock,
        token_path: Path,
        creds_path: Path,
    ) -> None:
        dead_creds = MagicMock(valid=False, expired=True, refresh_token="revoked")
        dead_creds.refresh.side_effect = RefreshError("invalid_grant")
        mock_pickle.load.return_value = dead_creds
        new_creds = MagicMock()
        mock_flow_class.from_client_secrets_file.return_value.run_local_server.return_value = (
            new_creds
        )

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
            patch.object(Path, "mkdir"),
        ):
            result = auth_from_file(token_path, creds_path)

        assert result == new_creds
        assert mock_pickle.dump.call_args.args[0] is new_creds  # the new sign-in is saved

    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    @patch("gtasks.client.client_factory.pickle")
    def test_auth_from_file_GIVEN_refresh_fails_and_no_credentials_file_THEN_sign_in_required(
        self,
        mock_pickle: MagicMock,
        mock_flow_class: MagicMock,
        token_path: Path,
        creds_path: Path,
    ) -> None:
        dead_creds = MagicMock(valid=False, expired=True, refresh_token="revoked")
        dead_creds.refresh.side_effect = RefreshError("invalid_grant")
        mock_pickle.load.return_value = dead_creds
        mock_flow_class.from_client_secrets_file.side_effect = FileNotFoundError(str(creds_path))

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
            pytest.raises(SignInRequiredError),
        ):
            auth_from_file(token_path, creds_path)

    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    def test_auth_from_file_GIVEN_no_token_and_sign_in_not_allowed_THEN_no_flow(
        self, mock_flow_class: MagicMock, token_path: Path, creds_path: Path
    ) -> None:
        with (
            patch.object(Path, "exists", return_value=False),
            pytest.raises(SignInRequiredError),
        ):
            auth_from_file(token_path, creds_path, allow_sign_in=False)

        mock_flow_class.from_client_secrets_file.assert_not_called()

    @patch("google_auth_oauthlib.flow.InstalledAppFlow")
    @patch("gtasks.client.client_factory.pickle")
    def test_auth_from_file_GIVEN_refresh_fails_and_sign_in_not_allowed_THEN_no_flow(
        self,
        mock_pickle: MagicMock,
        mock_flow_class: MagicMock,
        token_path: Path,
        creds_path: Path,
    ) -> None:
        dead_creds = MagicMock(valid=False, expired=True, refresh_token="revoked")
        dead_creds.refresh.side_effect = RefreshError("invalid_grant")
        mock_pickle.load.return_value = dead_creds

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", mock_open()),
            pytest.raises(SignInRequiredError),
        ):
            auth_from_file(token_path, creds_path, allow_sign_in=False)

        mock_flow_class.from_client_secrets_file.assert_not_called()


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

        mock_build.assert_called_once_with("tasks", "v1", credentials=creds)

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
        mock_build.assert_called_once_with("tasks", "v1", http=mock_authed.return_value)
