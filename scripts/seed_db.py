#!/usr/bin/env python3
"""
Seed the Grading Factors database with initial grain data.

Usage (from project root):
    python scripts/seed_db.py

Reads data/seed/v1_initial.json, validates every record against
data/schema/grain_record.json, then writes to Supabase in dependency order:
  grain_classes -> factor_groups -> factors

Re-runnable: existing factor_groups (and their factors, via CASCADE) are
deleted and reinserted for each grain processed. grain_classes rows are
upserted on grain_id.
"""
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from api.db import supabase  # noqa: E402 — path must be set first

SEED_FILE = ROOT / "data" / "seed" / "v1_initial.json"
SCHEMA_FILE = ROOT / "data" / "schema" / "grain_record.json"


def load_and_validate() -> list[dict]:
    with open(SCHEMA_FILE) as f:
        schema = json.load(f)

    with open(SEED_FILE) as f:
        records = json.load(f)

    if not isinstance(records, list):
        print("ERROR: v1_initial.json must be a JSON array.")
        sys.exit(1)

    if not records:
        print(
            "ERROR: v1_initial.json is empty.\n"
            "Populate it with verified grain records before running this script."
        )
        sys.exit(1)

    print(f"Validating {len(records)} record(s)...")

    errors = []
    for i, record in enumerate(records):
        grain_id = record.get("grain_id", f"record[{i}]")
        try:
            jsonschema.validate(instance=record, schema=schema)
        except jsonschema.ValidationError as e:
            path = " > ".join(str(p) for p in e.absolute_path) or "(root)"
            errors.append(f"  {grain_id}: {e.message}  [path: {path}]")

    if errors:
        print("Validation failed:\n" + "\n".join(errors))
        sys.exit(1)

    print(f"All {len(records)} record(s) valid.\n")
    return records


def seed_grain(record: dict) -> None:
    grain_id = record["grain_id"]

    # --- grain_classes (upsert on grain_id) ---
    grain_row = {
        "grain_id": grain_id,
        "grain_name": record["grain_name"],
        "kind": record["kind"],
        "region": record.get("region"),
        "use_class": record.get("use_class"),
        "colour_modifier": record["colour_modifier"],
        "size_modifier": record["size_modifier"],
        "source_url": record["source_url"],
        "effective_crop_year": record["effective_crop_year"],
        "last_scraped": record["last_scraped"],
        "coverage_status": record["coverage_status"],
        "fallthrough_label": record.get("fallthrough_label"),
        "grade_floor_rules": record.get("grade_floor_rules", []),
        "grades": record["grades"],
        "variety_tracks": record.get("variety_tracks"),
        "footnotes": record.get("footnotes"),
    }

    result = (
        supabase.table("grain_classes")
        .upsert(grain_row, on_conflict="grain_id")
        .execute()
    )
    grain_class_id = result.data[0]["id"]

    # --- factor_groups + factors ---
    # Delete existing groups for this grain (CASCADE removes their factors too).
    supabase.table("factor_groups").delete().eq("grain_class_id", grain_class_id).execute()

    total_factors = 0
    for group_order, group in enumerate(record["factor_groups"]):
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
        print(
            f"  {grain_id} / {group['group_id']}: "
            f"{len(factor_rows)} factor(s) inserted"
        )

    print(f"  {grain_id}: done ({total_factors} total factor(s))")


def main() -> None:
    print("=== Grading Factors DB Seed ===\n")
    records = load_and_validate()
    print(f"Seeding {len(records)} grain(s)...\n")

    for record in records:
        seed_grain(record)

    print(f"\nDone. {len(records)} grain(s) seeded successfully.")


if __name__ == "__main__":
    main()
