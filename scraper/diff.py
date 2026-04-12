"""
Compare a freshly parsed grain record against the current DB state.

Usage:
    from scraper.diff import diff_grain
    grain_diff = diff_grain("CWRS", parsed_record)
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.db import supabase  # noqa: E402

# Grain-level scalar fields to compare (excludes source_url, last_scraped —
# these change on every scrape and are not meaningful diff signals).
_GRAIN_SCALAR_FIELDS = [
    "grain_name",
    "kind",
    "region",
    "use_class",
    "colour_modifier",
    "size_modifier",
    "effective_crop_year",
    "coverage_status",
    "fallthrough_label",
]

# Grain-level complex fields compared as whole values.
_GRAIN_COMPLEX_FIELDS = [
    "grades",
    "grade_floor_rules",
    "variety_tracks",
    "footnotes",
]

# Factor-level scalar fields to compare.
_FACTOR_SCALAR_FIELDS = [
    "factor_label",
    "unit",
    "unit_alt",
    "threshold_direction",
    "is_aggregate",
    "aggregates",
    "footnote_ref",
    "fallthrough",
]


@dataclass
class FieldChange:
    field: str
    old_value: Any
    new_value: Any


@dataclass
class ThresholdChange:
    grade: str
    old: dict | None  # None if this grade did not exist before
    new: dict | None  # None if this grade was removed


@dataclass
class FactorDiff:
    factor_id: str
    factor_label: str
    group_id: str
    status: str  # "added" | "removed" | "changed"
    field_changes: list[FieldChange] = field(default_factory=list)
    threshold_changes: list[ThresholdChange] = field(default_factory=list)


@dataclass
class GrainDiff:
    grain_id: str
    has_changes: bool
    is_new: bool = False  # True if grain does not yet exist in DB
    grain_field_changes: list[FieldChange] = field(default_factory=list)
    factor_diffs: list[FactorDiff] = field(default_factory=list)


def _fetch_db_record(grain_id: str) -> dict | None:
    """Reconstruct a full grain record from the DB as a plain dict."""
    grain_result = (
        supabase.table("grain_classes")
        .select("*")
        .eq("grain_id", grain_id.upper())
        .maybe_single()
        .execute()
    )
    if not grain_result.data:
        return None

    grain = grain_result.data

    groups_result = (
        supabase.table("factor_groups")
        .select("*")
        .eq("grain_class_id", grain["id"])
        .order("sort_order")
        .execute()
    )
    groups = groups_result.data

    factors_by_group: dict[str, list] = {g["id"]: [] for g in groups}
    if groups:
        factors_result = (
            supabase.table("factors")
            .select("*")
            .in_("factor_group_id", [g["id"] for g in groups])
            .order("sort_order")
            .execute()
        )
        for f in factors_result.data:
            factors_by_group[f["factor_group_id"]].append(f)

    return {
        **grain,
        "factor_groups": [
            {
                **g,
                "factors": factors_by_group[g["id"]],
            }
            for g in groups
        ],
    }


def _diff_factors(
    parsed_groups: list[dict],
    db_groups: list[dict],
) -> list[FactorDiff]:
    """Compare factor groups and factors between parsed and DB state."""
    diffs: list[FactorDiff] = []

    # Index DB factors by (group_id, factor_id) for O(1) lookup.
    db_factor_index: dict[tuple[str, str], dict] = {}
    for group in db_groups:
        for f in group["factors"]:
            db_factor_index[(group["group_id"], f["factor_id"])] = f

    # Track which DB factors we've seen (to detect removals).
    seen: set[tuple[str, str]] = set()

    for group in parsed_groups:
        group_id = group["group_id"]
        for factor in group["factors"]:
            key = (group_id, factor["factor_id"])
            seen.add(key)
            db_factor = db_factor_index.get(key)

            if db_factor is None:
                diffs.append(
                    FactorDiff(
                        factor_id=factor["factor_id"],
                        factor_label=factor["factor_label"],
                        group_id=group_id,
                        status="added",
                    )
                )
                continue

            factor_diff = FactorDiff(
                factor_id=factor["factor_id"],
                factor_label=factor["factor_label"],
                group_id=group_id,
                status="changed",
            )

            # Scalar field changes
            for f in _FACTOR_SCALAR_FIELDS:
                old_val = db_factor.get(f)
                new_val = factor.get(f)
                if old_val != new_val:
                    factor_diff.field_changes.append(
                        FieldChange(field=f, old_value=old_val, new_value=new_val)
                    )

            # Threshold changes
            old_thresholds: dict = db_factor.get("thresholds") or {}
            new_thresholds: dict = factor.get("thresholds") or {}
            all_grades = set(old_thresholds) | set(new_thresholds)
            for grade in sorted(all_grades):
                old_t = old_thresholds.get(grade)
                new_t = new_thresholds.get(grade)
                if old_t != new_t:
                    factor_diff.threshold_changes.append(
                        ThresholdChange(grade=grade, old=old_t, new=new_t)
                    )

            if factor_diff.field_changes or factor_diff.threshold_changes:
                diffs.append(factor_diff)

    # Removals: DB factors not seen in parsed output
    for (group_id, factor_id), db_factor in db_factor_index.items():
        if (group_id, factor_id) not in seen:
            diffs.append(
                FactorDiff(
                    factor_id=factor_id,
                    factor_label=db_factor["factor_label"],
                    group_id=group_id,
                    status="removed",
                )
            )

    return diffs


def diff_grain(grain_id: str, parsed: dict) -> GrainDiff:
    """Compare a freshly parsed grain record against the current DB state.

    Returns a GrainDiff describing all changes. If the grain does not yet
    exist in the DB, returns a GrainDiff with is_new=True and has_changes=True.
    """
    db_record = _fetch_db_record(grain_id)

    if db_record is None:
        return GrainDiff(grain_id=grain_id, has_changes=True, is_new=True)

    result = GrainDiff(grain_id=grain_id, has_changes=False)

    # Grain-level scalar fields
    for f in _GRAIN_SCALAR_FIELDS:
        old_val = db_record.get(f)
        new_val = parsed.get(f)
        if old_val != new_val:
            result.grain_field_changes.append(
                FieldChange(field=f, old_value=old_val, new_value=new_val)
            )

    # Grain-level complex fields
    for f in _GRAIN_COMPLEX_FIELDS:
        old_val = db_record.get(f)
        new_val = parsed.get(f)
        if old_val != new_val:
            result.grain_field_changes.append(
                FieldChange(field=f, old_value=old_val, new_value=new_val)
            )

    # Factors
    result.factor_diffs = _diff_factors(
        parsed.get("factor_groups", []),
        db_record.get("factor_groups", []),
    )

    result.has_changes = bool(result.grain_field_changes or result.factor_diffs)
    return result
