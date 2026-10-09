import argparse
from collections.abc import Iterator
from unittest.mock import MagicMock, Mock, create_autospec, patch

import pytest
from pytest import CaptureFixture
from rich.text import Text

from gtasks import defaults
from gtasks.cli.errors import Cancelled
from gtasks.cli.parsers.auth_parser import (
    cmd_auth,
    mask_client_id,
    mask_secret,
    prompt_setup_credentials,
    validate_client_id,
    validate_client_secret,
)
from gtasks.client.client_factory import SignInRequiredError
from gtasks.utils.config import Config

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

    def test_GIVEN_current_and_enter_twice_THEN_keeps_both(self, mock_input: Mock) -> None:
        mock_input.side_effect = ["", ""]

        result = prompt_setup_credentials(mock_input, current=(CLIENT_ID, CLIENT_SECRET))

        assert result == (CLIENT_ID, CLIENT_SECRET)

    def test_GIVEN_current_THEN_prompts_show_both_shortened(self, mock_input: Mock) -> None:
        mock_input.side_effect = ["", ""]

        prompt_setup_credentials(mock_input, current=(CLIENT_ID, CLIENT_SECRET))

        id_prompt, secret_prompt = (c.args[0] for c in mock_input.call_args_list)
        assert id_prompt == "Enter the client ID [0000...-...fake.apps.googleusercontent.com]: "
        assert secret_prompt == f"Enter the client secret [****{CLIENT_SECRET[-4:]}]: "

    def test_GIVEN_current_THEN_defaults_dimmed_and_question_not(self) -> None:
        prompts: list[Text] = []

        def record(prompt: Text, input_fn: object) -> str:
            prompts.append(prompt)
            return ""

        with patch("gtasks.cli.parsers.auth_parser.ui.ask", side_effect=record):
            prompt_setup_credentials(current=(CLIENT_ID, CLIENT_SECRET))

        for prompt in prompts:
            dimmed = "".join(prompt.plain[sp.start : sp.end] for sp in prompt.spans
                             if sp.style == "muted")
            assert dimmed.startswith(" [") and dimmed.endswith("]")
            assert prompt.plain.startswith("Enter the ")

    def test_GIVEN_new_client_id_THEN_secret_has_no_default(self, mock_input: Mock) -> None:
        new_id = "1" * 12 + "-" + "new0" * 8 + ".apps.googleusercontent.com"
        # Enter on the secret must not reuse the old client's secret: it asks again.
        mock_input.side_effect = [new_id, "", CLIENT_SECRET]

        result = prompt_setup_credentials(mock_input, current=(CLIENT_ID, "OLD-" + "x" * 20))

        assert result == (new_id, CLIENT_SECRET)
        assert "[" not in mock_input.call_args_list[1].args[0]


@pytest.mark.parametrize(
    "client_id, shown",
    [
        (
            "1" * 11 + "-" + "fake" * 7 + "abcd.apps.googleusercontent.com",
            "1111...-...abcd.apps.googleusercontent.com",
        ),
        ("not-the-usual-shape", "not-the-usual-shape"),
    ],
)
def test_mask_client_id_THEN_keeps_distinguishing_ends(client_id: str, shown: str) -> None:
    assert mask_client_id(client_id) == shown


def test_mask_secret_THEN_last_four_only() -> None:
    assert mask_secret("GOCSPX-abcdefghijWXYZ") == "****WXYZ"


class TestCmdAuth:
    @pytest.fixture
    def flow(self) -> Iterator[dict[str, MagicMock]]:
        """Everything cmd_auth reaches outside itself, patched where it's looked up."""
        names = ("read_creds_from_file", "refresh_saved_sign_in", "sign_in", "clear_cache")
        mocks = {n: MagicMock() for n in names}
        with patch.multiple("gtasks.cli.parsers.auth_parser", **mocks):
            yield mocks

    def _run(self, *answers: str) -> None:
        with patch("builtins.input", side_effect=list(answers)):
            cmd_auth(argparse.Namespace(), lambda **_: None, Config(defaults.config_file()))

    def _signed_in(self, flow: dict[str, MagicMock]) -> None:
        flow["read_creds_from_file"].return_value = MagicMock(
            client_id=CLIENT_ID, client_secret=CLIENT_SECRET
        )

    def test_GIVEN_no_saved_sign_in_THEN_signs_in_with_entered_client(
        self, flow: dict[str, MagicMock]
    ) -> None:
        flow["read_creds_from_file"].return_value = None

        self._run(CLIENT_ID, CLIENT_SECRET)

        flow["sign_in"].assert_called_once_with(
            defaults.token_file(), CLIENT_ID, CLIENT_SECRET
        )
        flow["clear_cache"].assert_called_once()

    def test_GIVEN_signed_in_and_kept_THEN_no_new_sign_in_and_cache_kept(
        self, flow: dict[str, MagicMock], capsys: CaptureFixture[str]
    ) -> None:
        self._signed_in(flow)

        self._run("", "", "")  # keep ID, keep secret, don't sign in again

        flow["refresh_saved_sign_in"].assert_called_once_with(defaults.token_file())
        flow["sign_in"].assert_not_called()
        flow["clear_cache"].assert_not_called()
        assert "Still signed in" in capsys.readouterr().out

    def test_GIVEN_signed_in_and_asks_to_sign_in_again_THEN_new_sign_in(
        self, flow: dict[str, MagicMock]
    ) -> None:
        self._signed_in(flow)

        self._run("", "", "y")

        flow["sign_in"].assert_called_once_with(
            defaults.token_file(), CLIENT_ID, CLIENT_SECRET
        )
        flow["clear_cache"].assert_called_once()

    def test_GIVEN_signed_in_and_new_client_THEN_signs_in_without_asking(
        self, flow: dict[str, MagicMock]
    ) -> None:
        self._signed_in(flow)
        new_id = "1" * 12 + "-" + "new0" * 8 + ".apps.googleusercontent.com"

        self._run(new_id, CLIENT_SECRET)  # no third answer: no "sign in again?" question

        flow["sign_in"].assert_called_once_with(defaults.token_file(), new_id, CLIENT_SECRET)
        flow["refresh_saved_sign_in"].assert_not_called()

    def test_GIVEN_kept_but_saved_sign_in_dead_THEN_signs_in_again(
        self, flow: dict[str, MagicMock]
    ) -> None:
        self._signed_in(flow)
        flow["refresh_saved_sign_in"].side_effect = SignInRequiredError("revoked")

        self._run("", "", "")

        flow["sign_in"].assert_called_once()

    def test_GIVEN_cancelled_THEN_nothing_touched(self, flow: dict[str, MagicMock]) -> None:
        self._signed_in(flow)

        with pytest.raises(Cancelled):
            self._run("q")

        flow["sign_in"].assert_not_called()
        flow["clear_cache"].assert_not_called()

