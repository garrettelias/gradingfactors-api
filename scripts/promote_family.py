#!/usr/bin/env python3
"""
Promote reviewed pending-review grain records to seed data + Supabase.

Usage (from project root):
    python scripts/promote_family.py GRAIN_ID [GRAIN_ID ...]

For each grain_id whose file exists in data/pending_review/grains/:
  1. Re-validates the record against data/schema/grain_record.json.
  2. Copies the file into data/seed/grains/<GRAIN_ID>.json — this becomes the
     new manually-verified baseline for this grain going forward, same status
     as the original v1 grains.
  3. Diffs it against current DB state and writes the change via
     scraper.import_diff.import_changes(), which also creates a changelog
     entry — same one-entry-per-grain_id granularity as the steady-state
     weekly-update flow. No new changelog logic is needed here.

grain_ids with no matching file in data/pending_review/grains/ are skipped
with a message; they do not abort the rest of the batch.

Generic across grain families by design — this is not wheat-specific, and is
meant to be reused for every future family (Barley, Oilseed, ...) once its
pending-review files have been approved.

Prompts once per run (not once per grain) for crop_year and effective_date,
and once for a summary string shared across every grain in the batch — for a
same-day bulk promotion of many grains, writing one summary per grain is more
friction than it's worth; if a specific grain in the batch needs its own
distinct changelog wording, promote it separately with its own summary.

This script does not touch gradingfactors-api-project-brief-v2.md. After a
successful run it prints a reminder that the brief's grain count and V1 Grain
Classes table need a manual update — that edit is a deliberate follow-up step,
not something this script should do on its own.
"""
import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import jsonschema  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from scraper.diff import diff_grain  # noqa: E402
from scraper.import_diff import import_changes  # noqa: E402

PENDING_DIR = ROOT / "data" / "pending_review" / "grains"
SEED_DIR = ROOT / "data" / "seed" / "grains"
SCHEMA_FILE = ROOT / "data" / "schema" / "grain_record.json"


def _load_schema() -> dict:
    return json.loads(SCHEMA_FILE.read_text())


def promote_grain(
    grain_id: str,
    schema: dict,
    *,
    summary: str,
    crop_year: str,
    effective_date: date,
) -> bool:
    """Promote one grain from pending_review to seed + DB.

    Returns True if the grain was promoted successfully, False if it was
    skipped (no pending file, or schema validation failed) or if the DB write
    failed after the seed file was already copied.
    """
    grain_id = grain_id.upper()
    pending_path = PENDING_DIR / f"{grain_id}.json"

    if not pending_path.is_file():
        print(f"[{grain_id}] SKIPPED: no pending-review file at "
              f"{pending_path.relative_to(ROOT)}")
        return False

    record = json.loads(pending_path.read_text())

    try:
        jsonschema.validate(instance=record, schema=schema)
    except jsonschema.ValidationError as e:
        path = " > ".join(str(p) for p in e.absolute_path) or "(root)"
        print(f"[{grain_id}] SCHEMA VALIDATION FAILED: {e.message} [path: {path}]")
        print(f"[{grain_id}] Not promoted — fix the pending-review file and retry.")
        return False

    seed_path = SEED_DIR / f"{grain_id}.json"
    shutil.copyfile(pending_path, seed_path)
    print(f"[{grain_id}] Copied to {seed_path.relative_to(ROOT)}")

    try:
        grain_diff = diff_grain(grain_id, record)
        import_changes(
            grain_diff,
            record,
            summary=summary,
            crop_year=crop_year,
            effective_date=effective_date,
        )
    except Exception as e:
        print(f"[{grain_id}] DB WRITE FAILED: {e}")
        print(f"[{grain_id}] NOTE: {seed_path.relative_to(ROOT)} was already "
              f"written — the seed file and DB are now out of sync for this "
              f"grain until this is retried or reconciled by hand.")
        return False

    print(f"[{grain_id}] Promoted successfully.")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Promote reviewed pending-review grain records to seed data + Supabase.",
    )
    parser.add_argument(
        "grain_ids",
        nargs="+",
        help="Grain IDs to promote (e.g. CWHWS CWRW CWSWS ...).",
    )
    args = parser.parse_args()
    grain_ids = [g.upper() for g in args.grain_ids]

    schema = _load_schema()

    print(f"=== Promoting {len(grain_ids)} grain(s): {', '.join(grain_ids)} ===\n")

    crop_year = input("Crop year [2025/26]: ").strip() or "2025/26"

    date_str = input(f"Effective date (YYYY-MM-DD) [{date.today()}]: ").strip()
    try:
        effective_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        print(f"Invalid date '{date_str}'. Aborting.")
        sys.exit(1)

    summary = input("Changelog summary (shared across every grain in this batch): ").strip()
    if not summary:
        print("Aborting: summary is required.")
        sys.exit(1)

    print()
    results: list[tuple[str, bool]] = []
    for grain_id in grain_ids:
        ok = promote_grain(
            grain_id,
            schema,
            summary=summary,
            crop_year=crop_year,
            effective_date=effective_date,
        )
        results.append((grain_id, ok))
        print()

    succeeded = [g for g, ok in results if ok]
    failed = [g for g, ok in results if not ok]

    print(f"=== Done: {len(succeeded)}/{len(results)} promoted successfully ===")
    if failed:
        print(f"Not promoted: {', '.join(failed)}")

    if succeeded:
        print(
            "\nREMINDER (manual follow-up — this script does not do this): "
            "gradingfactors-api-project-brief-v2.md's grain count and V1 Grain "
            "Classes table need to be updated by hand to reflect the newly "
            f"promoted grain(s): {', '.join(succeeded)}."
        )


if __name__ == "__main__":
    main()
