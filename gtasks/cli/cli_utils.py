def prompt_index_choice(
    items: list,
    prompt_prefix: str,
    current_hint: str | None = None,
) -> int | None:
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
            f"{prompt_prefix} [1-{len(items)}]{hint_suffix} (or 'q' to cancel): "
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
