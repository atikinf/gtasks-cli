from unittest.mock import Mock, create_autospec

import pytest
from pytest import CaptureFixture

from gtasks.cli.cli_utils import HINT, prompt_index_choice


@pytest.fixture
def mock_input() -> Mock:
    return create_autospec(input, spec_set=True)


class TestPromptIndexChoice:
    def test_prompt_index_choice_GIVEN_one_option_THEN_returns_zero(
        self, mock_input: Mock
    ):
        result: int | None = prompt_index_choice(1, "Select: ", input_fn=mock_input)

        assert result == 0
        # Should not prompt the user if only one option
        assert mock_input.call_count == 0

    @pytest.mark.parametrize("ret_val", ["q", "Q"])
    def test_prompt_index_choice_GIVEN_quit_uppercase_THEN_returns_none(
        self, ret_val: str, mock_input: Mock
    ):
        mock_input.return_value = ret_val

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result is None

    def test_prompt_index_choice_GIVEN_invalid_then_quit_THEN_returns_none(
        self, mock_input: Mock, capsys: CaptureFixture[str]
    ):
        mock_input.side_effect = ["foo", "q"]

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result is None
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    @pytest.mark.parametrize("invalid", ["5", "0", "-1"])
    def test_prompt_index_choice_GIVEN_invalid_then_valid_THEN_retries(
        self, invalid: str, mock_input: Mock, capsys: CaptureFixture[str]
    ):
        mock_input.side_effect = [invalid, "2"]

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 1
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert HINT.format(num_options=3) in captured.out

    def test_prompt_index_choice_GIVEN_invalid_input_then_valid_THEN_retries(
        self, mock_input: Mock, capsys: CaptureFixture[str]
    ):
        mock_input.side_effect = ["abc", "1"]

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 0
        assert mock_input.call_count == 2
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    def test_prompt_index_choice_GIVEN_whitespace_around_input_THEN_strips(
        self, mock_input: Mock
    ):
        mock_input.return_value = "  2  "

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 1

    def test_prompt_index_choice_GIVEN_first_option_THEN_returns_zero(
        self, mock_input: Mock
    ):
        mock_input.return_value = "1"

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 0

    def test_prompt_index_choice_GIVEN_last_option_THEN_returns_last_index(
        self, mock_input: Mock
    ):
        mock_input.return_value = "3"

        result: int | None = prompt_index_choice(3, "Select: ", input_fn=mock_input)

        assert result == 2
