"""Interactive prompts and input validation."""

import re
from collections.abc import Callable

HINT = "Please choose a number between 1 and {num_options} or 'q' to cancel."


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
