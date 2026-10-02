"""Factory functions for building API clients and services."""

import pickle
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gtasks.client.api_client import ApiClient
from gtasks.client.protocol import TasksClient
from gtasks.defaults import APP_CFG_PATH

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


def build_client() -> TasksClient:
    return ApiClient(build_tasks_resource())


def _load_or_refresh_creds(
    token_path: Path, build_flow: Callable[[], InstalledAppFlow]
) -> Credentials:
    """Load cached credentials, refreshing or running the OAuth flow as needed.

    `build_flow` is only called when there's no valid cached token, since
    constructing a flow may require client secrets the caller would rather
    not gather (e.g. prompting the user) unless they're actually needed.
    """
    creds: Credentials | None = None

    if token_path.exists():
        with token_path.open("rb") as token_file:
            creds = pickle.load(token_file)

    if creds and creds.valid:
        return creds
    elif creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = build_flow()
        # Perform auth via local web server and browser-based consent screen.
        creds = flow.run_local_server()

    write_creds_to_file(creds, token_path)
    return creds


def auth(token_path: Path, client_id: str, client_secret: str) -> Credentials:
    """Authenticate using an inline client ID/secret (used by `gtasks auth`)."""
    return _load_or_refresh_creds(
        token_path,
        lambda: InstalledAppFlow.from_client_config(
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
        ),
    )


def auth_from_file(token_path: Path, creds_path: Path) -> Credentials:
    """Authenticate using a `credentials.json` file (used by `build_tasks_resource`)."""
    return _load_or_refresh_creds(
        token_path,
        lambda: InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES),
    )


def write_creds_to_file(creds: Credentials, token_path: Path) -> None:
    # Ensure parent directory exists (e.g. ~/.config/gtasks-cli)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    with token_path.open("wb") as token_file:
        pickle.dump(creds, token_file)
