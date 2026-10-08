from unittest.mock import Mock, create_autospec

import pytest
from pytest import CaptureFixture

from gtasks.cli.parsers.auth_parser import (
    prompt_setup_credentials,
    validate_client_id,
    validate_client_secret,
)

# Synthetic values in the shapes Google issues for Desktop OAuth clients. Built from parts so
# they're obviously fake (and don't trip secret scanners on push).
CLIENT_ID = "0" * 12 + "-" + "fake" * 8 + ".apps.googleusercontent.com"
CLIENT_SECRET = "FAKE-" + "Secret_0" * 3 + "xy"


@pytest.fixture
def mock_input() -> Mock:
    return create_autospec(input, spec_set=True)


class TestValidateClientId:
    @pytest.mark.parametrize(
        "client_id",
        [
            CLIENT_ID,
            "12345-" + "a" * 20 + ".apps.googleusercontent.com",  # shortest accepted
            "1" * 20 + "-" + "z9" * 25 + ".apps.googleusercontent.com",  # longest accepted
        ],
        ids=["typical", "shortest", "longest"],
    )
    def test_GIVEN_well_formed_id_THEN_valid(self, client_id: str) -> None:
        assert validate_client_id(client_id) is True

    @pytest.mark.parametrize(
        "client_id",
        [
            "",
            CLIENT_SECRET,  # pasted the secret into the ID prompt
            CLIENT_ID.replace(".apps.googleusercontent.com", ".example.com"),
            CLIENT_ID.removesuffix(".apps.googleusercontent.com"),
            CLIENT_ID.upper(),  # the suffix after the digits is lowercase only
            "1234-" + "a" * 32 + ".apps.googleusercontent.com",  # too few digits
            "123456789012-" + "a" * 19 + ".apps.googleusercontent.com",  # suffix too short
            " " + CLIENT_ID,
            CLIENT_ID + " ",
            CLIENT_ID + "\n",
            CLIENT_ID.replace(".", "x"),  # dots must be literal
        ],
        ids=["empty", "secret-instead", "wrong-domain", "no-domain", "uppercase", "few-digits",
             "short-suffix", "leading-space", "trailing-space", "trailing-newline",
             "dot-wildcard"],
    )
    def test_GIVEN_malformed_id_THEN_invalid(self, client_id: str) -> None:
        assert validate_client_id(client_id) is False


class TestValidateClientSecret:
    @pytest.mark.parametrize(
        "secret",
        [CLIENT_SECRET, "a" * 20, "Z_-9" * 12 + "ab"],
        ids=["typical", "shortest", "longest"],
    )
    def test_GIVEN_well_formed_secret_THEN_valid(self, secret: str) -> None:
        assert validate_client_secret(secret) is True

    @pytest.mark.parametrize(
        "secret",
        [
            "",
            "a" * 19,
            "a" * 51,
            CLIENT_ID,  # pasted the ID into the secret prompt
            CLIENT_SECRET[:10] + " " + CLIENT_SECRET[10:],
            CLIENT_SECRET + " ",
            CLIENT_SECRET + "\n",
            CLIENT_SECRET[:-1] + "!",
        ],
        ids=["empty", "too-short", "too-long", "id-instead", "inner-space", "trailing-space",
             "trailing-newline", "symbol"],
    )
    def test_GIVEN_malformed_secret_THEN_invalid(self, secret: str) -> None:
        assert validate_client_secret(secret) is False


class TestPromptSetupCredentials:
    def test_GIVEN_values_pasted_with_whitespace_THEN_trimmed_and_accepted(
        self, mock_input: Mock
    ) -> None:
        mock_input.side_effect = [f"  {CLIENT_ID}\t", f" {CLIENT_SECRET}  "]

        assert prompt_setup_credentials(mock_input) == (CLIENT_ID, CLIENT_SECRET)

    def test_GIVEN_invalid_then_valid_THEN_asks_again(
        self, mock_input: Mock, capsys: CaptureFixture[str]
    ) -> None:
        mock_input.side_effect = ["not an id", CLIENT_ID, "short", CLIENT_SECRET]

        assert prompt_setup_credentials(mock_input) == (CLIENT_ID, CLIENT_SECRET)
        assert capsys.readouterr().out.count("Invalid input") == 2

    @pytest.mark.parametrize(
        "answers", [["q"], [" q "], [CLIENT_ID, "q"]], ids=["at-id", "padded", "at-secret"]
    )
    def test_GIVEN_q_THEN_cancelled(self, mock_input: Mock, answers: list[str]) -> None:
        mock_input.side_effect = answers

        assert prompt_setup_credentials(mock_input) is None
