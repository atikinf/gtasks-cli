"""Options every API command shares."""

import argparse

import pytest


class TestRefreshOption:
    @pytest.mark.parametrize(
        "argv",
        [
            ["--refresh"],
            ["--refresh", "tasks"],
            ["tasks", "--refresh"],
            ["lists", "--refresh"],
            ["use", "Work", "--refresh"],
            ["add", "Milk", "--refresh"],
            ["done", "1", "--refresh"],
            ["delete", "1", "--refresh"],
        ],
    )
    def test_GIVEN_refresh_on_any_api_command_THEN_parsed(
        self, parser: argparse.ArgumentParser, argv: list[str]
    ) -> None:
        assert parser.parse_args(argv).refresh is True

    @pytest.mark.parametrize("argv", [[], ["tasks"], ["use", "Work"], ["done", "1"]])
    def test_GIVEN_no_refresh_THEN_false(
        self, parser: argparse.ArgumentParser, argv: list[str]
    ) -> None:
        assert parser.parse_args(argv).refresh is False
