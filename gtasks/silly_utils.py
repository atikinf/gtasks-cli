import pickle
from pathlib import Path
from typing import TYPE_CHECKING

from google.auth.transport import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from gtasks.utils.defaults import CONFIG_PATH

if TYPE_CHECKING:
    from googleapiclient._apis.tasks.v1.resources import TasksResource
    from googleapiclient._apis.tasks.v1.schemas import TaskList


SCOPES: list[str] = ["https://www.googleapis.com/auth/tasks"]


def tasklist_list_to_title_id_map(tasklists: list[TaskList]):
    title_id_map: dict[str, str] = {}
    for tasklist in tasklists:
        title: str | None = tasklist.get("title")
        id_: str | None = tasklist.get("id")
        if title is not None and id_ is not None:
            title_id_map[title] = id_
        else:
            raise ValueError("Cannot parse tasklist with empty id and title.")
    return title_id_map


def build_tasks_service(
    token_path: Path = CONFIG_PATH / "token.pickle",
    creds_path: Path = CONFIG_PATH / "credentials.json",
) -> TasksResource:
    creds: Credentials = _load_credentials(token_path, creds_path)

    return build("tasks", "v1", credentials=creds)


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
