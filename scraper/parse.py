"""
Parse CGC grading guide HTML pages into grain record dicts matching the schema.

Entry point:
    from scraper.parse import parse, GRAIN_CONFIG
    record = parse("CWRS", html_string)

Each grain_id maps to a URL path (relative to CGC_BASE_URL) and a parser
function. All parsers return a dict matching the grain_record.json schema.

HTML structure observations (validated against all v1 pages):
  - Each page has one or more <table> elements with <caption> elements.
  - The first row of each table is the header row (all <th> cells).
  - Header columns: "Grading factor" | grade_1 | ... | grade_N | fallthrough_label
  - Data rows: factor <th> | threshold <td> × N | fallthrough <td>
  - Footnotes appear in a <section class="wb-fnote"> in the last <tr>.
  - Floor rules appear as <p> elements between the <h2> and the first table.
  - CANOLA and BARLEY_GP and CORN pages contain tables for two sub-classes;
    the relevant slice is selected by the grain-specific assembler.
"""
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CGC_BASE = os.environ.get(
    "CGC_BASE_URL",
    "https://www.grainscanada.gc.ca/en/grain-quality/official-grain-grading-guide",
)
EFFECTIVE_CROP_YEAR = "2025/26"


# ---------------------------------------------------------------------------
# Grain configuration
# ---------------------------------------------------------------------------

GRAIN_CONFIG: dict[str, dict] = {
    "CWRS": {
        "url": "/04-wheat/primary-grade-determination/cwrs-wheat.html",
        "grain_name": "Canada Western Red Spring",
        "kind": "wheat",
        "region": "western",
        "use_class": None,
        "colour_modifier": False,
        "size_modifier": False,
        "parser": "wheat",
    },
    "CWAD": {
        "url": "/04-wheat/primary-grade-determination/cwad-wheat.html",
        "grain_name": "Canada Western Amber Durum",
        "kind": "wheat",
        "region": "western",
        "use_class": None,
        "colour_modifier": False,
        "size_modifier": False,
        "parser": "wheat",
    },
    "CPSR": {
        "url": "/04-wheat/primary-grade-determination/cpsr-wheat.html",
        "grain_name": "Canada Prairie Spring Red",
        "kind": "wheat",
        "region": "western",
        "use_class": None,
        "colour_modifier": False,
        "size_modifier": False,
        "parser": "wheat",
    },
    "CANOLA": {
        "url": "/10-canola-rapeseed/primary-export-grade-determination-tables.html",
        "grain_name": "Canola, Canada (CAN)",
        "kind": "oilseed",
        "region": None,
        "use_class": None,
        "colour_modifier": False,
        "size_modifier": False,
        "parser": "canola",
    },
    "BARLEY_GP_CW": {
        "url": "/06-barley/primary-export-grade-determination/general-purpose-barley.html",
        "grain_name": "Barley, Canada Western General Purpose",
        "kind": "cereal",
        "region": "western",
        "use_class": "general_purpose",
        "colour_modifier": False,
        "size_modifier": False,
        "parser": "barley_gp_cw",
    },
    "BARLEY_GP_CE": {
        "url": "/06-barley/primary-export-grade-determination/general-purpose-barley.html",
        "grain_name": "Barley, Canada Eastern General Purpose",
        "kind": "cereal",
        "region": "eastern",
        "use_class": "general_purpose",
        "colour_modifier": False,
        "size_modifier": False,
        "parser": "barley_gp_ce",
    },
    "CORN_CW": {
        "url": "/17-corn/primary-export-grade-determination-tables.html",
        "grain_name": "Corn, Canada Western Yellow, White or Mixed",
        "kind": "cereal",
        "region": "western",
        "use_class": None,
        "colour_modifier": True,
        "size_modifier": False,
        "parser": "corn_cw",
    },
    "CORN_CE": {
        "url": "/17-corn/primary-export-grade-determination-tables.html",
        "grain_name": "Corn, Canada Eastern Yellow, White or Mixed",
        "kind": "cereal",
        "region": "eastern",
        "use_class": None,
        "colour_modifier": True,
        "size_modifier": False,
        "parser": "corn_ce",
    },
    "SOYBEANS": {
        "url": "/20-soybeans/primary-export-grade-determination-tables.html",
        "grain_name": "Soybeans, Canada Yellow, Green, Brown, Black or Mixed",
        "kind": "oilseed",
        "region": None,
        "use_class": None,
        "colour_modifier": True,
        "size_modifier": False,
        "parser": "soybeans",
    },
}


# ---------------------------------------------------------------------------
# Label and unit parsing
# ---------------------------------------------------------------------------

_DUAL_UNIT_RE = re.compile(r"\s*kg/h[Ll]\s*\(g/0\.5\s*[Ll]\)(?:,\s*C[WwEe])?$")
_TOTAL_PCT_RE = re.compile(r"Total\s*%\s*")


def _extract_th_label(th) -> tuple[str, str | None]:
    """Return (clean_label, footnote_ref_or_None) from a factor <th> element."""
    th = th.__copy__()  # work on a copy so we can mutate

    # Extract footnote ref from <sup> before getting text
    footnote_ref = None
    sup = th.find("sup")
    if sup:
        m = re.search(r"(\d+)", sup.get_text())
        if m:
            footnote_ref = f"fnt{m.group(1)}"
        sup.decompose()

    # Join text nodes (handles <br/> inside <th>)
    parts = [s.strip() for s in th.strings if s.strip()]
    raw = " ".join(parts).replace("\xa0", " ").strip()
    return raw, footnote_ref


def _parse_label_and_unit(raw: str) -> tuple[str, str | None, str | None]:
    """Extract (factor_label, unit, unit_alt) from raw th text."""
    raw = raw.replace("\xa0", " ").strip()

    # Dual-unit: e.g. "Minimum test weightkg/hL (g/0.5 L)" or "..., CW"
    if _DUAL_UNIT_RE.search(raw):
        label = _DUAL_UNIT_RE.sub("", raw).strip()
        return label, "kg/hL", "g/0.5 L"

    # Aggregate "Total %" label — % is part of the label, not a unit
    if _TOTAL_PCT_RE.search(raw):
        label = _TOTAL_PCT_RE.sub("Total % ", raw, count=1).strip()
        return label, None, None

    # Trailing % (with or without preceding space)
    if raw.endswith("%"):
        label = raw[:-1].rstrip()
        return label, "%", None

    return raw, None, None


def _to_factor_id(label: str) -> str:
    """Convert a factor label to a stable snake_case identifier."""
    s = label.lower()
    s = s.replace("%", "")  # remove % from aggregate labels
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


# ---------------------------------------------------------------------------
# Threshold value parsing
# ---------------------------------------------------------------------------

_DUAL_NUM_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*\((\d+(?:\.\d+)?)\)$")
_PURE_NUM_RE = re.compile(r"^(\d+(?:\.\d+)?)$")
_NO_LIMIT_TERMS = {"no limit", "no minimum"}


def _parse_threshold_cell(text: str) -> dict:
    """Convert a threshold cell's text to a threshold object dict."""
    text = text.strip()
    base: dict = {"value_type": None, "value": None, "value_alt": None, "threshold_note": None}

    if not text or text.lower() == "not applicable":
        return {**base, "value_type": "not_applicable"}

    if text.lower() in _NO_LIMIT_TERMS:
        return {**base, "value_type": "no_limit"}

    # Dual-unit numeric: "75 (365)"
    m = _DUAL_NUM_RE.match(text)
    if m:
        return {**base, "value_type": "numeric", "value": float(m.group(1)), "value_alt": float(m.group(2))}

    # Pure number
    m = _PURE_NUM_RE.match(text)
    if m:
        return {**base, "value_type": "numeric", "value": float(m.group(1))}

    # Everything else: qualitative (prose, mixed prose+number, "No limit within..." etc.)
    return {**base, "value_type": "qualitative", "value": text}


# ---------------------------------------------------------------------------
# Fallthrough cell parsing
# ---------------------------------------------------------------------------

def _parse_fallthrough_cell(td) -> object:
    """Parse the final (fallthrough) column cell.

    Returns:
      - None if cell is empty
      - A list of condition objects for canola stones branching case
      - A plain string for all other cases
    """
    # Canola stones: bold West/East markers indicate branching by region
    strong_texts = [s.get_text(strip=True).lower() for s in td.find_all("strong")]
    if "west" in strong_texts and "east" in strong_texts:
        result = _parse_stones_fallthrough(td)
        if result is not None:
            return result

    text = td.get_text(separator=" ", strip=True).replace("\xa0", " ").strip()
    # Collapse internal whitespace artifacts from separator=" "
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else None


def _parse_stones_fallthrough(td) -> list | None:
    """Parse the canola stones branching fallthrough into condition objects.

    Expected structure (from live CGC page):
        "2.5% or less— West - Grade1, or East - Grade2 Over 2.5%—Grade3"
    with West and East in <strong> tags.
    """
    strings = list(td.stripped_strings)
    # e.g. ['2.5% or less—', 'West', '- Grade1, or', 'East', '- Grade2 Over 2.5%—Grade3']

    west_idx = next((i for i, s in enumerate(strings) if s.lower() == "west"), None)
    east_idx = next((i for i, s in enumerate(strings) if s.lower() == "east"), None)
    if west_idx is None or east_idx is None:
        return None

    pre = strings[0] if strings else ""
    cond_m = re.search(r"([\d.]+)%\s*or\s*less", pre, re.IGNORECASE)
    if not cond_m:
        return None
    threshold = cond_m.group(1)

    # West grade
    west_raw = strings[west_idx + 1] if west_idx + 1 < len(strings) else ""
    west_grade = re.sub(r"^-\s*", "", west_raw)
    west_grade = re.sub(r",\s*or\s*$", "", west_grade).strip()

    # East grade (and trailing "Over N%—Grade")
    east_raw = strings[east_idx + 1] if east_idx + 1 < len(strings) else ""
    east_raw = re.sub(r"^-\s*", "", east_raw)
    over_m = re.search(
        r"^(.*?)\s+[Oo]ver\s+[\d.]+%\s*[—\-]\s*(.+)$", east_raw
    )
    if not over_m:
        return None

    east_grade = over_m.group(1).strip()
    over_grade = over_m.group(2).strip()

    return [
        {"condition": f"<= {threshold}%", "region": "west", "grade": west_grade},
        {"condition": f"<= {threshold}%", "region": "east", "grade": east_grade},
        {"condition": f"> {threshold}%", "region": None, "grade": over_grade},
    ]


# ---------------------------------------------------------------------------
# Footnote extraction
# ---------------------------------------------------------------------------

def _extract_footnotes(table) -> dict[str, str]:
    """Extract footnotes from the wb-fnote section in the last table row."""
    footnotes: dict[str, str] = {}
    fn_section = table.find("section", class_="wb-fnote")
    if not fn_section:
        return footnotes
    for dt, dd in zip(fn_section.find_all("dt"), fn_section.find_all("dd")):
        fn_id = dd.get("id", "").strip()
        # Extract text from first <p>, stripping the "Return to footnote" back-link
        p = dd.find("p", class_=lambda c: c is None or "fn-rtn" not in (c or ""))
        raw = p.get_text(separator=" ") if p else dd.get_text(separator=" ")
        text = re.sub(r"\s+", " ", raw).strip()
        if fn_id and text:
            footnotes[fn_id] = text
    return footnotes


# ---------------------------------------------------------------------------
# Table parser
# ---------------------------------------------------------------------------

def _caption_to_group(caption_text: str) -> tuple[str, str]:
    """Map table caption text to (group_id, group_label)."""
    low = caption_text.lower()
    if "standard of quality" in low:
        return "standard_of_quality", "Standard of quality"
    if "grading factors" in low:
        return "grading_factors", "Grading factors"
    if "foreign material" in low:
        return "foreign_material", "Foreign material"
    if "damage" in low:
        return "damage", "Damage"
    if "other factors" in low:
        return "other_factors", "Other factors"
    # Fallback: derive from caption tail
    tail = caption_text.split(",")[-1].strip()
    slug = re.sub(r"[^a-z0-9]+", "_", tail.lower()).strip("_")
    return slug, tail


def _parse_table(table) -> tuple[list[str], str, list[dict], dict[str, str]]:
    """Parse a single CGC grade table.

    Returns:
        grades           — ordered list of grade column names
        fallthrough_label — header of the last column
        factors          — list of factor dicts
        footnotes        — {fntN: text} from this table's footnote section
    """
    rows = table.find_all("tr")
    if not rows:
        return [], "", [], {}

    # --- Header row ---
    header_cells = rows[0].find_all("th")
    all_headers = [c.get_text(strip=True).replace("\xa0", " ").strip() for c in header_cells]
    # all_headers[0] = "Grading factor" (skip)
    # all_headers[-1] = fallthrough label
    # all_headers[1:-1] = grade names
    grades = all_headers[1:-1]
    fallthrough_label = all_headers[-1] if len(all_headers) > 1 else ""

    # --- Footnotes ---
    footnotes = _extract_footnotes(table)

    # --- Factor rows ---
    factors: list[dict] = []
    for row in rows[1:]:
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        # Skip footnote rows (first cell is a wide <td>)
        if cells[0].name == "td":
            continue
        # Must be a factor row: first cell is <th>
        raw_label, footnote_ref = _extract_th_label(cells[0])
        factor_label, unit, unit_alt = _parse_label_and_unit(raw_label)
        factor_id = _to_factor_id(factor_label)
        is_aggregate = bool(_TOTAL_PCT_RE.search(raw_label))

        # Threshold cells: all cells between factor th and fallthrough td
        threshold_tds = cells[1:-1]
        fallthrough_td = cells[-1] if len(cells) > 1 else None

        # Threshold direction
        label_low = factor_label.lower()
        if label_low.startswith("minimum"):
            threshold_direction: str | None = "minimum"
        else:
            threshold_direction = None  # determined after value parsing

        thresholds: dict = {}
        has_numeric = False
        for grade, td in zip(grades, threshold_tds):
            text = td.get_text(strip=True).replace("\xa0", " ").strip()
            t = _parse_threshold_cell(text)
            thresholds[grade] = t
            if t["value_type"] == "numeric":
                has_numeric = True

        # Default non-minimum factors with any numeric threshold to "maximum"
        if has_numeric and threshold_direction is None:
            threshold_direction = "maximum"

        # Fallthrough
        fallthrough = _parse_fallthrough_cell(fallthrough_td) if fallthrough_td else None

        factors.append({
            "factor_id": factor_id,
            "factor_label": factor_label,
            "unit": unit,
            "unit_alt": unit_alt,
            "threshold_direction": threshold_direction,
            "is_aggregate": is_aggregate,
            "aggregates": None,  # TODO: verify against CGC source
            "footnote_ref": footnote_ref,
            "thresholds": thresholds,
            "fallthrough": fallthrough,
        })

    return grades, fallthrough_label, factors, footnotes


# ---------------------------------------------------------------------------
# Floor rule extraction
# ---------------------------------------------------------------------------

_FLOOR_RULE_RE = re.compile(
    r"graded no lower than\s+(No\.\s*\d+\s+\S+)\s+on account of\s+(\w+)",
    re.IGNORECASE,
)


def _extract_floor_rules(soup) -> list[dict]:
    """Find floor-rule paragraphs on the page."""
    rules = []
    for p in soup.find_all("p"):
        text = p.get_text(strip=True).replace("\xa0", " ").strip()
        # Strip leading "Note:" prefix used on some pages
        note_text = re.sub(r"^Note:\s*", "", text, flags=re.IGNORECASE).strip()
        m = _FLOOR_RULE_RE.search(note_text)
        if m:
            rules.append({
                "account": m.group(2).lower(),
                "floor_grade": m.group(1).strip(),
                "note": note_text,
            })
    return rules


# ---------------------------------------------------------------------------
# Common record assembler
# ---------------------------------------------------------------------------

def _assemble(
    grain_id: str,
    soup,
    table_slice: slice,
    *,
    variety_tracks: list | None = None,
) -> dict:
    """Assemble a grain record dict from a page soup and a slice of its tables."""
    cfg = GRAIN_CONFIG[grain_id]
    tables = soup.find_all("table")[table_slice]

    factor_groups: list[dict] = []
    all_footnotes: dict[str, str] = {}
    grades: list[str] = []
    fallthrough_label: str = ""

    for table in tables:
        caption = table.find("caption")
        cap_text = caption.get_text(strip=True).replace("\xa0", " ") if caption else ""
        group_id, group_label = _caption_to_group(cap_text)

        tbl_grades, tbl_ft_label, factors, footnotes = _parse_table(table)
        if tbl_grades and not grades:
            grades = tbl_grades
            fallthrough_label = tbl_ft_label
        all_footnotes.update(footnotes)

        factor_groups.append({
            "group_id": group_id,
            "group_label": group_label,
            "factors": factors,
        })

    floor_rules = _extract_floor_rules(soup)

    return {
        "grain_id": grain_id,
        "grain_name": cfg["grain_name"],
        "kind": cfg["kind"],
        "region": cfg["region"],
        "use_class": cfg["use_class"],
        "variety_tracks": variety_tracks,
        "colour_modifier": cfg["colour_modifier"],
        "size_modifier": cfg["size_modifier"],
        "source_url": CGC_BASE + cfg["url"],
        "effective_crop_year": EFFECTIVE_CROP_YEAR,
        "last_scraped": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "coverage_status": "complete",
        "fallthrough_label": fallthrough_label if fallthrough_label else None,
        "grade_floor_rules": floor_rules,
        "grades": grades,
        "factor_groups": factor_groups,
        "footnotes": all_footnotes if all_footnotes else None,
    }


# ---------------------------------------------------------------------------
# Grain-specific variety track helpers
# ---------------------------------------------------------------------------

def _barley_variety_tracks(grades: list[str]) -> list[dict]:
    """Split barley grades into covered vs hulless tracks."""
    covered = [g for g in grades if "Hulless" not in g]
    hulless = [g for g in grades if "Hulless" in g]
    tracks = []
    if covered:
        tracks.append({"track_id": "covered", "grades": covered})
    if hulless:
        tracks.append({"track_id": "hulless", "grades": hulless})
    return tracks or None


# ---------------------------------------------------------------------------
# Grain-specific parsers
# ---------------------------------------------------------------------------

def _parse_wheat(html: str, grain_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return _assemble(grain_id, soup, slice(0, 3))


def _parse_canola(html: str, grain_id: str) -> dict:
    # Tables 0-2: Canola. Tables 3-5: Rapeseed (out of scope for v1).
    soup = BeautifulSoup(html, "html.parser")
    return _assemble(grain_id, soup, slice(0, 3))


def _parse_barley_gp_cw(html: str, grain_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    # Determine variety tracks from grade headers in table 0
    tables = soup.find_all("table")
    if tables:
        hdr = tables[0].find("tr")
        ths = [th.get_text(strip=True).replace("\xa0", " ") for th in hdr.find_all("th")]
        grades = ths[1:-1]  # strip first ("Grading factor") and last (fallthrough)
        tracks = _barley_variety_tracks(grades)
    else:
        tracks = None
    return _assemble(grain_id, soup, slice(0, 3), variety_tracks=tracks)


def _parse_barley_gp_ce(html: str, grain_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    if len(tables) >= 4:
        hdr = tables[3].find("tr")
        ths = [th.get_text(strip=True).replace("\xa0", " ") for th in hdr.find_all("th")]
        grades = ths[1:-1]
        tracks = _barley_variety_tracks(grades)
    else:
        tracks = None
    return _assemble(grain_id, soup, slice(3, 6), variety_tracks=tracks)


def _parse_corn_cw(html: str, grain_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return _assemble(grain_id, soup, slice(0, 3))


def _parse_corn_ce(html: str, grain_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return _assemble(grain_id, soup, slice(3, 6))


def _parse_soybeans(html: str, grain_id: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return _assemble(grain_id, soup, slice(0, 4))


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_PARSERS = {
    "wheat": _parse_wheat,
    "canola": _parse_canola,
    "barley_gp_cw": _parse_barley_gp_cw,
    "barley_gp_ce": _parse_barley_gp_ce,
    "corn_cw": _parse_corn_cw,
    "corn_ce": _parse_corn_ce,
    "soybeans": _parse_soybeans,
}


def parse(grain_id: str, html: str) -> dict:
    """Parse a CGC page HTML string into a grain record dict.

    Args:
        grain_id: One of the keys in GRAIN_CONFIG (e.g. "CWRS").
        html:     The full HTML string of the CGC page for this grain.

    Returns:
        A dict matching the grain_record.json schema.

    Raises:
        KeyError: if grain_id is not in GRAIN_CONFIG.
    """
    cfg = GRAIN_CONFIG[grain_id]
    parser_fn = _PARSERS[cfg["parser"]]
    return parser_fn(html, grain_id)
