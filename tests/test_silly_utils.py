import pickle
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

from gtasks.utils import load_credentials


class TestLoadCredentials:
    @pytest.fixture
    def token_path(self, tmp_path: Path) -> Path:
        return tmp_path / "token.pickle"

    @pytest.fixture
    def creds_path(self, tmp_path: Path) -> Path:
        return tmp_path / "credentials.json"

    @pytest.fixture
    def valid_creds(self) -> MagicMock:
        creds = MagicMock(spec=Credentials)
        creds.valid = True
        creds.expired = False
        creds.refresh_token = None
        return creds

    @pytest.fixture
    def expired_creds_with_refresh_token(self) -> MagicMock:
        creds = MagicMock(spec=Credentials)
        creds.valid = False
        creds.expired = True
        creds.refresh_token = "refresh_token_value"
        return creds

    def test_load_credentials_GIVEN_valid_cached_token_THEN_returns_cached_creds(
        self, token_path: Path, creds_path: Path, valid_creds: MagicMock
    ) -> None:
        token_path.write_bytes(pickle.dumps(valid_creds))

        result = load_credentials(token_path, creds_path)

        assert result == valid_creds

    def test_load_credentials_GIVEN_expired_creds_with_refresh_token_THEN_refreshes_and_saves(
        self,
        token_path: Path,
        creds_path: Path,
        expired_creds_with_refresh_token: MagicMock,
    ) -> None:
        token_path.write_bytes(pickle.dumps(expired_creds_with_refresh_token))

        result = load_credentials(token_path, creds_path)

        expired_creds_with_refresh_token.refresh.assert_called_once()
        assert result == expired_creds_with_refresh_token
        assert token_path.exists()

    @patch("gtasks.utils.InstalledAppFlow")
    def test_load_credentials_GIVEN_no_cached_token_THEN_runs_oauth_flow(
        self,
        mock_flow_class: MagicMock,
        token_path: Path,
        creds_path: Path,
    ) -> None:
        new_creds = MagicMock(spec=Credentials)
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        result = load_credentials(token_path, creds_path)

        mock_flow_class.from_client_secrets_file.assert_called_once_with(
            str(creds_path),
            ["https://www.googleapis.com/auth/tasks"],
        )
        mock_flow.run_local_server.assert_called_once()
        assert result == new_creds
        assert token_path.exists()

    @patch("gtasks.utils.InstalledAppFlow")
    def test_load_credentials_GIVEN_invalid_cached_creds_THEN_runs_oauth_flow(
        self,
        mock_flow_class: MagicMock,
        token_path: Path,
        creds_path: Path,
    ) -> None:
        invalid_creds = MagicMock(spec=Credentials)
        invalid_creds.valid = False
        invalid_creds.expired = False
        invalid_creds.refresh_token = None
        token_path.write_bytes(pickle.dumps(invalid_creds))

        new_creds = MagicMock(spec=Credentials)
        mock_flow = MagicMock()
        mock_flow.run_local_server.return_value = new_creds
        mock_flow_class.from_client_secrets_file.return_value = mock_flow

        result = load_credentials(token_path, creds_path)

        mock_flow.run_local_server.assert_called_once()
        assert result == new_creds

    def test_load_credentials_GIVEN_nested_token_path_THEN_creates_parent_dirs(
        self, tmp_path: Path, creds_path: Path
    ) -> None:
        nested_token_path = tmp_path / "nested" / "dir" / "token.pickle"
        valid_creds = MagicMock(spec=Credentials)
        valid_creds.valid = False
        valid_creds.expired = True
        valid_creds.refresh_token = "refresh_token"

        with (
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "open", create=True) as mock_open,
        ):
            mock_open.return_value.__enter__.return_value.read = lambda: pickle.dumps(
                valid_creds
            )

        # Use expired creds to trigger save path
        nested_token_path.parent.mkdir(parents=True, exist_ok=True)
        nested_token_path.write_bytes(pickle.dumps(valid_creds))

        load_credentials(nested_token_path, creds_path)

        assert nested_token_path.parent.exists()

    def test_load_credentials_GIVEN_refreshed_creds_THEN_persists_to_file(
        self,
        token_path: Path,
        creds_path: Path,
        expired_creds_with_refresh_token: MagicMock,
    ) -> None:
        token_path.write_bytes(pickle.dumps(expired_creds_with_refresh_token))

        load_credentials(token_path, creds_path)

        # Verify the token was saved by reading it back
        with token_path.open("rb") as f:
            saved_creds = pickle.load(f)
        assert saved_creds == expired_creds_with_refresh_token
