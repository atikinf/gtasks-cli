"""Small JSON files that gtasks manages itself (the cache, the last listing shown).

Shared conventions, so every such file behaves the same:
- **Schema-versioned.** Each file carries a semver `schema`. A reader accepts the same MAJOR
  version (a newer MINOR only adds optional fields, which it ignores) and treats anything else
  as missing. Bump MAJOR when an existing field changes shape or meaning, MINOR when adding one.
- **Never breaks a command.** An unreadable, corrupt or incompatible file reads as missing, and
  a failed write (read-only disk, disk full) is skipped.
- **Atomic and private.** Writes go to a temp file that is renamed into place, so a reader or a
  concurrent gtasks process never sees half a file. Files are 0600 and the directories gtasks
  creates for them 0700, since they hold task titles and notes.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def schema_compatible(found: object, expected: str) -> bool:
    """Whether a file written with schema `found` is readable by code expecting `expected`."""
    if not isinstance(found, str):
        return False
    try:
        return int(found.split(".")[0]) == int(expected.split(".")[0])
    except ValueError:
        return False


def read_json(path: Path, schema: str) -> dict[str, Any]:
    """The file's fields (without `schema`) if readable and compatible, else an empty dict."""
    try:
        doc = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    if not isinstance(doc, dict) or not schema_compatible(doc.pop("schema", None), schema):
        return {}
    return doc


def write_json(path: Path, doc: dict[str, Any], schema: str, *, root: Path) -> bool:
    """Atomically write `doc` stamped with `schema`; True if it was written.

    Every directory from `root` down to the file's is created (or reset to) owner-only.
    """
    try:
        _ensure_private_dirs(root, path.parent)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"schema": schema, **doc}, f)
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
    except OSError:
        return False
    return True


def unlink_quietly(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _ensure_private_dirs(root: Path, directory: Path) -> None:
    chain = [root]
    if directory != root and directory.is_relative_to(root):
        for part in directory.relative_to(root).parts:
            chain.append(chain[-1] / part)
    elif directory != root:
        chain.append(directory)
    for d in chain:
        d.mkdir(mode=0o700, parents=True, exist_ok=True)
        d.chmod(0o700)
