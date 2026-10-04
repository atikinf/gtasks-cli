"""Isolation every test needs from the developer's own terminal and shell."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from rich.console import Console

from gtasks import defaults
from gtasks.cli import ui
from gtasks.cli.title_id_resolution import ENV_VAR


def _plain_console(*, stderr: bool = False) -> Console:
    # No `file=`: the console resolves sys.stdout/sys.stderr at write time, so capsys captures.
    # Explicit no-colour so FORCE_COLOR or a real TTY (pytest -s) can't add escape codes.
    return Console(
        theme=ui.THEME,
        highlight=False,
        emoji=False,
        width=100,
        force_terminal=False,
        color_system=None,
        stderr=stderr,
    )


@pytest.fixture(autouse=True)
def plain_output_and_clean_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    monkeypatch.delenv(ENV_VAR, raising=False)
    # Files gtasks manages itself (e.g. the last listing) must never touch the real ~/.cache.
    monkeypatch.setattr(defaults, "CACHE_DIR", tmp_path / "cache")
    ui.use_consoles(_plain_console(), _plain_console(stderr=True))
    yield
    ui.use_consoles(None, None)
