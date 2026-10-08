"""Factory functions for building API clients and services.

The Google libraries are imported inside the functions that use them, never at module level:
together they take ~0.4 s to import, and a command served from the cache never needs them.
"""

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, cast

from gtasks import defaults
from gtasks.client.api_client import ApiClient
from gtasks.client.cache_store import CacheStore, account_key
from gtasks.client.caching_client import CachingClient
from gtasks.client.protocol import TasksClient

if TYPE_CHECKING:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
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
    from googleapiclient.discovery import build

    if timeout is None:
        return build("tasks", "v1", credentials=creds)

    import httplib2
    from google_auth_httplib2 import AuthorizedHttp

    http = AuthorizedHttp(creds, http=httplib2.Http(timeout=timeout))
    # AuthorizedHttp is the documented way to pass credentials with a custom Http, but the
    # stubs only accept a plain httplib2.Http here.
    return build("tasks", "v1", http=cast(httplib2.Http, http))


def build_client(
    *,
    fresh: bool = False,
    cache_dir: Path | None = None,
    token_path: Path | None = None,
    creds_path: Path | None = None,
    allow_sign_in: bool = True,
) -> TasksClient:
    """Sign in and build the client: cached under `cache_dir` if given, else plain.

    Credentials are loaded (and refreshed if expired) once, before any client is built, so
    the main client and a concurrent refetch never race to refresh the same token.
    `allow_sign_in=False` never starts the browser flow (see `auth_from_file`).
    """
    creds: Credentials = auth_from_file(
        token_path or defaults.token_file(),
        creds_path or defaults.credentials_file(),
        allow_sign_in=allow_sign_in,
    )
    if cache_dir is None:
        return ApiClient(build_tasks_resource(creds))

    store = CacheStore(cache_dir, account_key(creds.client_id, creds.refresh_token))
    return CachingClient(
        store,
        make_inner=lambda: ApiClient(build_tasks_resource(creds)),
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
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request

    creds = read_creds_from_file(token_path)

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
    from google_auth_oauthlib.flow import InstalledAppFlow

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


def auth_from_file(
    token_path: Path, creds_path: Path, *, allow_sign_in: bool = True
) -> Credentials:
    """Authenticate using a `credentials.json` file (used by `build_client`).

    With `allow_sign_in=False`, a missing or dead token raises `SignInRequiredError` instead
    of running the browser flow, for callers with no user at a terminal (the MCP server,
    whose stdout the flow's prompts would corrupt).
    """

    def build_flow() -> InstalledAppFlow:
        from google_auth_oauthlib.flow import InstalledAppFlow

        if not allow_sign_in:
            raise SignInRequiredError("No usable saved sign-in")
        try:
            return InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
        except FileNotFoundError as e:
            raise SignInRequiredError(f"No saved sign-in and no {creds_path}") from e

    return _load_or_refresh_creds(token_path, build_flow)


def read_creds_from_file(token_path: Path) -> Credentials | None:
    """The saved sign-in, or None if there's none or it can't be read (so: sign in again).

    JSON rather than a pickle: a pickle names google-auth's internal modules, so a token saved
    by one google-auth version may not load in another (an installed gtasks and a checkout).
    A token from before the switch is migrated the first time it's read.
    """
    from google.oauth2.credentials import Credentials

    if not token_path.exists():
        return _migrate_legacy_token(token_path)
    try:
        info = json.loads(token_path.read_text())
        return Credentials.from_authorized_user_info(info, SCOPES)
    except (OSError, ValueError, TypeError, AttributeError):
        return None  # unreadable, corrupt, or missing required fields


def _migrate_legacy_token(token_path: Path) -> Credentials | None:
    """Convert a `token.pickle` saved next to `token_path` by an earlier gtasks to JSON.

    One that won't load (e.g. pickled by another google-auth version) is left in place for
    whichever install wrote it; this one then signs in afresh.
    """
    import pickle

    legacy_path = token_path.with_suffix(".pickle")
    try:
        with legacy_path.open("rb") as legacy_file:
            creds = pickle.load(legacy_file)
        # Same account (client ID and refresh token), so the cache carries over too.
        write_creds_to_file(creds, token_path)
    except Exception:
        return None
    legacy_path.unlink(missing_ok=True)
    return creds


def write_creds_to_file(creds: Credentials, token_path: Path) -> None:
    """Save the sign-in atomically and owner-only (0600): it grants access to the account."""
    token_path.parent.mkdir(parents=True, exist_ok=True)
    # mkstemp creates the file 0600; the rename means no reader ever sees half a token.
    fd, tmp = tempfile.mkstemp(dir=token_path.parent, prefix=".tmp-token-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(creds.to_json())
        os.replace(tmp, token_path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
