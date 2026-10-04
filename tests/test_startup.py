"""Startup cost: heavy libraries must only load when a command actually needs them.

Run in a subprocess, since this pytest process has already imported everything.
"""

import json
import subprocess
import sys

# ~0.6 s of imports together; see client_factory's module docstring.
HEAVY = (
    "googleapiclient",
    "google",
    "google_auth_oauthlib",
    "google_auth_httplib2",
    "httplib2",
    "dateparser",
)


def _loaded_heavy_modules(code: str) -> list[str]:
    probe = f"""
import json, sys
{code}
heavy = {HEAVY!r}
print(json.dumps(sorted({{m.split(".")[0] for m in sys.modules if m.split(".")[0] in heavy}})))
"""
    result = subprocess.run(
        [sys.executable, "-c", probe], capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestStartupImports:
    def test_import_app_GIVEN_nothing_run_THEN_no_heavy_libraries(self) -> None:
        assert _loaded_heavy_modules("import gtasks.app") == []

    def test_build_parser_and_help_text_THEN_no_heavy_libraries(self) -> None:
        code = "from gtasks.cli.cli import build_parser; build_parser().format_help()"

        assert _loaded_heavy_modules(code) == []
