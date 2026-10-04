"""Factory functions for building API clients and services."""

import pickle
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

import httplib2
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gtasks.client.api_client import ApiClient
from gtasks.client.cache_store import CacheStore, account_key
from gtasks.client.caching_client import CachingClient
from gtasks.client.protocol import TasksClient
from gtasks.defaults import APP_CFG_PATH

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource


SCOPES: list[str] = ["https://www.googleapis.com/auth/tasks"]


class SignInRequiredError(Exception):
    """No usable saved sign-in, and no client secrets on disk to start a new one.

    Raised instead of the underlying FileNotFoundError so callers can tell the user how
    to sign in (e.g. `gtasks auth`, which supplies the secrets inline) rather than
    reporting a missing file.
    """


# A concurrent cache refetch gets its own connection with a timeout, so it can never hang
# the command it runs alongside.
_REFETCH_TIMEOUT_SECONDS = 10


def build_tasks_resource(creds: Credentials, timeout: float | None = None) -> "TasksResource":
    """Build a Google Tasks API resource with its own HTTP connection.

    Each resource owns a separate httplib2 connection, which isn't thread-safe: code running
    on another thread must build its own resource rather than share one.
    """
    if timeout is None:
        return build("tasks", "v1", credentials=creds)
    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=timeout))
    # AuthorizedHttp is the documented way to pass credentials with a custom Http, but the
    # stubs only accept a plain httplib2.Http here.
    return build("tasks", "v1", http=cast(httplib2.Http, http))


def build_client(
    *,
    fresh: bool = False,
    cache_dir: Path | None = None,
    token_path: Path = APP_CFG_PATH / "token.pickle",
    creds_path: Path = APP_CFG_PATH / "credentials.json",
) -> TasksClient:
    """Sign in and build the client: cached under `cache_dir` if given, else plain.

    Credentials are loaded (and refreshed if expired) once, before any client is built, so
    the main client and a concurrent refetch never race to refresh the same token.
    """
    creds: Credentials = auth_from_file(token_path, creds_path)
    api = ApiClient(build_tasks_resource(creds))
    if cache_dir is None:
        return api

    store = CacheStore(cache_dir, account_key(creds.client_id, creds.refresh_token))
    return CachingClient(
        api,
        store,
        fresh=fresh,
        make_refresher=lambda: ApiClient(
            build_tasks_resource(creds, timeout=_REFETCH_TIMEOUT_SECONDS)
        ),
    )


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

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            # Revoked or long-expired refresh token: fall through and sign in again.
            # Without this, `gtasks auth` could never replace a dead token.
            pass
        else:
            write_creds_to_file(creds, token_path)
            return creds

    flow = build_flow()
    # Perform auth via local web server and browser-based consent screen.
    new_creds: Credentials = flow.run_local_server()
    write_creds_to_file(new_creds, token_path)
    return new_creds


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
    """Authenticate using a `credentials.json` file (used by `build_client`)."""

    def build_flow() -> InstalledAppFlow:
        try:
            return InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        except FileNotFoundError as e:
            raise SignInRequiredError(f"No saved sign-in and no {creds_path}") from e

    return _load_or_refresh_creds(token_path, build_flow)


def write_creds_to_file(creds: Credentials, token_path: Path) -> None:
    # Ensure parent directory exists (e.g. ~/.config/gtasks-cli)
    token_path.parent.mkdir(parents=True, exist_ok=True)

    with token_path.open("wb") as token_file:
        pickle.dump(creds, token_file)
