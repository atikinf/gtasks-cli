from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from gtasks.client.client_factory import load_credentials


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
            result = load_credentials(token_path, creds_path)

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
            result = load_credentials(token_path, creds_path)

        expired_creds_with_refresh_token.refresh.assert_called_once()
        mock_pickle.dump.assert_called_once()
        assert result == expired_creds_with_refresh_token

    @patch("gtasks.client.client_factory.InstalledAppFlow")
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
            result = load_credentials(token_path, creds_path)

        mock_flow_class.from_client_secrets_file.assert_called_once_with(
            str(creds_path),
            ["https://www.googleapis.com/auth/tasks"],
        )
        mock_flow.run_local_server.assert_called_once()
        mock_pickle.dump.assert_called_once()
        assert result == new_creds

    @patch("gtasks.client.client_factory.InstalledAppFlow")
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
            result = load_credentials(token_path, creds_path)

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
            load_credentials(nested_token_path, creds_path)

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
            patch.object(Path, "open", mock_open()) as m_open,
            patch.object(Path, "mkdir"),
        ):
            load_credentials(token_path, creds_path)

        # Verify pickle.dump was called with the creds and the file handle
        mock_pickle.dump.assert_called_once()
        assert mock_pickle.dump.call_args[0][0] == expired_creds_with_refresh_token
