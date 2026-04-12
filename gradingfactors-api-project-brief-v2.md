# Grading Factors API — Project Brief

## Purpose

This document is the authoritative specification for building the Grading Factors API. It contains all decisions, constraints, schema definitions, endpoint specifications, and build instructions needed to execute the project from scratch. Do not deviate from decisions documented here without explicit instruction.

---

## What We Are Building

A **public reference data API** that serves structured, machine-readable versions of the Canadian Grain Commission's (CGC) Official Grain Grading Guide (GGG) grade determinant tables.

The CGC publishes grade determinant data — the thresholds used to assign an official grade to a sample of grain — only as HTML web pages and printable PDFs. No machine-readable version exists anywhere. This API fills that gap.

**This is a data service, not a grading calculator.** It does not accept sample measurements and return a grade. It serves the reference data that developers need to build such tools themselves. The mental model for consumers is: pull the full dataset periodically, store it locally, build against your own copy. The API is designed for sync, not live query.

The project is branded as **Grading Factors**, accessible at `gradingfactors.ca`. The API lives at `api.gradingfactors.ca`. The apex domain is reserved for a future marketing or documentation page.

---

## Scope

### V1 Grain Classes

| grain_id | Full Name | Source Page |
|---|---|---|
| `CWRS` | Canada Western Red Spring wheat | `/04-wheat/primary-grade-determination/cwrs-wheat.html` |
| `CWAD` | Canada Western Amber Durum wheat | `/04-wheat/primary-grade-determination/cwad-wheat.html` |
| `CPSR` | Canada Prairie Spring Red wheat | `/04-wheat/primary-grade-determination/cpsr-wheat.html` |
| `CANOLA` | Canola, Canada (CAN) | `/10-canola-rapeseed/primary-export-grade-determination-tables.html` |
| `BARLEY_GP` | Barley, Canada Western/Eastern General Purpose | `/06-barley/primary-export-grade-determination/general-purpose-barley.html` |
| `CORN` | Corn, Canada Western/Eastern Yellow, White or Mixed | `/17-corn/primary-export-grade-determination-tables.html` |
| `SOYBEANS` | Soybeans, Canada Yellow, Green, Brown, Black or Mixed | `/20-soybeans/primary-export-grade-determination-tables.html` |

All source URLs are relative to `https://www.grainscanada.gc.ca/en/grain-quality/official-grain-grading-guide`.

**Effective crop year for all v1 data: 2025/26.**

### Explicitly Out of Scope for V1

- Export grade determination tables (primary stream only)
- All wheat classes not listed above (14 additional classes exist)
- Barley Malting and Barley Food use classes
- Rapeseed (shares a source page with Canola; will be added in a future version)
- All remaining grain types: Oats, Rye, Triticale, Peas, Lentils, Beans, Faba Beans, Chickpeas, Flaxseed, Mustard Seed, Sunflower Seed, Safflower Seed, Buckwheat, Canary Seed
- Mixed Grain, Screenings, Experimental Grades, Sample Feed Grain (permanently excluded — no standard grade tables)
- A grading calculator (separate project — do not conflate with this API)
- A web UI for end users beyond API documentation

---

## Tech Stack

| Component | Choice | Rationale |
|---|---|---|
| Database | PostgreSQL via Supabase | Relational structure fits the data model; hosted; managed |
| API layer | Python 3.11+ / FastAPI | Shares language with scraper; auto-generates OpenAPI docs |
| Scraper | Python script in same repo | BeautifulSoup + httpx; runs manually on a trigger, not on a schedule |
| Primary dev environment | WSL2 (Ubuntu) on Windows 10 desktop | Consistent Linux tooling; primary machine |
| Secondary dev environment | M2 MacBook Air (macOS) | Secondary machine; same repo via Git |
| Public hosting | Fly.io | Always-on free tier; no cold starts; simple CLI deployment |
| Auth | API key via request header | `X-API-Key` header; keys stored in Supabase |

### Two-Machine Workflow

Git is the sync layer between machines. Work locally on whichever machine you are at, commit and push to GitHub, pull on the other machine when switching. Claude Code runs locally on each machine and operates on the current repo state.

The following must be installed identically on both machines:
- Python 3.11+
- Node.js
- Claude Code (`npm install -g @anthropic/claude-code`)
- Fly CLI
- A local `.env` file with Supabase credentials — this never goes in the repo and must be created manually on each machine

### Key Constraints

- The Supabase database is the source of truth. The FastAPI layer reads from it. The scraper writes to it.
- The API layer must **never** expose the raw Supabase auto-generated REST API to the public. All public access goes through FastAPI.
- All routes are prefixed `/api/`. Schema versioning is handled via a `schema_version` field in all responses, not via URL prefixes.
- The scraper is a **diff tool**, not an automated pipeline. It fetches CGC pages, compares to current DB state, outputs a human-readable diff report, and provides a one-command import after human review. It does not run on a schedule.

---

## Data Model

### Validated JSON Schema

The following schema was validated against every grain type in the GGG. It must not be changed without updating this brief.

#### Value Types

Every threshold has a `value_type` field. Valid values:

| value_type | Meaning | Example |
|---|---|---|
| `numeric` | A number; compare against this threshold | `0.04` |
| `no_limit` | No maximum or minimum applies | `"No minimum"`, `"No limit"` |
| `qualitative` | Descriptive text; not machine-comparable | Standard of quality descriptions; policy instructions like `"Considered as other cereal grains"`. When a CGC table cell mixes prose and numbers, store as qualitative — the text is preserved and consumers can parse numbers if needed. |
| `qualitative_judgment` | Text that replaces a numeric threshold at a specific grade | `"Consider overall appearance"` (CWAD smudge at No. 4) |
| `not_applicable` | Factor genuinely does not apply at this grade level | Red Lentils Wrinkled factor at Extra No. 3 and No. 3 |

#### Threshold Object

```json
{
  "value_type": "numeric",
  "value": 0.04,
  "value_alt": null,
  "threshold_note": null
}
```

- `value`: numeric value, the descriptive string for qualitative types, or `null` for `no_limit` and `not_applicable`
- `value_alt`: used only when a factor has dual units (e.g. test weight in both kg/hL and g/0.5L)
- `threshold_note`: optional string for qualifying annotations that do not replace the value (e.g. `"excluding frost"`, `"Not included in total damage assessment"`)

#### Factor Object

```json
{
  "factor_id": "ergot",
  "factor_label": "Ergot",
  "unit": "%",
  "unit_alt": null,
  "threshold_direction": "maximum",
  "is_aggregate": false,
  "aggregates": null,
  "footnote_ref": null,
  "thresholds": {
    "No. 1 CWRS": { "value_type": "numeric", "value": 0.04 },
    "No. 2 CWRS": { "value_type": "numeric", "value": 0.04 },
    "No. 3 CWRS": { "value_type": "numeric", "value": 0.04 },
    "CW Feed":    { "value_type": "numeric", "value": 0.10 }
  },
  "fallthrough": "Wheat, Sample CW Account Ergot"
}
```

- `threshold_direction`: `"maximum"` (sample must not exceed) or `"minimum"` (sample must meet or exceed). Null for qualitative factors.
- `is_aggregate`: `true` if this factor is a combined total of sibling factors
- `aggregates`: array of `factor_id` strings that compose this total, or `null`
- `fallthrough`: the grade assigned if the sample exceeds this factor's threshold for all named grades. Can be:
  - A string (simple case)
  - An array of condition objects (branching case, used for Stones regional split and multi-tier outcomes):
    ```json
    [
      { "condition": "<= 2.5%", "region": "west", "grade": "Canola, Rejected (grade) Account Stones" },
      { "condition": "<= 2.5%", "region": "east", "grade": "Canola, Sample Canada Account Stones" },
      { "condition": "> 2.5%",  "region": null,   "grade": "Canola, Sample Salvage" }
    ]
    ```
  - `null` if no downgrade outcome is defined for this factor

#### Factor Group Object

```json
{
  "group_id": "foreign_material",
  "group_label": "Foreign material",
  "factors": [ ]
}
```

`group_id` and `group_label` are not standardized across grain types by design. Store what the CGC uses:
- Wheat: `standard_of_quality`, `foreign_material`, `grading_factors`
- Oilseeds / Pulses / Corn: `standard_of_quality`, `damage`, `foreign_material`
- Soybeans: `standard_of_quality`, `damage`, `foreign_material`, `other_factors`
- Canary Seed: `standard_of_quality`, `foreign_material`

#### Grain Class Record (Top Level)

```json
{
  "schema_version": "1.0",
  "grain_id": "CWRS",
  "grain_name": "Canada Western Red Spring",
  "kind": "wheat",
  "region": "western",
  "use_class": null,
  "variety_tracks": null,
  "colour_modifier": false,
  "size_modifier": false,
  "source_url": "https://www.grainscanada.gc.ca/en/...",
  "effective_crop_year": "2025/26",
  "last_scraped": "2025-11-01T00:00:00Z",
  "coverage_status": "complete",
  "grade_floor_rules": [
    {
      "account": "mildew",
      "floor_grade": "No. 3 CWRS",
      "note": "Samples of CWRS will be graded no lower than No. 3 CWRS on account of mildew"
    }
  ],
  "grades": ["No. 1 CWRS", "No. 2 CWRS", "No. 3 CWRS", "CW Feed"],
  "fallthrough_label": "Grade, if specs for CW Feed not met",
  "factor_groups": [ ],
  "footnotes": {
    "fnt1": "See Frost and Mildew for applicable standard"
  }
}
```

Field notes:
- `schema_version`: the version of the response schema. Increment on breaking changes only; additive changes do not require a version bump. Current value: `"1.0"`.
- `region`: `"western"`, `"eastern"`, or `null` if not regionally split at the record level (e.g. Triticale, Canola)
- `use_class`: `"malting"`, `"food"`, `"general_purpose"`, or `null`. Used for Barley.
- `variety_tracks`: array of track objects when a table has parallel grade columns for different variety types. Used for Barley GP (Covered vs Hulless):
  ```json
  [
    { "track_id": "covered", "grades": ["No. 1 CW", "No. 2 CW"] },
    { "track_id": "hulless", "grades": ["No. 1 CW Hulless", "No. 2 CW Hulless"] }
  ]
  ```
- `colour_modifier`: `true` if colour is appended to the grade name (Soybeans, Corn)
- `size_modifier`: `true` if size is appended to the grade name (Buckwheat — future version)
- `coverage_status`: `"complete"` or `"partial"`. Use `"partial"` for grains where not all sub-classes are yet loaded.

---

## Database Schema

Implement in Supabase PostgreSQL. Supabase project name: `gradingfactors-api`. Use UUID primary keys throughout.

### Tables

#### `grain_classes`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `grain_id` | `text` UNIQUE | e.g. `"CWRS"` |
| `grain_name` | `text` | |
| `kind` | `text` | `"wheat"`, `"oilseed"`, `"pulse"`, `"cereal"` |
| `region` | `text` NULLABLE | `"western"` or `"eastern"` |
| `use_class` | `text` NULLABLE | `"malting"`, `"food"`, `"general_purpose"` |
| `colour_modifier` | `boolean` | default `false` |
| `size_modifier` | `boolean` | default `false` |
| `source_url` | `text` | |
| `effective_crop_year` | `text` | e.g. `"2025/26"` |
| `last_scraped` | `timestamptz` | |
| `coverage_status` | `text` | `"complete"` or `"partial"` |
| `fallthrough_label` | `text` NULLABLE | |
| `grade_floor_rules` | `jsonb` | Array of floor rule objects |
| `grades` | `jsonb` | Ordered array of grade name strings |
| `variety_tracks` | `jsonb` NULLABLE | Array of track objects |
| `footnotes` | `jsonb` NULLABLE | Object keyed by footnote id |
| `created_at` | `timestamptz` | default `now()` |
| `updated_at` | `timestamptz` | default `now()` |

#### `factor_groups`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `grain_class_id` | `uuid` FK → `grain_classes.id` | |
| `group_id` | `text` | e.g. `"foreign_material"` |
| `group_label` | `text` | e.g. `"Foreign material"` |
| `sort_order` | `integer` | Preserves original table ordering |

#### `factors`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `factor_group_id` | `uuid` FK → `factor_groups.id` | |
| `factor_id` | `text` | e.g. `"ergot"` |
| `factor_label` | `text` | e.g. `"Ergot"` |
| `unit` | `text` NULLABLE | e.g. `"%"`, `"kg/hL"` |
| `unit_alt` | `text` NULLABLE | e.g. `"g/0.5L"` |
| `threshold_direction` | `text` NULLABLE | `"maximum"` or `"minimum"` |
| `is_aggregate` | `boolean` | default `false` |
| `aggregates` | `jsonb` NULLABLE | Array of factor_id strings |
| `footnote_ref` | `text` NULLABLE | References `grain_classes.footnotes` key |
| `thresholds` | `jsonb` | Keyed by grade name string |
| `fallthrough` | `jsonb` NULLABLE | String or array of condition objects |
| `sort_order` | `integer` | Preserves original table ordering |

#### `api_keys`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `key_hash` | `text` UNIQUE | SHA-256 hash of the actual key |
| `email` | `text` | Registrant email |
| `created_at` | `timestamptz` | |
| `last_used_at` | `timestamptz` NULLABLE | |
| `is_active` | `boolean` | default `true` |

#### `changelog`

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | |
| `crop_year` | `text` | e.g. `"2025/26"` |
| `effective_date` | `date` | |
| `grain_ids_affected` | `jsonb` | Array of grain_id strings |
| `summary` | `text` | Human-readable description of changes |
| `source_memo_url` | `text` NULLABLE | CGC trade memo URL if available |
| `created_at` | `timestamptz` | |

---

## API Endpoints

Base URL: `https://api.gradingfactors.ca`

All endpoints require `X-API-Key: {key}` header except `POST /api/register`.

All responses are `application/json`. All responses include a top-level `schema_version` field. All errors follow:
```json
{ "error": "string describing the problem" }
```

### `GET /api/grains`

Returns metadata for all grain classes in the database. Does not include factor data.

**Response:**
```json
{
  "schema_version": "1.0",
  "count": 7,
  "grains": [
    {
      "grain_id": "CWRS",
      "grain_name": "Canada Western Red Spring",
      "kind": "wheat",
      "region": "western",
      "use_class": null,
      "effective_crop_year": "2025/26",
      "coverage_status": "complete",
      "grades": ["No. 1 CWRS", "No. 2 CWRS", "No. 3 CWRS", "CW Feed"]
    }
  ]
}
```

`count` is a computed field — the number of grain records in the response. It is not stored; it is calculated as `len(grains)` at response time.

### `GET /api/grains/{grain_id}`

Returns the complete record for a grain class including all factor groups, factors, and thresholds. This is the primary endpoint.

`grain_id` is case-insensitive.

**Response:** The full grain class record. The response includes all fields defined in the data model above. The following is a structurally complete but abbreviated example showing the nesting of `factor_groups` → `factors` → `thresholds`:

```json
{
  "schema_version": "1.0",
  "grain_id": "CWRS",
  "grain_name": "Canada Western Red Spring",
  "kind": "wheat",
  "region": "western",
  "use_class": null,
  "variety_tracks": null,
  "colour_modifier": false,
  "size_modifier": false,
  "source_url": "https://www.grainscanada.gc.ca/en/...",
  "effective_crop_year": "2025/26",
  "last_scraped": "2026-04-11T00:00:00Z",
  "coverage_status": "complete",
  "fallthrough_label": "Grade, if specs for CW Feed not met",
  "grade_floor_rules": [
    {
      "account": "mildew",
      "floor_grade": "No. 3 CWRS",
      "note": "Samples of CWRS will be graded no lower than No. 3 CWRS on account of mildew"
    }
  ],
  "grades": ["No. 1 CWRS", "No. 2 CWRS", "No. 3 CWRS", "CW Feed"],
  "factor_groups": [
    {
      "group_id": "foreign_material",
      "group_label": "Foreign material",
      "factors": [
        {
          "factor_id": "ergot",
          "factor_label": "Ergot",
          "unit": "%",
          "unit_alt": null,
          "threshold_direction": "maximum",
          "is_aggregate": false,
          "aggregates": null,
          "footnote_ref": null,
          "thresholds": {
            "No. 1 CWRS": { "value_type": "numeric", "value": 0.04, "value_alt": null, "threshold_note": null },
            "No. 2 CWRS": { "value_type": "numeric", "value": 0.04, "value_alt": null, "threshold_note": null },
            "No. 3 CWRS": { "value_type": "numeric", "value": 0.04, "value_alt": null, "threshold_note": null },
            "CW Feed":    { "value_type": "numeric", "value": 0.10, "value_alt": null, "threshold_note": null }
          },
          "fallthrough": "Wheat, Sample CW Account Ergot"
        }
      ]
    }
  ],
  "footnotes": {
    "fnt1": "See Frost and Mildew for applicable standard"
  }
}
```

All factor groups and all factors are returned. The example above shows one factor group with one factor for brevity. A real CWRS response contains three factor groups and approximately 25 factors.

**Error — grain not found:**
```json
{ "error": "Grain class 'XYZ' not found. Call GET /api/grains for available grain IDs." }
```

### `GET /api/changelog`

Returns changelog entries in reverse chronological order.

**Query params:**
- `?grain_id=CWRS` — filter to a specific grain
- `?limit=10` — number of entries (default 20, max 100)

**Response:**
```json
{
  "schema_version": "1.0",
  "count": 2,
  "entries": [
    {
      "id": "uuid",
      "crop_year": "2025/26",
      "effective_date": "2025-08-01",
      "grain_ids_affected": ["CWRS", "CWAD"],
      "summary": "Updated fusarium damage tolerances for CWRS and CWAD per CGC trade memo 2025-01.",
      "source_memo_url": "https://grainscanada.gc.ca/en/industry/memos/2025/2025-01.html"
    }
  ]
}
```

### `POST /api/register`

Issues an API key. No authentication required.

**Request body:**
```json
{ "email": "developer@example.com" }
```

**Response:**
```json
{
  "schema_version": "1.0",
  "api_key": "gf_live_xxxxxxxxxxxxxxxx",
  "email": "developer@example.com",
  "message": "Store this key securely — it will not be shown again."
}
```

The key itself is never stored; only its SHA-256 hash is stored in the `api_keys` table. Key format prefix: `gf_live_`.

---

## Directory Structure

```
gradingfactors-api/
├── README.md
├── CHANGELOG.md
├── pyproject.toml
├── .env.example
├── .gitignore
│
├── api/
│   ├── main.py              # FastAPI app entry point
│   ├── dependencies.py      # API key auth dependency
│   ├── routers/
│   │   ├── grains.py        # /grains and /grains/{grain_id}
│   │   ├── changelog.py     # /changelog
│   │   └── register.py      # /register
│   ├── models/
│   │   ├── grain.py         # Pydantic response models
│   │   ├── changelog.py
│   │   └── register.py
│   └── db.py                # Supabase client singleton
│
├── docs/
│   └── field-reference.md   # Field-level documentation for all schema fields
│
├── scraper/
│   ├── fetch.py             # HTTP fetch with rate limiting and retries
│   ├── parse.py             # HTML → structured dict for each grain type
│   ├── diff.py              # Compare fetched data against DB state
│   ├── report.py            # Human-readable diff output to terminal
│   └── import.py            # Write approved diff to DB
│
├── data/
|   ├── seed/
|   │   ├── grains/
|   │   │   ├── CWRS.json
|   │   │   ├── CWAD.json
|   │   │   ├── CPSR.json
|   │   │   ├── CANOLA.json
|   │   │   ├── BARLEY_GP_CW.json
|   │   │   ├── BARLEY_GP_CE.json
|   │   │   ├── CORN_CW.json
|   │   │   ├── CORN_CE.json
|   │   │   └── SOYBEANS.json
|   └── schema/
|       └── grain_record.json
│
├── scripts/
│   ├── seed_db.py           # Load seed data into DB
│   └── generate_api_key.py  # Admin script to generate keys outside registration
│
├── tests/
│   ├── test_api.py
│   ├── test_parser.py
│   └── fixtures/
│       └── cwrs_page.html   # Saved CGC page for offline parser testing
│
└── fly.toml                 # Fly.io deployment config
```

---

## Environment Variables

```bash
# .env (never commit — add to .gitignore)
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_KEY=xxxx        # Service role key — server only, never expose
CGC_BASE_URL=https://www.grainscanada.gc.ca/en/grain-quality/official-grain-grading-guide
ENVIRONMENT=development           # or production
```

This file must be created manually on each development machine. It is never committed to the repository.

---

## Rate Limiting

Implement simple rate limiting in FastAPI middleware:
- 100 requests per hour per API key
- 429 response with `Retry-After` header when exceeded
- No rate limit on `POST /api/register`

---

## Phased Build Plan

Execute strictly in phase order. Do not begin a phase until the previous phase is confirmed working. Confirm the plan for each phase before generating any code.

### Phase 1: Project skeleton and database

1. Initialise Python project with `pyproject.toml` (dependencies: fastapi, uvicorn, supabase-py, httpx, beautifulsoup4, python-dotenv, pytest)
2. Create `.env.example` and `.gitignore` (ensure `.env` is gitignored)
3. Create Supabase tables as specified in the database schema section above
4. Create `api/db.py` with Supabase client initialisation
5. Create `api/main.py` with FastAPI app and health check: `GET /health` returning `{"status": "ok"}`
6. **Confirm:** `uvicorn api.main:app --reload` starts without errors and `GET /health` returns 200

### Phase 2: API key auth

1. Implement `POST /api/register` — validate email, generate `gf_live_` prefixed key, store SHA-256 hash, return key once
2. Implement `api/dependencies.py` — `verify_api_key` dependency that hashes the incoming header value and checks against DB
3. Apply the dependency to a test-only protected route `GET /api/ping` returning `{"authenticated": true}`
4. **Confirm:** registration returns a key; authenticated request to `/ping` returns 200; unauthenticated request returns 401

### Phase 3: Seed data

1. Populate `data/seed/grains/` with one verified JSON file per grain class. Each file contains a single grain record matching the schema. Files are named by `grain_id` (e.g. CWRS.json). Do not generate these files programmatically — they are manually verified.
2. Build `data/schema/grain_record.json` — a JSON Schema file for validating grain records
3. Create `scripts/seed_db.py` — reads all JSON files from `data/seed/grains/`, validates each record against the schema, writes to Supabase in order: `grain_classes` → `factor_groups` → `factors`
4. Run the seed script
5. **Confirm:** all 7 grains are present in the Supabase dashboard with correct structure and factor data

### Phase 4: Core API endpoints

1. Implement `GET /api/grains` — query `grain_classes`, return metadata array with `schema_version: "1.0"` and computed `count` field
2. Implement `GET /api/grains/{grain_id}` — query full record with joined factor groups and factors, assemble response matching the grain class record schema including all factor groups and factors. `grain_id` lookup is case-insensitive.
3. Implement `GET /api/changelog` — query changelog table with optional `grain_id` and `limit` filtering
4. Ensure all responses include `schema_version: "1.0"` at the top level
5. Apply rate limiting middleware (100 requests/hour per API key)
6. Remove the test-only `GET /api/ping` route
7. **Confirm:** all three endpoints return correct data including full factor group and factor nesting; rate limiting triggers at threshold; unknown `grain_id` returns correct error message

### Phase 5: Scraper

1. Implement `scraper/fetch.py` — fetches a CGC page by URL with 2-second delay between requests and 3-retry logic on failure
2. Implement `scraper/parse.py` — parses fetched HTML into a grain record dict matching the schema. Use CWRS as the reference implementation and confirm it matches the seeded data before building parsers for remaining grains.
3. Implement `scraper/diff.py` — compares parsed dict against current DB state, produces a structured diff
4. Implement `scraper/report.py` — prints diff to terminal in readable format: what changed, what was added, what was removed
5. Implement `scraper/import.py` — writes an approved diff to DB and creates a changelog entry
6. **Confirm:** running the scraper against the live CWRS page produces a diff of zero changes (data matches seeded state)

### Phase 6: Tests

1. Write pytest tests for all three API endpoints: happy path, missing grain, invalid API key, rate limit
2. Write pytest tests for the parser using the saved CWRS fixture HTML at `tests/fixtures/cwrs_page.html`
3. **Confirm:** all tests pass

### Phase 7: Fly.io deployment

1. Create `fly.toml` with appropriate configuration for a Python/FastAPI app
2. Set all production environment variables as Fly.io secrets
3. Deploy
4. **Confirm:** all three endpoints respond correctly at `https://api.gradingfactors.ca`

### Phase 8: Documentation

1. Add docstrings to all route handlers — FastAPI uses these to populate the auto-generated OpenAPI docs at `/docs`
2. Write `README.md` covering: what the API is, what it is not, authentication, the three endpoints with full example requests and responses, the update model (how and when data changes), and how to register for a key
3. Write `CHANGELOG.md` with the initial v1 entry
4. Ensure `docs/field-reference.md` is present and up to date
5. **Confirm:** `/docs` renders accurate documentation; README is complete and accurate

---

## Key Decisions — Do Not Revisit Without Instruction

- **Primary stream only.** Export grade tables are not in scope.
- **No grading calculator.** This API serves reference data only. Do not add logic that accepts sample measurements and returns a grade.
- **No auto-scraping.** The scraper is a human-assisted diff/import tool. It does not run on a schedule and is not triggered by any automated process.
- **Three public endpoints only.** No sub-endpoints, no filtering on the grains list, no partial responses.
- **Rapeseed excluded from v1.** It will be added in a future version alongside other grains not in the initial scope.
- **No URL versioning.** Routes are `/api/grains/`, `/api/grains/{grain_id}`, `/api/changelog`, `/api/register`. Breaking changes are managed through `schema_version` in the response body and communicated via changelog and documentation. If a breaking schema change is ever required, `schema_version` is incremented and a changelog entry is created — there are no parallel versioned URL prefixes.
- **Supabase service key is server-only.** It is never exposed in client-facing code, logs, or responses.
- **Seed data is manually verified.** The initial dataset is one hand-verified JSON file per grain class in `data/seed/grains/`. Do not generate or overwrite these files programmatically.
- **Git is the sync layer between machines.** Commit and push after each working session; pull before starting on the other machine. Do not attempt to share a live dev environment across machines.
- **Mixed qualitative/quantitative cells default to qualitative.** When a CGC table cell contains both prose and numbers, store as `value_type: "qualitative"` with the full text preserved. Consumers can parse numbers from the text if needed; information must not be lost by storing as numeric only.

---

## Notes for Claude Code

- Read this brief fully and confirm understanding before writing any code
- Confirm the plan for each phase before executing it
- Keep changes surgical and scoped — do not touch files outside the stated task
- Flag out-of-scope issues proactively, but distinguish "worth knowing" from "blocking"
- Do not generate or overwrite files in `data/seed/grains/` — these files contain manually verified data and must not be modified programmatically
- The grain record schema is validated and locked — do not alter field names, types, or structure without flagging it first
- When uncertain about a grading edge case, leave a `# TODO: verify against CGC source` comment rather than guessing
- If something in this brief appears to conflict with itself, stop and flag it rather than resolving it independently
