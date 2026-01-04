from collections.abc import Callable
from unittest.mock import create_autospec

from pytest import CaptureFixture

from gtasks.utils.prompter import Prompter


class TestPrompterInit:
    def test_init_GIVEN_default_input_THEN_uses_builtin_input(self):
        prompter = Prompter()

        assert prompter._input_fn is input


class TestPromptIndexChoice:
    def test_prompt_index_choice_GIVEN_one_option_THEN_returns_zero(self):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(1, "Select: ")

        assert result == 0
        # Should not prompt the user if only one option
        assert mock_input.call_count == 0

    def test_prompt_index_choice_GIVEN_valid_choice_THEN_returns_zero_indexed(self):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.return_value = "2"
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 1  # 0-indexed

    def test_prompt_index_choice_GIVEN_quit_THEN_returns_none(self):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.return_value = "q"
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result is None

    def test_prompt_index_choice_GIVEN_quit_uppercase_THEN_returns_none(self):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.return_value = "Q"
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result is None

    def test_prompt_index_choice_GIVEN_invalid_then_quit_THEN_returns_none(
        self, capsys: CaptureFixture[str]
    ):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.side_effect = ["foo", "q"]
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result is None
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    def test_prompt_index_choice_GIVEN_out_of_range_then_valid_THEN_retries(
        self, capsys: CaptureFixture[str]
    ):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.side_effect = ["5", "2"]
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 1
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Please enter a number between 1 and 3" in captured.out

    def test_prompt_index_choice_GIVEN_invalid_input_then_valid_THEN_retries(
        self, capsys: CaptureFixture[str]
    ):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.side_effect = ["abc", "1"]
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 0
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    def test_prompt_index_choice_GIVEN_whitespace_around_input_THEN_strips(self):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.return_value = "  2  "
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 1

    def test_prompt_index_choice_GIVEN_zero_THEN_retries(
        self, capsys: CaptureFixture[str]
    ):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.side_effect = ["0", "1"]
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 0
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Please enter a number between 1 and 3" in captured.out

    def test_prompt_index_choice_GIVEN_negative_number_THEN_retries(
        self, capsys: CaptureFixture[str]
    ):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.side_effect = ["-1", "1"]
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 0
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Please enter a number between 1 and 3" in captured.out

    def test_prompt_index_choice_GIVEN_first_option_THEN_returns_zero(self):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.return_value = "1"
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 0

    def test_prompt_index_choice_GIVEN_last_option_THEN_returns_last_index(self):
        mock_input: Callable[[str], str] = create_autospec(input, spec_set=True)
        mock_input.return_value = "3"
        prompter = Prompter(input_fn=mock_input)

        result: int | None = prompter.prompt_index_choice(3, "Select: ")

        assert result == 2
