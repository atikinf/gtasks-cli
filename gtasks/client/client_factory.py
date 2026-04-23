"""Factory functions for building API clients and services."""

import pickle
from pathlib import Path
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gtasks.client.api_client import ApiClient
from gtasks.client.cached_api_client import CachedApiClient
from gtasks.defaults import APP_CFG_PATH, CACHE_FILE_PATH, TASKS_CACHE_DIR_PATH
from gtasks.utils.bidict_cache import BidictCache

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource


SCOPES: list[str] = ["https://www.googleapis.com/auth/tasks"]


def build_tasks_resource(
    token_path: Path = APP_CFG_PATH / "token.pickle",
    creds_path: Path = APP_CFG_PATH / "credentials.json",
) -> "TasksResource":
    """Build and return a Google Tasks API resource."""
    creds: Credentials = auth_from_file(token_path, creds_path)
    return build("tasks", "v1", credentials=creds)


def build_cached_client() -> CachedApiClient:
    tasklists_cache: BidictCache[str, str] = BidictCache(CACHE_FILE_PATH)
    tasks_cache: dict[str, BidictCache[str, str]] = {}
    return CachedApiClient(
        build_tasks_resource(), tasklists_cache, TASKS_CACHE_DIR_PATH, tasks_cache
    )


def build_client() -> ApiClient:
    return ApiClient(build_tasks_resource())


def auth(token_path: Path, client_id: str, client_secret: str) -> Credentials:
    creds: Credentials | None = None

    if token_path.exists():
        with token_path.open("rb") as token_file:
            creds = pickle.load(token_file)

    if creds and creds.valid:
        return creds
    elif creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_config(
            client_config={
                "installed": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["http://localhost"],
                }
            },
            scopes=SCOPES,
        )
        # Perform auth via local web server and browser-based consent screen.
        creds = flow.run_local_server()

    write_creds_to_file(creds, token_path)
    return creds

def auth_from_file(
    token_path: Path,
    creds_path: Path,
) -> Credentials:
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
        # Perform auth via local web server and browser-based consent screen.
        creds = flow.run_local_server()

    write_creds_to_file(creds, token_path)
    return creds


def write_creds_to_file(creds: Credentials, token_path: Path) -> None:
    # Ensure parent directory exists (e.g. ~/.config/gtasks-cli)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    with token_path.open("wb") as token_file:
        pickle.dump(creds, token_file)
