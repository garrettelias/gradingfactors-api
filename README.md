# Grading Factors API

A public REST API serving machine-readable Canadian Grain Commission (CGC) grade determinant tables.

The CGC publishes grading factor data — the thresholds used to assign an official grade to a grain sample — only as HTML pages and PDFs. No machine-readable version exists. This API fills that gap.

**This is a data service, not a grading calculator.** It serves the reference tables that developers need to build grading tools. The intended use pattern is: pull the full dataset, store it locally, build against your own copy.

Base URL: `https://api.gradingfactors.ca`

---

## Authentication

All endpoints except `POST /api/register` require an API key passed as a request header:
X-API-Key: gf_live_...

Register for a key at `POST /api/register` or at [gradingfactors.ca](https://gradingfactors.ca).

---

## Endpoints

### GET /api/grains

Returns metadata for all supported grain classes. Does not include factor data.

```bash
curl https://api.gradingfactors.ca/api/grains \
  -H "X-API-Key: gf_live_..."
```

### GET /api/grains/{grain_id}

Returns the full grading factor table for a single grain class, including all factor groups, factors, per-grade thresholds, grade floor rules, and footnotes. `grain_id` is case-insensitive.

```bash
curl https://api.gradingfactors.ca/api/grains/CWRS \
  -H "X-API-Key: gf_live_..."
```

Returns 404 if the grain_id is not found.

### GET /api/changelog

Returns recent data changelog entries, newest first. Supports optional filtering by `grain_id` and `limit` (default 20, max 100).

```bash
curl "https://api.gradingfactors.ca/api/changelog?grain_id=CWRS&limit=5" \
  -H "X-API-Key: gf_live_..."
```

### POST /api/register

Generates a new API key linked to the provided email address. The key is returned once and never stored — save it immediately.

```bash
curl -X POST https://api.gradingfactors.ca/api/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'
```

---

## Rate Limiting

100 requests per hour per API key. Exceeding the limit returns a `429` response with a `Retry-After` header indicating when the window resets.

---

## Supported Grains (V1)

| grain_id | Name |
|---|---|
| `CWRS` | Canada Western Red Spring wheat |
| `CWAD` | Canada Western Amber Durum wheat |
| `CPSR` | Canada Prairie Spring Red wheat |
| `CANOLA` | Canola, Canada (CAN) |
| `BARLEY_GP_CW` | Barley, Canada Western General Purpose |
| `BARLEY_GP_CE` | Barley, Canada Eastern General Purpose |
| `CORN_CW` | Corn, Canada Western Yellow, White or Mixed |
| `CORN_CE` | Corn, Canada Eastern Yellow, White or Mixed |
| `SOYBEANS` | Soybeans, Canada Yellow, Green, Brown, Black or Mixed |

Effective crop year: 2025/26.

---

## Data Model

All responses include `schema_version: "1.0"` at the top level. Full field reference and schema documentation at [gradingfactors.ca](https://gradingfactors.ca).

---

## Update Model

CGC grade determinant data changes annually at the start of each crop year. This API is updated manually after CGC publishes changes. The changelog endpoint records all updates. See [gradingfactors.ca](https://gradingfactors.ca) for details.

---

## OpenAPI Documentation

Interactive API documentation is available at [https://api.gradingfactors.ca/docs](https://api.gradingfactors.ca/docs).