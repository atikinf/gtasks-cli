import argparse
import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gtasks.client.api_client import ApiClient

HINT = "Please choose a number between 1 and {num_options} or 'q' to cancel."

_STRIKETHROUGH = "\033[9m"
_RESET = "\033[0m"


def _ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


def _fmt_due(due: str) -> str:
    """Format an RFC 3339 due date string as e.g. 'Tuesday, April 22nd'."""
    try:
        dt = datetime.fromisoformat(due.replace("Z", "+00:00")).astimezone(timezone.utc)
        return dt.strftime("%A, %B ") + _ordinal(dt.day)
    except ValueError:
        return due


def _fmt_title(title: str, completed: bool) -> str:
    if completed:
        return f"{_STRIKETHROUGH}{title}{_RESET}"
    return title


def print_tasks(tasks: list, args: argparse.Namespace) -> None:
    for ix, task in enumerate(tasks, 1):
        raw_title: str = task.get("title", "<no title>")
        notes = task.get("notes")
        due = task.get("due")
        completed = task.get("status") == "completed"
        title = _fmt_title(raw_title, completed)
        if args.show_ids:
            id_ = task.get("id", "<no id>")
            print(f"{ix}.   [{id_}] {title}", end="")
        else:
            print(f"{ix}.   {title}", end="")
        if due:
            print(f"        (Due: {_fmt_due(due)})", end="")
        print()
        if notes:
            print(f"        Notes: {notes}")


def print_tasklists(tasklists: list, args: argparse.Namespace) -> None:
    for ix, tasklist in enumerate(tasklists, 1):
        title = tasklist.get("title", "<no title>")
        if args.show_ids:
            id_ = tasklist.get("id", "<no id>")
            print(f"{ix}.   [{id_}] {title}")
        else:
            print(f"{ix}.   {title}")


def prompt_setup_credentials(
    input_fn: Callable[[str], str] = input,
) -> None | tuple[str, str]:
    client_id: None | str
    client_secret: None | str
    while True:
        client_id = input_fn("Enter the client ID: ")
        if client_id == "q":
            return None
        elif not validate_client_id(client_id):
            print("Invalid input. Double check that you entered the correct client ID.")
        else:
            break
    while True:
        client_secret = input_fn("Enter the client secret: ")
        if client_secret == "q":
            return None
        elif not validate_client_secret(client_secret):
            print(
                "Invalid input. Double check that you entered the correct client secret."
            )
        else:
            break
    return client_id, client_secret


def validate_client_id(client_id: str) -> bool:
    """
    Expected format: {digits}-{alphanumeric}.apps.googleusercontent.com
    """
    pattern = r"^\d{5,20}-[a-z0-9]{20,50}\.apps\.googleusercontent\.com$"
    return bool(re.match(pattern, client_id))


def validate_client_secret(client_secret: str) -> bool:
    """
    Expected format: {alphanumeric with possible hyphens}
    """
    pattern = r"^[A-Za-z0-9_-]{20,50}$"
    return bool(re.match(pattern, client_secret))


def prompt_choose_task_id(
    ids: list[str], tasks: list, task_title: str
) -> None | str:
    if len(ids) <= 0:
        print(f"Error: No task found with title '{task_title}'!")
    elif len(ids) == 1:
        return ids[0]
    else:
        filtered_tasks = [t for t in tasks if t.get("id") in ids]
        print_tasks(filtered_tasks, argparse.Namespace(show_ids=True))
        ix_choice: None | int = prompt_index_choice(
            len(filtered_tasks),
            f"Found multiple tasks with title '{task_title}'.",
            input,
        )
        if ix_choice is not None:
            return filtered_tasks[ix_choice].get("id")

    return None


def prompt_choose_tasklist_id(matches: list, tasklist_title: str) -> None | str:
    ids = [tl.get("id") for tl in matches if tl.get("id") is not None]
    if len(ids) == 0:
        print(f"Error: No tasklist found with title {tasklist_title}!")
    elif len(ids) == 1:
        return ids[0]
    else:
        print_tasklists(matches, argparse.Namespace(show_ids=True))
        ix_choice: None | int = prompt_index_choice(
            len(matches),
            f"Found multiple tasklists with title {tasklist_title}.",
            input,
        )
        if ix_choice is not None:
            return matches[ix_choice].get("id")

    return None


def resolve_tasks_from_inputs(
    inputs: list[str],
    client: "ApiClient",
    tasklist_id: str,
) -> list:
    """Resolve user inputs (1-based indices or title strings) to full task objects.

    Digit inputs are treated as 1-based display indices into the needsAction list
    (fetched lazily on the first digit input). Other inputs are matched by title
    with interactive disambiguation when multiple tasks share a title.
    """
    all_tasks: list | None = None
    resolved: list = []
    for inp in inputs:
        if inp.isdigit():
            if all_tasks is None:
                all_tasks = client.get_tasks(tasklist_id, show_completed=False)
            ix = int(inp) - 1
            if 0 <= ix < len(all_tasks):
                task = all_tasks[ix]
                if task.get("id"):
                    resolved.append(task)
            else:
                n = len(all_tasks) if all_tasks else 0
                print(f"Error: index {inp} is out of range (list has {n} tasks)")
        else:
            matches = client.resolve_task_from_title(inp, tasklist_id)
            ids = [t["id"] for t in matches if t.get("id")]
            task_id = prompt_choose_task_id(ids, matches, inp)
            if task_id:
                task = next((t for t in matches if t.get("id") == task_id), None)
                if task:
                    resolved.append(task)
    return resolved


def prompt_index_choice(
    num_options: int,
    prompt_prefix: str,
    input_fn: Callable[[str], str] = input,  # solely for testability
) -> int | None:
    assert num_options > 0

    if num_options == 1:
        return 0

    while True:
        choice_str: str = input_fn(
            f"{prompt_prefix} [1-{num_options}] (or 'q' to cancel): "
        ).strip()

        if choice_str.lower() == "q":
            return None

        if not choice_str.isdigit():
            print("Invalid input. " + HINT.format(num_options=num_options))
            continue

        choice = int(choice_str)
        if 1 <= choice <= num_options:
            return choice - 1  # Convert to 0-based index

        print("Out of range. " + HINT.format(num_options=num_options))
