"""
Pytest tests for scraper/parse.py.

All tests load HTML from saved fixture files in tests/fixtures/ — no network
calls and no database access. Tests are organised as:

  TestCWRSParser      — deep structural assertions against the CWRS reference
  TestGrainSmoke      — parametrized smoke tests across all 8 remaining grains
  TestParserEdgeCases — targeted assertions for known parser edge cases
"""
from pathlib import Path

import pytest

from scraper.parse import GRAIN_CONFIG, parse

FIXTURES_DIR = Path(__file__).parent / "fixtures"

VALID_VALUE_TYPES = frozenset(
    {"numeric", "no_limit", "qualitative", "qualitative_judgment", "not_applicable"}
)

# All grain IDs except CWRS (which has its own deep test class).
SMOKE_GRAIN_IDS = [gid for gid in GRAIN_CONFIG if gid != "CWRS"]


def _load_fixture(grain_id: str) -> str:
    path = FIXTURES_DIR / f"{grain_id.lower()}_page.html"
    return path.read_text(encoding="utf-8")


def _find_factor(record: dict, factor_id: str) -> dict | None:
    """Return the first factor matching factor_id across all groups, or None."""
    for fg in record["factor_groups"]:
        for f in fg["factors"]:
            if f["factor_id"] == factor_id:
                return f
    return None


# ---------------------------------------------------------------------------
# CWRS deep structural test
# ---------------------------------------------------------------------------

class TestCWRSParser:
    """Deep assertions against the CWRS reference grain.

    CWRS is the canonical reference implementation for the parser (per the
    project brief). If any of these tests fail, the parser has regressed on
    a well-understood, manually verified case.
    """

    @pytest.fixture(scope="class")
    def cwrs(self):
        return parse("CWRS", _load_fixture("CWRS"))

    def test_top_level_keys_present(self, cwrs):
        expected = {
            "grain_id", "grain_name", "kind", "region", "use_class",
            "variety_tracks", "colour_modifier", "size_modifier", "source_url",
            "effective_crop_year", "last_scraped", "coverage_status",
            "fallthrough_label", "grade_floor_rules", "grades",
            "factor_groups", "footnotes",
        }
        assert expected.issubset(cwrs.keys())

    def test_schema_version_absent_from_parsed_output(self, cwrs):
        # schema_version belongs to the API response layer, not the parser.
        assert "schema_version" not in cwrs

    def test_grain_metadata(self, cwrs):
        assert cwrs["grain_id"] == "CWRS"
        assert cwrs["grain_name"] == "Canada Western Red Spring"
        assert cwrs["kind"] == "wheat"
        assert cwrs["region"] == "western"
        assert cwrs["use_class"] is None
        assert cwrs["variety_tracks"] is None
        assert cwrs["colour_modifier"] is False
        assert cwrs["size_modifier"] is False

    def test_grades(self, cwrs):
        assert cwrs["grades"] == ["No. 1 CWRS", "No. 2 CWRS", "No. 3 CWRS", "CW Feed"]

    def test_factor_group_ids(self, cwrs):
        ids = [fg["group_id"] for fg in cwrs["factor_groups"]]
        assert ids == ["standard_of_quality", "foreign_material", "grading_factors"]

    def test_floor_rules(self, cwrs):
        rules = cwrs["grade_floor_rules"]
        assert len(rules) >= 1
        mildew = rules[0]
        assert mildew["account"] == "mildew"
        assert mildew["floor_grade"] == "No. 3 CWRS"

    def test_footnotes(self, cwrs):
        fn = cwrs["footnotes"]
        assert isinstance(fn, dict)
        assert "fnt1" in fn
        assert "fnt2" in fn

    def test_ergot_factor(self, cwrs):
        ergot = _find_factor(cwrs, "ergot")
        assert ergot is not None, "ergot factor not found"
        assert ergot["unit"] == "%"
        assert ergot["threshold_direction"] == "maximum"
        t1 = ergot["thresholds"]["No. 1 CWRS"]
        assert t1["value_type"] == "numeric"
        assert t1["value"] == pytest.approx(0.04)
        assert isinstance(ergot["fallthrough"], str)

    def test_dual_unit_factor(self, cwrs):
        tw = _find_factor(cwrs, "minimum_test_weight")
        assert tw is not None, "minimum_test_weight factor not found"
        assert tw["unit"] == "kg/hL"
        assert tw["unit_alt"] == "g/0.5 L"
        assert tw["threshold_direction"] == "minimum"
        assert tw["thresholds"]["No. 1 CWRS"]["value_alt"] is not None

    def test_no_empty_string_fallthroughs(self, cwrs):
        for fg in cwrs["factor_groups"]:
            for f in fg["factors"]:
                assert f["fallthrough"] != "", (
                    f"Factor '{f['factor_id']}' has an empty-string fallthrough"
                )

    def test_all_threshold_value_types_valid(self, cwrs):
        for fg in cwrs["factor_groups"]:
            for f in fg["factors"]:
                for grade, t in f["thresholds"].items():
                    assert t["value_type"] in VALID_VALUE_TYPES, (
                        f"'{f['factor_id']}' / '{grade}': "
                        f"unexpected value_type {t['value_type']!r}"
                    )


# ---------------------------------------------------------------------------
# Smoke tests — parametrized across all remaining grains
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("grain_id", SMOKE_GRAIN_IDS)
class TestGrainSmoke:
    """Basic structural correctness for every grain other than CWRS."""

    @pytest.fixture
    def record(self, grain_id):
        return parse(grain_id, _load_fixture(grain_id))

    def test_grain_id_matches(self, record, grain_id):
        assert record["grain_id"] == grain_id

    def test_grades_non_empty(self, record, grain_id):
        assert isinstance(record["grades"], list)
        assert len(record["grades"]) > 0, f"[{grain_id}] grades list is empty"

    def test_factor_groups_non_empty(self, record, grain_id):
        assert len(record["factor_groups"]) > 0, (
            f"[{grain_id}] factor_groups is empty"
        )
        for fg in record["factor_groups"]:
            assert isinstance(fg["factors"], list), (
                f"[{grain_id}] group '{fg['group_id']}' has no factors list"
            )

    def test_all_threshold_value_types_valid(self, record, grain_id):
        for fg in record["factor_groups"]:
            for f in fg["factors"]:
                for grade, t in f["thresholds"].items():
                    assert t["value_type"] in VALID_VALUE_TYPES, (
                        f"[{grain_id}] '{f['factor_id']}' / '{grade}': "
                        f"unexpected value_type {t['value_type']!r}"
                    )

    def test_no_empty_string_fallthroughs(self, record, grain_id):
        for fg in record["factor_groups"]:
            for f in fg["factors"]:
                assert f["fallthrough"] != "", (
                    f"[{grain_id}] factor '{f['factor_id']}' has an empty-string fallthrough"
                )


# ---------------------------------------------------------------------------
# Targeted edge-case assertions
# ---------------------------------------------------------------------------

class TestParserEdgeCases:
    def test_barley_gp_cw_variety_tracks(self):
        record = parse("BARLEY_GP_CW", _load_fixture("BARLEY_GP_CW"))
        tracks = record["variety_tracks"]
        assert isinstance(tracks, list), "BARLEY_GP_CW should have variety_tracks"
        track_ids = {t["track_id"] for t in tracks}
        assert track_ids == {"covered", "hulless"}
        for t in tracks:
            assert len(t["grades"]) > 0

    def test_barley_gp_ce_variety_tracks(self):
        record = parse("BARLEY_GP_CE", _load_fixture("BARLEY_GP_CE"))
        tracks = record["variety_tracks"]
        assert isinstance(tracks, list), "BARLEY_GP_CE should have variety_tracks"
        track_ids = {t["track_id"] for t in tracks}
        assert track_ids == {"covered", "hulless"}

    def test_canola_stones_fallthrough_branching(self):
        record = parse("CANOLA", _load_fixture("CANOLA"))
        stones = _find_factor(record, "stones")
        assert stones is not None, "CANOLA stones factor not found"
        ft = stones["fallthrough"]
        assert isinstance(ft, list), "CANOLA stones fallthrough should be a list"
        assert len(ft) == 3
        regions = {c["region"] for c in ft}
        assert "west" in regions
        assert "east" in regions

    def test_corn_ce_variety_fallthrough_null(self):
        """Regression test: missing </tr> in CORN_CE HTML previously caused the
        Other classes row's fallthrough to bleed into the Variety row."""
        record = parse("CORN_CE", _load_fixture("CORN_CE"))
        variety = _find_factor(record, "variety")
        assert variety is not None, "CORN_CE variety factor not found"
        assert variety["fallthrough"] is None

    def test_corn_ce_stones_footnote_ref(self):
        """CORN_CE stones carries footnote anchor fnt2.

        The CGC page displays 'Footnote 1' for this row (the display counter
        resets per table), but the actual HTML anchor ID is fnt2 because CW and
        CE tables coexist on the same page and IDs must be globally unique.
        fnt2 is the correct and accepted value.
        """
        record = parse("CORN_CE", _load_fixture("CORN_CE"))
        stones = _find_factor(record, "stones")
        assert stones is not None, "CORN_CE stones factor not found"
        assert stones["footnote_ref"] == "fnt2"

    def test_cwad_has_qualitative_judgment_threshold(self):
        record = parse("CWAD", _load_fixture("CWAD"))
        found = any(
            t["value_type"] == "qualitative_judgment"
            for fg in record["factor_groups"]
            for f in fg["factors"]
            for t in f["thresholds"].values()
        )
        assert found, "Expected at least one qualitative_judgment threshold in CWAD"
