"""
Grading Factors scraper CLI.

Usage (from project root):

    python -m scraper <GRAIN_ID>            # fetch → parse → diff → report (read-only)
    python -m scraper <GRAIN_ID> --import   # above + prompt to confirm → import if yes
    python -m scraper --all                 # read-only run for all 9 grains

Examples:
    python -m scraper CWRS
    python -m scraper CANOLA --import
    python -m scraper --all

The fetched HTML is saved to tests/fixtures/<grain_id>_page.html on first
fetch so it can be used for offline parser testing in Phase 6.
"""
import argparse
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv()

from scraper.diff import diff_grain  # noqa: E402
from scraper.fetch import fetch  # noqa: E402
from scraper.import_diff import import_changes  # noqa: E402
from scraper.parse import GRAIN_CONFIG, parse  # noqa: E402
from scraper.report import print_report  # noqa: E402

CGC_BASE = os.environ.get(
    "CGC_BASE_URL",
    "https://www.grainscanada.gc.ca/en/grain-quality/official-grain-grading-guide",
)
FIXTURES_DIR = ROOT / "tests" / "fixtures"


def _fetch_and_save(grain_id: str) -> str:
    """Fetch the CGC page for grain_id and save HTML to the fixtures directory."""
    cfg = GRAIN_CONFIG[grain_id]
    url = CGC_BASE + cfg["url"]
    print(f"[{grain_id}] Fetching {url} ...")
    html = fetch(url)

    fixture_path = FIXTURES_DIR / f"{grain_id.lower()}_page.html"
    if not fixture_path.exists():
        FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(html, encoding="utf-8")
        print(f"[{grain_id}] Saved fixture to {fixture_path.relative_to(ROOT)}")

    return html


def _run_grain(grain_id: str, do_import: bool) -> bool:
    """Fetch, parse, diff, and report for one grain. Returns True if changes found."""
    grain_id = grain_id.upper()

    if grain_id not in GRAIN_CONFIG:
        print(f"ERROR: Unknown grain_id '{grain_id}'. Valid IDs: {', '.join(GRAIN_CONFIG)}")
        return False

    try:
        html = _fetch_and_save(grain_id)
    except RuntimeError as e:
        print(f"[{grain_id}] Fetch error: {e}")
        return False

    print(f"[{grain_id}] Parsing ...")
    record = parse(grain_id, html)

    print(f"[{grain_id}] Diffing against DB ...")
    grain_diff = diff_grain(grain_id, record)

    print_report(grain_diff)

    if not grain_diff.has_changes:
        return False

    if not do_import:
        return True

    # --- Import flow ---
    confirm = input(f"Import changes for {grain_id}? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Import cancelled.")
        return True

    summary = input("Enter changelog summary (one line): ").strip()
    if not summary:
        print("Import cancelled: summary is required.")
        return True

    date_str = input(f"Effective date (YYYY-MM-DD) [{date.today()}]: ").strip()
    try:
        effective_date = date.fromisoformat(date_str) if date_str else date.today()
    except ValueError:
        print(f"Invalid date '{date_str}'. Import cancelled.")
        return True

    crop_year = input(f"Crop year [2025/26]: ").strip() or "2025/26"

    import_changes(
        grain_diff,
        record,
        summary=summary,
        crop_year=crop_year,
        effective_date=effective_date,
    )
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Grading Factors scraper: fetch → parse → diff → (optionally) import."
    )
    parser.add_argument(
        "grain_id",
        nargs="?",
        help="Grain ID to process (e.g. CWRS). Omit when using --all.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process all configured grain IDs (read-only; --import is ignored).",
    )
    parser.add_argument(
        "--import",
        dest="do_import",
        action="store_true",
        help="Prompt to import changes after showing diff report.",
    )
    args = parser.parse_args()

    if args.all:
        for gid in GRAIN_CONFIG:
            _run_grain(gid, do_import=False)
        return

    if not args.grain_id:
        parser.print_help()
        sys.exit(1)

    _run_grain(args.grain_id, do_import=args.do_import)


if __name__ == "__main__":
    main()
