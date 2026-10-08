"""Completion subcommand - print the shell snippet that enables Tab completion."""

import argparse
from typing import TYPE_CHECKING

from gtasks.cli import ui
from gtasks.utils.config import Config

if TYPE_CHECKING:
    from gtasks.client.protocol import ClientProvider

SHELLS = ("bash", "zsh", "fish")

# zsh filters candidates by its own matching, case-sensitively unless the user configured
# otherwise; gtasks matches titles ignoring case, so make zsh agree - for gtasks only.
_ZSH_CASE_INSENSITIVE = "zstyle ':completion:*:*:gtasks:*' matcher-list 'm:{a-z}={A-Za-z}'"


def cmd_completion(args: argparse.Namespace, get_client: "ClientProvider", cfg: Config) -> None:
    """Handle the 'completion' command.

    Never calls `get_client`: setting up completion needs no sign-in. Both params are unused;
    they match the uniform dispatch signature.
    """
    import argcomplete

    snippet = argcomplete.shellcode(["gtasks"], shell=args.shell)
    if args.shell == "zsh":
        snippet = f"{snippet.rstrip()}\n{_ZSH_CASE_INSENSITIVE}\n"
    ui.raw(snippet)


def add_subparser_completion(subparsers) -> None:
    """Add the 'completion' subcommand."""
    completion_parser = subparsers.add_parser(
        "completion",
        help="Print shell setup for Tab completion",
        description=(
            "Print the snippet that enables Tab completion of task and list titles. Add it to "
            'your shell config, e.g. `eval "$(gtasks completion zsh)"` in ~/.zshrc, '
            '`eval "$(gtasks completion bash)"` in ~/.bashrc, or '
            "`gtasks completion fish | source` in ~/.config/fish/config.fish."
        ),
    )
    completion_parser.add_argument("shell", choices=SHELLS, help="Your shell")
    completion_parser.set_defaults(func=cmd_completion)
