from pathlib import Path

import pytest

from gtasks.utils.bidict_cache import BidictCache


class TestInitBidictCache:
    # invalid path logic tested in the
    def test_init_GIVEN_valid_path_THEN_success(self, tmp_path: Path):
        bdc = BidictCache(tmp_path / "test.json")
        assert len(bdc) == 0


class TestGetForwardBackwardBidictCache:
    @pytest.fixture
    def bdc(self, tmp_path: Path) -> BidictCache[str, str]:
        items: dict[str, str] = {"a": "hello", "b": "goodbye"}
        bdc: BidictCache[str, str] = BidictCache(tmp_path / "test.json")
        bdc.update_from_items(items)
        return bdc

    def test_get_forward_GIVEN_is_present_THEN_success(
        self, bdc: BidictCache[str, str]
    ):
        assert bdc.get_forward("a") == "hello"

    def test_get_forward_GIVEN_not_present_THEN_failure(
        self, bdc: BidictCache[str, str]
    ):
        with pytest.raises(KeyError):
            bdc.get_forward("c")

    def test_get_backward_GIVEN_is_present_THEN_success(
        self, bdc: BidictCache[str, str]
    ):
        assert bdc.get_backward("hello") == "a"

    def test_get_backward_GIVEN_not_present_THEN_failure(
        self, bdc: BidictCache[str, str]
    ):
        with pytest.raises(KeyError):
            bdc.get_backward("toodaloo")


class TestSaveBidictCache:
    def test_save_GIVEN_valid_path_THEN_success(self, tmp_path: Path):
        cache_path: Path = tmp_path / "subdir" / "test_cache.json"
        bdc: BidictCache[str, str] = BidictCache(cache_path)
        bdc.update_from_items({"key1": "value1", "key2": "value2"})

        bdc.save()

        assert cache_path.exists()
        with cache_path.open("r", encoding="utf-8") as f:
            saved_data = f.read()
        assert '"key1": "value1"' in saved_data
        assert '"key2": "value2"' in saved_data


class TestLoadBidictCache:
    def test_load_GIVEN_valid_path_THEN_success(self, tmp_path: Path):
        cache_path: Path = tmp_path / "subdir" / "test_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text('{"key1": "value1", "key2": "value2"}', encoding="utf-8")

        bdc: BidictCache[str, str] = BidictCache(cache_path)

        assert len(bdc) == 2
        assert bdc.get_forward("key1") == "value1"
        assert bdc.get_forward("key2") == "value2"
        assert bdc.get_backward("value1") == "key1"
        assert bdc.get_backward("value2") == "key2"

    def test_load_GIVEN_corrupted_json_THEN_raises_valueerror(self, tmp_path: Path):
        cache_path: Path = tmp_path / "subdir" / "test_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text("{invalid json content", encoding="utf-8")

        with pytest.raises(ValueError, match=BidictCache.ERR_PARSE_JSON):
            BidictCache(cache_path)

    def test_load_GIVEN_duplicate_values_THEN_raises_valueerror(self, tmp_path: Path):
        cache_path: Path = tmp_path / "subdir" / "test_cache.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            '{"key1": "same_value", "key2": "same_value"}', encoding="utf-8"
        )

        with pytest.raises(ValueError, match=BidictCache.ERR_DUPLICATE_KEY_VALUE):
            BidictCache(cache_path)


class TestClearBidictCache:
    def test_clear_GIVEN_populated_cache_THEN_empties_and_saves(self, tmp_path: Path):
        cache_path: Path = tmp_path / "subdir" / "test_cache.json"
        bdc: BidictCache[str, str] = BidictCache(cache_path)
        bdc.update_from_items({"key1": "value1", "key2": "value2"})
        bdc.save()
        assert len(bdc) == 2

        bdc.clear()

        assert len(bdc) == 0
        assert cache_path.exists()
        assert cache_path.read_text(encoding="utf-8") == "{}"
