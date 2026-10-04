import pytest

from gtasks.cli.title_matching import complete_titles, match_titles, normalize

MILK = {"id": "t1", "title": "Buy milk"}
OAT = {"id": "t2", "title": "Buy oat milk"}
DENTIST = {"id": "t3", "title": "Call dentist"}
COFFEE = {"id": "t4", "title": "Coffee beans"}
TASKS = [MILK, OAT, DENTIST, COFFEE]


class TestNormalize:
    @pytest.mark.parametrize(
        "text", ["Buy milk", "buy MILK", "  Buy   milk ", "BUY\tmilk"], ids=str
    )
    def test_normalize_GIVEN_case_and_spacing_variants_THEN_equal(self, text: str) -> None:
        assert normalize(text) == "buy milk"


class TestMatchTitles:
    def test_GIVEN_exact_title_THEN_exact_even_if_others_contain_it(self) -> None:
        result = match_titles(TASKS, "buy milk")

        assert result.kind == "exact"
        assert result.matches == [MILK]  # "Buy oat milk" also contains "milk" but loses

    def test_GIVEN_duplicate_exact_titles_THEN_all_returned(self) -> None:
        dupe = {"id": "t9", "title": "Buy milk"}

        assert match_titles([MILK, dupe], "Buy milk").matches == [MILK, dupe]

    def test_GIVEN_fragment_in_one_title_THEN_partial_single(self) -> None:
        result = match_titles(TASKS, "dent")

        assert (result.kind, result.matches) == ("partial", [DENTIST])

    def test_GIVEN_fragment_in_several_titles_THEN_partial_all(self) -> None:
        result = match_titles(TASKS, "MILK")

        assert (result.kind, result.matches) == ("partial", [MILK, OAT])

    def test_GIVEN_typo_THEN_none_with_suggestions(self) -> None:
        result = match_titles(TASKS, "Buy mlik")

        assert result.kind == "none"
        assert result.matches == []
        assert result.suggestions[0] == "Buy milk"

    def test_GIVEN_nothing_close_THEN_none_without_suggestions(self) -> None:
        assert match_titles(TASKS, "zzzzzz") == match_titles([], "zzzzzz")
        assert match_titles(TASKS, "zzzzzz").suggestions == []

    def test_GIVEN_items_without_id_THEN_skipped(self) -> None:
        assert match_titles([{"title": "Buy milk"}, MILK], "Buy milk").matches == [MILK]

    def test_GIVEN_blank_query_THEN_matches_nothing(self) -> None:
        assert match_titles(TASKS, "   ").kind == "none"


class TestCompleteTitles:
    def test_GIVEN_prefix_any_case_THEN_titles_starting_with_it(self) -> None:
        titles = [t["title"] for t in TASKS]

        assert complete_titles(titles, "bu") == ["Buy milk", "Buy oat milk"]

    def test_GIVEN_mid_title_fragment_THEN_not_completed(self) -> None:
        assert complete_titles(["Buy milk"], "milk") == []

    def test_GIVEN_empty_prefix_THEN_every_title_once(self) -> None:
        assert complete_titles(["A", "B", "A", ""], "") == ["A", "B"]
