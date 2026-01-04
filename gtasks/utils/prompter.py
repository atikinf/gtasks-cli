from collections.abc import Callable


class Prompter:
    def __init__(self, input_fn: Callable[[str], str] = input) -> None:
        """Initialize Prompter with an input function.

        Args:
            input_fn: Input function for reading user input (injectable for tests).
        """
        self._input_fn = input_fn

    def prompt_index_choice(
        self,
        num_options: int,
        prompt: str,
    ) -> int | None:
        """Prompt user to select an index from a numbered list.

        Args:
            num_options: Total number of options (1-indexed display).
            prompt: The prompt message to display.

        Returns:
            The 0-indexed selection, or None if user quits.
        """
        assert num_options > 0

        if num_options == 1:
            return 0

        while True:
            choice = self._input_fn(prompt).strip()

            if choice.lower() == "q":
                return None

            try:
                choice_idx = int(choice) - 1
                if 0 <= choice_idx < num_options:
                    return choice_idx
                print(f"Please enter a number between 1 and {num_options}.")
            except ValueError:
                print("Invalid input. Enter a number or 'q' to quit.")
