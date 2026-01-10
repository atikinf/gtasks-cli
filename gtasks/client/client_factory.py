"""Factory functions for building API clients and services."""

import pickle
from pathlib import Path
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gtasks.client.cached_api_client import CachedApiClient
from gtasks.defaults import APP_CFG_PATH, CACHE_FILE_PATH
from gtasks.utils.bidict_cache import BidictCache

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource


SCOPES: list[str] = ["https://www.googleapis.com/auth/tasks"]


def build_tasks_resource(
    token_path: Path = APP_CFG_PATH / "token.pickle",
    creds_path: Path = APP_CFG_PATH / "credentials.json",
) -> "TasksResource":
    """Build and return a Google Tasks API resource."""
    creds: Credentials = _load_credentials(token_path, creds_path)
    return build("tasks", "v1", credentials=creds)


def build_cached_client() -> CachedApiClient:
    """Build and return a CachedApiClient instance with cache."""
    cache: BidictCache[str, str] = BidictCache(CACHE_FILE_PATH)
    return CachedApiClient(build_tasks_resource(), cache)


def _load_credentials(
    token_path: Path,
    creds_path: Path,
) -> Credentials:
    """Load existing credentials or perform an OAuth2 login flow."""
    creds: Credentials | None = None

    if token_path.exists():
        with token_path.open("rb") as token_file:
            creds = pickle.load(token_file)

    if creds and creds.valid:
        return creds
    elif creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(creds_path),
            SCOPES,
        )
        # Uses a local web server and browser-based consent screen.
        creds = flow.run_local_server()

    # Ensure parent directory exists (e.g. ~/.config/gtasks-cli)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    with token_path.open("wb") as token_file:
        pickle.dump(creds, token_file)

    return creds
