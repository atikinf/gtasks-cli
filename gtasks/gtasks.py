from __future__ import annotations

from pathlib import Path
from typing import Optional

import configparser
import pickle

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build


SCOPES: list[str] = ["https://www.googleapis.com/auth/tasks"]

class TasksHelper:
    """Helper for authenticating with Google Tasks and exposing a Tasks API client.
    Attributes:
        _credentials_path: Path
        _token_path: Path
        _config_path: Path
        _default_list_id: Optional[str]
        _scopes: list[str]
        _service: Resource - Google Tasks API client
    """

    def __init__(
        self,
        credentials_path: str | Path = "credentials.json",
        token_path: str | Path = "token.pickle",
        config_path: str | Path = Path("~/.config/gtasks-cli/config.conf").expanduser(),
        scopes: Optional[list[str]] = None,
    ) -> None:
        """Initialize the helper and create a Google Tasks API client.

        Args:
            credentials_path: Path to the OAuth client credentials JSON file.
            token_path: Path where the user token will be cached.
            config_path: Path to the configuration file used for defaults.
            scopes: Optional list of OAuth scopes to request. Defaults to
                the Tasks scope if not provided.
        """
        self._credentials_path: Path = Path(credentials_path)
        self._token_path: Path = Path(token_path)
        self._config_path: Path = Path(config_path)
        # TODO: Read the config file to get the default task list id on initialization
        self._default_list_id: Optional[str] = None 
        self._scopes: list[str] = scopes if scopes is not None else SCOPES

        creds: Credentials = self._load_credentials()
        self._service: Resource = build("tasks", "v1", credentials=creds)

    def set_default_tasklist(self) -> None:
        """Interactively set a default task list and persist it to config.
        """
        tasklists_resource = self._service.tasklists()
        response = tasklists_resource.list().execute()
        items = response.get("items", [])

        if not items:
            print("No task lists found for this account.")
            return

        # TODO: Factor out the config file + other helpers to a separate class 
        config = configparser.ConfigParser()
        current_default_title: Optional[str] = None

        if self._config_path.exists():
            config.read(self._config_path)
            if config.has_option("defaults", "default_tasklist_title"):
                current_default_title = config.get(
                    "defaults",
                    "default_tasklist_title",
                )
            if config.has_option("defaults", "default_tasklist_id"):
                self._default_list_id = config.get(
                    "defaults",
                    "default_tasklist_id",
                )

        print("Available task lists:")
        for idx, tlist in enumerate(items, start=1):
            title = tlist.get("title", "<untitled>")
            print(f"{idx}. {title}")

        choice_idx = self._prompt_index_choice(
            items,
            "Select a default task list",
            current_default_title,
        )

        if choice_idx is None:
            print("Aborted setting default task list.")
            return

        selected = items[choice_idx]
        selected_id: str = selected["id"]
        selected_title: str = selected.get("title", "")

        if "defaults" not in config:
            config["defaults"] = {}

        config["defaults"]["default_tasklist_id"] = selected_id
        config["defaults"]["default_tasklist_title"] = selected_title
        self._default_list_id = selected_id

        # Ensure parent directory exists (e.g. ~/.config/gtasks-cli)
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        with self._config_path.open("w") as cfg_file:
            config.write(cfg_file)

        print(
            f"Default task list set to '{selected_title}' "
            f"(id: {selected_id}) and written to {self._config_path}"
        )

    def list_tasklists(self, n: Optional[int] = None) -> None:
        """Print first ``n`` task lists (all if ``n`` is not given).
        """
        tasklists_resource = self._service.tasklists()
        response = tasklists_resource.list().execute()
        items = response.get("items", [])

        if not items:
            print("No task lists found for this account.")
            return

        limit = n if n is not None else len(items)
        print(f"Showing first {limit} task lists:")

        for idx, tlist in enumerate(items[:limit], start=1):
            title = tlist.get("title", "<untitled>")
            list_id = tlist.get("id", "")
            default_suffix = " [DEFAULT]" if list_id == self._default_list_id else ""
            print(f"{idx}. {title}{default_suffix} (id: {list_id})")

    def list_tasks(
        self,
        tasklist_id: Optional[str] = None,
        n: Optional[int] = None,
    ) -> None:
        """Print first ``n`` tasks from the given task list (all if ``n`` is not given).
        """
        effective_tasklist_id: Optional[str] = tasklist_id or self._default_list_id

        if effective_tasklist_id is None:
            print(
                # TODO: Replace with the CLI command when implemented.
                "No task list id provided and no default task list is configured. "
                "Use `set_default_tasklist` or pass a tasklist_id."
            )
            return

        tasks_resource = self._service.tasks()
        response = tasks_resource.list(tasklist=effective_tasklist_id).execute()
        items = response.get("items", [])

        if not items:
            print(f"No tasks found for task list id '{effective_tasklist_id}'.")
            return

        limit = n if n is not None else len(items)
        print(f"Showing first {limit} tasks from task list '{effective_tasklist_id}':")

        for idx, task in enumerate(items[:limit], start=1):
            title = task.get("title", "<untitled>")
            status = task.get("status", "unknown")
            print(f"{idx}. {title} [status: {status}]")

    def _load_credentials(self) -> Credentials:
        """Load existing credentials or perform an OAuth2 login flow."""
        creds: Optional[Credentials] = None

        if self._token_path.exists():
            with self._token_path.open("rb") as token_file:
                creds = pickle.load(token_file)

        if creds and creds.valid:
            return creds
        elif creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self._credentials_path),
                self._scopes,
            )
            # Uses a local web server and browser-based consent screen.
            creds = flow.run_local_server()

        with self._token_path.open("wb") as token_file:
            pickle.dump(creds, token_file)

        return creds

    def _prompt_index_choice(
        self,
        items: list,
        prompt_prefix: str,
        current_hint: Optional[str] = None,
    ) -> Optional[int]:
        """Prompt user to select an item from a numbered list.

        Args:
            items: List of items to choose from.
            prompt_prefix: e.g., "Select a default task list".
            current_hint: Optional hint to display about the current selection.

        Returns:
            0-based index of the selected item, or None if the user cancelled.
        """
        while True:
            hint_suffix = f" (current: {current_hint})" if current_hint else ""
            choice_str = input(
                f"{prompt_prefix} [1-{len(items)}]{hint_suffix} "
                "(or 'q' to cancel): "
            ).strip()

            if choice_str.lower() in {"q", "quit"}:
                return None

            if not choice_str.isdigit():
                print("Please enter a number or 'q' to cancel.")
                continue

            choice = int(choice_str)
            if 1 <= choice <= len(items):
                return choice - 1  # Convert to 0-based index

            print(f"Please choose a number between 1 and {len(items)}.")


