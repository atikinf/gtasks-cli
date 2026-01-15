import argparse
from collections.abc import Callable

HINT = "Please choose a number between 1 and {num_options} or 'q' to cancel."


def print_tasks(tasks: list, args: argparse.Namespace) -> None:
    for ix, task in enumerate(tasks, 1):
        title: str = task.get("title", "<no title>")
        notes = task.get("notes")
        due = task.get("due")
        if args.show_ids:
            id_ = task.get("id", "<no id>")
            print(f"{ix}.   [{id_}] {title}", end="")
        else:
            print(f"{ix}.   {title}", end="")
        if due:
            print(f"        (Due: {due})", end="")
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


def prompt_choose_tasklist_id(
    ids: list[str], tasklists: list, tasklist_title: str
) -> None | str:
    if len(ids) <= 0:
        print(f"Error: No tasklist found with title {tasklist_title}!")
    elif len(ids) == 1:
        return ids[0]
    else:  # multiple resolved ids
        filtered_tasklists = [li for li in tasklists if li.get("id") in ids]
        print_tasklists(filtered_tasklists, argparse.Namespace(show_ids=True))
        ix_choice: None | int = prompt_index_choice(
            len(filtered_tasklists),
            f"Found multiple tasklists with title {tasklist_title}.",
            input,
        )
        if ix_choice:
            id_: str | None = filtered_tasklists[ix_choice].get("id")
            return id_

    return None


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
