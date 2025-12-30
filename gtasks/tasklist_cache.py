from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Optional

import json
import sys


# Default config directory: ~/.config/gtasks-cli/
CONFIG_DIR: Path = Path("~/.config/gtasks-cli").expanduser()

# ANSI escape codes for terminal formatting
BOLD = "\033[1m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class TaskListCache:
    """Cache for mapping TaskList IDs to TaskList Titles (bidirectional).

    Stores the ID->Title mapping as a JSON file in the config directory for
    persistence across CLI invocations. Maintains an in-memory reverse index
    (Title->ID) for efficient bidirectional lookups.

    Attributes:
        _cache_path: Path to the JSON cache file.
        _id_to_title: Dictionary mapping TaskList IDs to Titles (canonical, persisted).
        _title_to_id: Dictionary mapping Titles to IDs (derived, in-memory only).
    """

    def __init__(
        self,
        cache_path: str | Path = CONFIG_DIR / "tasklists_cache.json",
    ) -> None:
        """Initialize the TaskList cache.

        Args:
            cache_path: Path where the cache file will be stored.
        """
        self._cache_path: Path = Path(cache_path).expanduser()
        self._id_to_title: dict[str, str] = {}
        self._title_to_id: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        """Load cache from disk if it exists."""
        if not self._cache_path.exists():
            self._id_to_title = {}
            self._title_to_id = {}
            return

        try:
            with self._cache_path.open("r", encoding="utf-8") as f:
                self._id_to_title = json.load(f)
        except (json.JSONDecodeError, OSError):
            # If cache is corrupted or unreadable, start fresh
            self._id_to_title = {}

        self._rebuild_reverse_index()

    def update_from_api_response(
        self,
        response: dict[str, Any],
        warn_duplicates: bool = True,
    ) -> None:
        """Update cache from a tasklists.list() API response.

        Parses the response from Google Tasks API tasklists.list() call
        and updates the cache with all TaskList ID -> Title mappings.

        Args:
            response: The raw response dictionary from tasklists.list().execute().
                      Expected format: {"items": [{"id": "...", "title": "..."}, ...]}
            warn_duplicates: If True, print a warning when duplicate titles are detected.
        """
        items = response.get("items", [])
        for item in items:
            tasklist_id = item.get("id")
            tasklist_title = item.get("title", "")
            if tasklist_id:
                self._id_to_title[tasklist_id] = tasklist_title
                self._title_to_id[tasklist_title] = tasklist_id
        self._save()
        if warn_duplicates:
            self._warn_duplicate_titles()

    def update_from_items(
        self,
        items: list[dict[str, Any]],
        warn_duplicates: bool = True,
    ) -> None:
        """Update cache from a list of TaskList items.

        Args:
            items: List of TaskList dictionaries with "id" and "title" keys.
            warn_duplicates: If True, print a warning when duplicate titles are detected.
        """
        for item in items:
            tasklist_id = item.get("id")
            tasklist_title = item.get("title", "")
            if tasklist_id:
                self._id_to_title[tasklist_id] = tasklist_title
                self._title_to_id[tasklist_title] = tasklist_id
        self._save()
        if warn_duplicates:
            self._warn_duplicate_titles()

    def get_title(self, tasklist_id: str) -> Optional[str]:
        """Get the cached title for a TaskList ID.

        Args:
            tasklist_id: The TaskList ID to look up.

        Returns:
            The cached title, or None if not found.
        """
        return self._id_to_title.get(tasklist_id)

    def get_id(self, title: str) -> Optional[str]:
        """Get a TaskList ID by its title.

        Note: If multiple TaskLists have the same title, returns the last one
        that was added to the cache.

        Args:
            title: The TaskList title to search for.

        Returns:
            The TaskList ID, or None if not found.
        """
        return self._title_to_id.get(title)

    def get_all(self) -> dict[str, str]:
        """Get the entire cache as a dictionary (ID -> Title).

        Returns:
            Dictionary mapping TaskList IDs to Titles.
        """
        return self._id_to_title.copy()

    def get_all_by_title(self) -> dict[str, str]:
        """Get the entire cache as a dictionary (Title -> ID).

        Returns:
            Dictionary mapping TaskList Titles to IDs.
        """
        return self._title_to_id.copy()

    def clear(self) -> None:
        """Clear the cache both in memory and on disk."""
        self._id_to_title = {}
        self._title_to_id = {}
        if self._cache_path.exists():
            self._cache_path.unlink()

    def is_empty(self) -> bool:
        """Check if the cache is empty.

        Returns:
            True if cache has no entries, False otherwise.
        """
        return len(self._id_to_title) == 0

    def _save(self) -> None:
        """Persist cache to disk."""
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        with self._cache_path.open("w", encoding="utf-8") as f:
            json.dump(self._id_to_title, f, indent=2, ensure_ascii=False)

    def _rebuild_reverse_index(self) -> None:
        """Rebuild the title->id reverse index from the canonical id->title mapping.

        Note: If multiple TaskLists share the same title, the last one encountered
        will be stored in the reverse index.
        """
        self._title_to_id = {title: id_ for id_, title in self._id_to_title.items()}

    def _find_duplicate_titles(self) -> list[str]:
        """Find titles that are shared by multiple TaskLists.

        Returns:
            List of titles that appear more than once.
        """
        title_counts = Counter[str](self._id_to_title.values())
        return [title for title, count in title_counts.items() if count > 1]

    def _warn_duplicate_titles(self) -> None:
        """Print a warning if any TaskLists share the same title."""
        duplicates = self._find_duplicate_titles()
        if not duplicates:
            return

        duplicate_list = ", ".join(f"'{title}'" for title in duplicates)
        warning = (
            f"{BOLD}{YELLOW}Warning:{RESET} Multiple task lists share the same title: "
            f"{duplicate_list}.\n"
            f"You will need to use the task list ID (instead of the title) to refer to "
            f"these lists in commands.\n"
            f"Use {BOLD}gtasks lists --show-ids{RESET} to see the IDs."
        )
        print(warning, file=sys.stderr)

    def __contains__(self, tasklist_id: str) -> bool:
        """Check if a TaskList ID is in the cache."""
        return tasklist_id in self._id_to_title

    def __len__(self) -> int:
        """Return the number of cached TaskLists."""
        return len(self._id_to_title)

