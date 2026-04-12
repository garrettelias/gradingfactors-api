"""
Write an approved diff to the DB and create a changelog entry.

Note: this file is named import_diff.py rather than import.py because
`import` is a Python reserved word and a file named import.py cannot be
imported as a module without workarounds.
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.db import supabase  # noqa: E402
from scraper.diff import GrainDiff  # noqa: E402


def import_changes(
    diff: GrainDiff,
    parsed: dict,
    *,
    summary: str,
    crop_year: str,
    effective_date: date,
) -> None:
    """Write an approved diff to the DB and create a changelog entry.

    Args:
        diff:           The GrainDiff produced by diff_grain().
        parsed:         The full parsed grain record dict.
        summary:        Human-readable description of the changes (for changelog).
        crop_year:      e.g. "2025/26"
        effective_date: Date the changes take effect.
    """
    if not diff.has_changes:
        print(f"[{diff.grain_id}] No changes to import.")
        return

    grain_id = diff.grain_id
    print(f"[{grain_id}] Importing changes...")

    # --- grain_classes (upsert on grain_id) ---
    grain_row = {
        "grain_id": parsed["grain_id"],
        "grain_name": parsed["grain_name"],
        "kind": parsed["kind"],
        "region": parsed.get("region"),
        "use_class": parsed.get("use_class"),
        "colour_modifier": parsed["colour_modifier"],
        "size_modifier": parsed["size_modifier"],
        "source_url": parsed["source_url"],
        "effective_crop_year": parsed["effective_crop_year"],
        "last_scraped": parsed["last_scraped"],
        "coverage_status": parsed["coverage_status"],
        "fallthrough_label": parsed.get("fallthrough_label"),
        "grade_floor_rules": parsed.get("grade_floor_rules", []),
        "grades": parsed["grades"],
        "variety_tracks": parsed.get("variety_tracks"),
        "footnotes": parsed.get("footnotes"),
    }

    result = (
        supabase.table("grain_classes")
        .upsert(grain_row, on_conflict="grain_id")
        .execute()
    )
    grain_class_id = result.data[0]["id"]

    # --- factor_groups + factors (delete existing, reinsert) ---
    supabase.table("factor_groups").delete().eq("grain_class_id", grain_class_id).execute()

    total_factors = 0
    for group_order, group in enumerate(parsed["factor_groups"]):
        group_result = (
            supabase.table("factor_groups")
            .insert({
                "grain_class_id": grain_class_id,
                "group_id": group["group_id"],
                "group_label": group["group_label"],
                "sort_order": group_order,
            })
            .execute()
        )
        factor_group_id = group_result.data[0]["id"]

        factor_rows = [
            {
                "factor_group_id": factor_group_id,
                "factor_id": factor["factor_id"],
                "factor_label": factor["factor_label"],
                "unit": factor.get("unit"),
                "unit_alt": factor.get("unit_alt"),
                "threshold_direction": factor.get("threshold_direction"),
                "is_aggregate": factor["is_aggregate"],
                "aggregates": factor.get("aggregates"),
                "footnote_ref": factor.get("footnote_ref"),
                "thresholds": factor["thresholds"],
                "fallthrough": factor.get("fallthrough"),
                "sort_order": factor_order,
            }
            for factor_order, factor in enumerate(group["factors"])
        ]

        if factor_rows:
            supabase.table("factors").insert(factor_rows).execute()

        total_factors += len(factor_rows)

    print(f"[{grain_id}] {total_factors} factor(s) written.")

    # --- changelog entry ---
    supabase.table("changelog").insert({
        "crop_year": crop_year,
        "effective_date": effective_date.isoformat(),
        "grain_ids_affected": [grain_id],
        "summary": summary,
    }).execute()

    print(f"[{grain_id}] Changelog entry created.")
