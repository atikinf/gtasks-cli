"""How typed text matches task and list titles. Pure functions, no I/O.

Shared by Enter-matching (`title_id_resolution`) and Tab completion (`completion`), so what
the shell offers and what a command accepts never disagree.

Matching ignores case and runs of whitespace. A query that equals a title is an *exact* match
and always wins; otherwise any title containing the query is a *partial* match; with neither,
close spellings are offered as suggestions.
"""

import difflib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

MAX_SUGGESTIONS = 3
_SUGGESTION_CUTOFF = 0.6


def normalize(text: str) -> str:
    """Comparison form of a title: case-folded, trimmed, inner whitespace collapsed."""
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class TitleMatch[T]:
    kind: Literal["exact", "partial", "none"]
    matches: list[T] = field(default_factory=list)
    # Titles that are close to the query, offered as "Did you mean ...?" when nothing matched.
    suggestions: list[str] = field(default_factory=list)


def match_titles[T: Mapping[str, Any]](items: Iterable[T], query: str) -> TitleMatch[T]:
    """Find items whose title matches `query`; items without an ID are skipped, since there'd
    be nothing to act on."""
    candidates = [item for item in items if item.get("id")]
    wanted = normalize(query)
    titled = [(normalize(item.get("title") or ""), item) for item in candidates]

    exact = [item for title, item in titled if title == wanted]
    if exact:
        return TitleMatch("exact", exact)

    partial = [item for title, item in titled if wanted and wanted in title]
    if partial:
        return TitleMatch("partial", partial)

    titles = [item.get("title") or "" for item in candidates]
    by_normalized = {normalize(t): t for t in reversed(titles)}  # first title wins
    close = difflib.get_close_matches(
        wanted, list(by_normalized), n=MAX_SUGGESTIONS, cutoff=_SUGGESTION_CUTOFF
    )
    return TitleMatch("none", suggestions=[by_normalized[t] for t in close])


def complete_titles(titles: Iterable[str], prefix: str) -> list[str]:
    """Titles starting with `prefix` (ignoring case and spacing), de-duplicated, in order."""
    wanted = normalize(prefix)
    seen: set[str] = set()
    completions = []
    for title in titles:
        if title and title not in seen and normalize(title).startswith(wanted):
            seen.add(title)
            completions.append(title)
    return completions
