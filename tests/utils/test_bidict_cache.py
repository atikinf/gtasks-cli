from pathlib import Path

import pytest

from gtasks.utils.bidict_cache import BidictCache

# @pytest.fixture
# def mock_bidict_and_path(tmp_path: Path):
#     """
#     Fixture that returns a tuple of a mock bidict and a cache path,
#     suitable for initializing BidictCache instances in tests.
#     """
#     mock_bi: bidict[str, str] = bidict()
#     cache_path: Path = tmp_path / "test_cache.json"
#     return mock_bi, cache_path


class TestBidictCacheInit:
    def test_init_GIVEN_valid_path_THEN_success(self, tmp_path: Path):
        bdc = BidictCache(tmp_path / "test.json")
        assert len(bdc) == 0


class TestBidictGetForwardBackward:
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


class TestBidictSave:
    def test_save_GIVEN_valid_path_THEN_success(self):
        pass
