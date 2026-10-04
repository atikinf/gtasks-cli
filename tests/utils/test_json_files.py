"""The file conventions shared by the cache and the listing snapshot."""

import json
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from gtasks.utils.json_files import read_json, schema_compatible, write_json

SCHEMA = "1.2.0"


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "root"


class TestSchemaCompatible:
    @pytest.mark.parametrize(
        "found, compatible",
        [
            ("1.2.0", True),
            ("1.7.3", True),
            ("1.0.0", True),
            ("2.0.0", False),
            ("0.9.0", False),
            ("garbage", False),
            (None, False),
            (1, False),
        ],
        ids=["same", "newer-minor", "older-minor", "newer-major", "older-major", "malformed",
             "missing", "not-a-string"],
    )
    def test_GIVEN_version_THEN_only_same_major_compatible(
        self, found: object, compatible: bool
    ) -> None:
        assert schema_compatible(found, SCHEMA) is compatible


class TestReadJson:
    def test_GIVEN_written_THEN_fields_without_schema(self, root: Path) -> None:
        path = root / "f.json"
        write_json(path, {"a": 1}, SCHEMA, root=root)

        assert read_json(path, SCHEMA) == {"a": 1}

    def test_GIVEN_newer_minor_with_unknown_fields_THEN_still_read(self, root: Path) -> None:
        root.mkdir()
        path = root / "f.json"
        path.write_text(json.dumps({"schema": "1.9.0", "a": 1, "added_later": True}))

        assert read_json(path, SCHEMA) == {"a": 1, "added_later": True}

    @pytest.mark.parametrize(
        "content",
        ["{not json", "[]", json.dumps({"schema": "2.0.0", "a": 1}), json.dumps({"a": 1})],
        ids=["bad-json", "not-an-object", "other-major", "no-schema"],
    )
    def test_GIVEN_unusable_file_THEN_empty(self, root: Path, content: str) -> None:
        root.mkdir()
        path = root / "f.json"
        path.write_text(content)

        assert read_json(path, SCHEMA) == {}

    def test_GIVEN_missing_or_unreadable_THEN_empty(self, root: Path) -> None:
        (root / "dir.json").mkdir(parents=True)  # reading a directory raises an OSError

        assert read_json(root / "missing.json", SCHEMA) == {}
        assert read_json(root / "dir.json", SCHEMA) == {}


class TestWriteJson:
    def test_GIVEN_ok_THEN_true_and_stamped_with_schema(self, root: Path) -> None:
        path = root / "a" / "f.json"

        assert write_json(path, {"a": 1}, SCHEMA, root=root) is True
        assert json.loads(path.read_text()) == {"schema": SCHEMA, "a": 1}

    def test_GIVEN_path_blocked_by_a_file_THEN_false(self, tmp_path: Path) -> None:
        blocked = tmp_path / "blocked"
        blocked.write_text("a file where the folder should be")

        assert write_json(blocked / "f.json", {}, SCHEMA, root=blocked) is False

    def test_GIVEN_disk_full_THEN_false(self, root: Path) -> None:
        with patch("gtasks.utils.json_files.tempfile.mkstemp", side_effect=OSError(28, "full")):
            assert write_json(root / "f.json", {}, SCHEMA, root=root) is False

    def test_GIVEN_failure_after_temp_file_created_THEN_false_and_temp_removed(
        self, root: Path
    ) -> None:
        with patch("gtasks.utils.json_files.os.replace", side_effect=OSError("boom")):
            assert write_json(root / "f.json", {}, SCHEMA, root=root) is False

        assert list(root.iterdir()) == []

    def test_GIVEN_repeated_writes_THEN_no_temp_files_left(self, root: Path) -> None:
        write_json(root / "f.json", {"n": 1}, SCHEMA, root=root)
        write_json(root / "f.json", {"n": 2}, SCHEMA, root=root)

        assert [p.name for p in root.iterdir()] == ["f.json"]
        assert read_json(root / "f.json", SCHEMA) == {"n": 2}

    def test_THEN_owner_only_from_root_down(self, root: Path) -> None:
        write_json(root / "a" / "b" / "f.json", {}, SCHEMA, root=root)

        for directory in (root, root / "a", root / "a" / "b"):
            assert stat.S_IMODE(directory.stat().st_mode) == 0o700
        assert stat.S_IMODE((root / "a" / "b" / "f.json").stat().st_mode) == 0o600
