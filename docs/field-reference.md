# Grading Factors API — Field Reference

This document describes every field in the grain record schema returned by the Grading Factors API. It is the authoritative reference for understanding what each field means, what values it can hold, and how to use it correctly when building against the API.

All grain data is sourced from the Canadian Grain Commission's Official Grain Grading Guide (GGG) and reflects the primary grade determination tables for the current crop year. This API serves reference data only — it does not accept sample measurements or return grades.

---

## Grain record fields

A grain record is the top-level object returned by `GET /api/v1/grains/{grain_id}`. It describes a single grain class and contains all grading factor data for that class.

---

### `grain_id`

**Type:** string  
**Required:** yes

The unique identifier for this grain class. Used as the path parameter in `GET /api/v1/grains/{grain_id}`. Lookup is case-insensitive.

```json
"grain_id": "CWRS"
```

Valid v1 values: `CWRS`, `CWAD`, `CPSR`, `CANOLA`, `BARLEY_GP`, `CORN`, `SOYBEANS`

---

### `grain_name`

**Type:** string  
**Required:** yes

The full human-readable name of the grain class, as used by the CGC.

```json
"grain_name": "Canada Western Red Spring"
```

---

### `kind`

**Type:** string (enum)  
**Required:** yes

The broad category the grain belongs to.

| Value | Description |
|---|---|
| `wheat` | All wheat classes |
| `cereal` | Non-wheat cereals (barley, rye, oats, triticale) |
| `oilseed` | Canola, rapeseed, flaxseed, mustard, sunflower, safflower |
| `pulse` | Peas, lentils, beans, faba beans, chickpeas, soybeans |

```json
"kind": "wheat"
```

---

### `region`

**Type:** string (enum) or null  
**Required:** no

Indicates whether this record applies to a specific geographic production region. When a grain class has meaningfully different grade specifications between western and eastern Canada, separate records are created — one per region.

| Value | Description |
|---|---|
| `"western"` | Applies to grain grown in western Canada |
| `"eastern"` | Applies to grain grown in eastern Canada |
| `null` | No regional distinction — the record applies nationally |

```json
"region": "western"
```

`null` appears on grains like Canola and Triticale where the CGC publishes a single national table. `"western"` and `"eastern"` appear where separate tables exist, such as Barley General Purpose CW and CE.

Note: some grains with a single record still have regionally branching outcomes within individual factors (notably Stones). See [`fallthrough`](#fallthrough) for how this is handled at the factor level.

---

### `use_class`

**Type:** string (enum) or null  
**Required:** no

For grains where different end uses produce different grade specifications, this field identifies which use class this record covers. Currently used only for Barley, which has separate grade tables for malting, food, and general purpose use.

| Value | Description |
|---|---|
| `"malting"` | Selected for malting purposes |
| `"food"` | Selected for food purposes |
| `"general_purpose"` | All other barley; primarily used as feed |
| `null` | Use class is not applicable for this grain |

```json
"use_class": "general_purpose"
```

---

### `variety_tracks`

**Type:** array of track objects, or null  
**Required:** no

Used when a single grade table contains parallel columns for different variety types — distinct grade sequences that exist side by side in the same source table rather than as separate records.

In v1 this appears only in Barley General Purpose, where covered and hulless barley have separate grade sequences (No. 1 CW / No. 2 CW alongside No. 1 CW Hulless / No. 2 CW Hulless) within the same table.

Each track object contains:

| Field | Type | Description |
|---|---|---|
| `track_id` | string | Machine-readable identifier for this track |
| `grades` | array of strings | The grade names belonging to this track, in quality order |

```json
"variety_tracks": [
  { "track_id": "covered", "grades": ["No. 1 CW", "No. 2 CW"] },
  { "track_id": "hulless", "grades": ["No. 1 CW Hulless", "No. 2 CW Hulless"] }
]
```

When `variety_tracks` is present, a consumer should use it to understand which grades are comparable to each other. Thresholds keyed to `"No. 1 CW"` and `"No. 1 CW Hulless"` are the top grade of their respective tracks — they are parallel, not sequential.

When `variety_tracks` is `null`, all grades in the `grades` array form a single sequential quality ladder from highest to lowest.

---

### `colour_modifier`

**Type:** boolean  
**Required:** yes

When `true`, the colour of the grain is appended to the grade name when expressing an official grade. The colour is not a separate grading factor — it is part of the grade name itself.

```json
"colour_modifier": true
```

For example, Soybeans grades are expressed as "No. 1 Canada Yellow" or "No. 2 Canada Brown" — the colour comes from the physical sample and is appended at grading time. The API stores thresholds under the base grade names (e.g. `"No. 1 Canada"`) without a colour suffix. Consumers assembling a full grade name should append the appropriate colour when `colour_modifier` is `true`.

Grains with `colour_modifier: true` in v1: `CORN`, `SOYBEANS`

---

### `size_modifier`

**Type:** boolean  
**Required:** yes

When `true`, the physical size of the grain (Large or Small, determined by sieve) is appended to the grade name. Applies to Buckwheat, which is not in v1 but is in the schema for forward compatibility.

```json
"size_modifier": false
```

---

### `source_url`

**Type:** string (URI)  
**Required:** yes

The canonical URL of the CGC web page from which this grain record's data was sourced. Use this to cross-reference any value against the authoritative CGC source.

```json
"source_url": "https://www.grainscanada.gc.ca/en/grain-quality/official-grain-grading-guide/04-wheat/primary-grade-determination/cwrs-wheat.html"
```

---

### `effective_crop_year`

**Type:** string  
**Required:** yes

The crop year for which this grade data is in effect. CGC crop years run August 1 to July 31.

```json
"effective_crop_year": "2025/26"
```

Check the [`/api/v1/changelog`](#) endpoint to determine whether data has been updated since you last synced.

---

### `last_scraped`

**Type:** string (ISO 8601 datetime)  
**Required:** yes

The UTC timestamp of when the CGC source page was last fetched and compared against this record. This is not the same as the CGC's own last-modified date — it reflects when the Grading Factors API last verified the data.

```json
"last_scraped": "2026-04-11T00:00:00Z"
```

---

### `coverage_status`

**Type:** string (enum)  
**Required:** yes

Indicates whether all sub-classes for this grain type are present in the API.

| Value | Description |
|---|---|
| `"complete"` | All grade tables for this grain class are loaded |
| `"partial"` | Some sub-classes or tables are not yet loaded |

```json
"coverage_status": "complete"
```

All v1 grain records have `"complete"` coverage status. This field exists to signal to consumers when a grain type has been partially loaded during incremental expansion of the dataset.

---

### `fallthrough_label`

**Type:** string or null  
**Required:** no

The header text of the final column in the CGC source table — the column that specifies what grade is assigned when a sample fails the lowest named grade. This label varies between grain types and is stored here so consumers can accurately describe the column in their own interfaces.

```json
"fallthrough_label": "Grade, if specs for CW Feed not met"
```

For grains where the source table has no such column (e.g. Chickpeas Standard of Quality), this is `null`.

---

### `grade_floor_rules`

**Type:** array of floor rule objects  
**Required:** yes (may be an empty array)

Rules that set a minimum grade floor for specific downgrade accounts. These override the normal grading logic: even if a sample would otherwise be graded lower based on its factor measurements, the floor rule prevents it from going below the specified grade for that specific reason.

Each floor rule object contains:

| Field | Type | Description |
|---|---|---|
| `account` | string | The grading account (reason) this floor applies to |
| `floor_grade` | string | The lowest grade that can be assigned on this account |
| `note` | string | The verbatim CGC statement establishing this rule |

```json
"grade_floor_rules": [
  {
    "account": "mildew",
    "floor_grade": "No. 3 CWRS",
    "note": "Samples of CWRS will be graded no lower than No. 3 CWRS on account of mildew"
  }
]
```

An empty array (`[]`) means no floor rules apply to this grain class.

**Important:** Grade floor rules take precedence over factor threshold outcomes. See [Grade floor rules and precedence](#grade-floor-rules-and-precedence) in the Special values section.

---

### `grades`

**Type:** array of strings  
**Required:** yes

The named grades for this grain class, in order from highest quality to lowest. The final entry is typically the catch-all feed or lowest grade.

```json
"grades": ["No. 1 CWRS", "No. 2 CWRS", "No. 3 CWRS", "CW Feed"]
```

These strings are the exact keys used in all `thresholds` objects throughout the record. A consumer can use this array to iterate grades in quality order without parsing threshold keys.

Note: the final grade (e.g. `"CW Feed"`) is a catch-all tier — samples are assigned this grade when they fail all numbered grade thresholds but still meet minimum feed requirements. It is not a grade a producer would typically target. See `fallthrough_label` for what happens when a sample fails even this grade.

---

### `factor_groups`

**Type:** array of factor group objects  
**Required:** yes

The grading factors organized into sub-tables, preserving the structure of the CGC source table. Each group represents a distinct section of the grade determination table.

Each factor group object contains:

| Field | Type | Description |
|---|---|---|
| `group_id` | string | Machine-readable identifier for this group |
| `group_label` | string | The section heading as it appears in the CGC source table |
| `factors` | array | The grading factors in this group; see [Factor fields](#factor-fields) |

```json
{
  "group_id": "foreign_material",
  "group_label": "Foreign material",
  "factors": [ ]
}
```

Group naming is not standardized across grain types — it reflects what the CGC uses for each grain. Common group IDs in v1:

| group_id | Appears in |
|---|---|
| `standard_of_quality` | All grains |
| `foreign_material` | All grains |
| `grading_factors` | Wheat classes |
| `damage` | Canola, Barley, Corn, Soybeans |
| `other_factors` | Soybeans |
| `foreign_material_and_damage` | Beans (future) |

Factors within a group are ordered to match the original CGC table row order.

---

### `footnotes`

**Type:** object (string keys, string values) or null  
**Required:** no

Footnotes from the CGC source table that are referenced by individual factors. Keys are footnote identifiers (e.g. `"fnt1"`); values are the full footnote text.

```json
"footnotes": {
  "fnt1": "See Frost and Mildew for applicable standard",
  "fnt2": "See working tolerance for Wheats of Other Classes or Varieties"
}
```

Factors reference footnotes via their `footnote_ref` field. `null` means no footnotes exist for this grain class.

---

## Factor fields

A factor is a single grading criterion within a factor group. It defines what is being measured, how it is measured, and what the consequences are for each grade level.

---

### `factor_id`

**Type:** string  
**Required:** yes

A machine-readable identifier for this factor, unique within the grain record. Derived from the factor label using snake_case. Used in `aggregates` arrays to reference sibling factors.

```json
"factor_id": "fusarium_damage"
```

---

### `factor_label`

**Type:** string  
**Required:** yes

The factor name exactly as it appears in the CGC source table, including any units or qualifiers in the label itself.

```json
"factor_label": "Fusarium damage"
```

```json
"factor_label": "Total % Shrunken and broken"
```

```json
"factor_label": "Binburnt, severely mildewed, rotted, mouldy"
```

---

### `unit`

**Type:** string or null  
**Required:** no

The unit of measurement for this factor's threshold values.

```json
"unit": "%"
```

```json
"unit": "kg/hL"
```

`null` for qualitative factors (e.g. Degree of soundness, Variety) that have no numeric unit.

---

### `unit_alt`

**Type:** string or null  
**Required:** no

A secondary unit of measurement used when the CGC table expresses thresholds in two units simultaneously. Present only for test weight factors, which are expressed in both kg/hL and g/0.5L.

```json
"unit": "kg/hL",
"unit_alt": "g/0.5L"
```

When `unit_alt` is present, each threshold object will have both a `value` (in the primary unit) and a `value_alt` (in the alternate unit). `null` in all other cases.

---

### `threshold_direction`

**Type:** string (enum) or null  
**Required:** no

Indicates whether the threshold is a ceiling the sample must stay at or below, or a floor the sample must meet or exceed.

| Value | Description |
|---|---|
| `"maximum"` | The sample value must not exceed this threshold |
| `"minimum"` | The sample value must meet or exceed this threshold |
| `null` | No directional threshold applies — factor is qualitative |

```json
"threshold_direction": "maximum"
```

`null` is intentional and not missing data. It appears on qualitative factors such as Degree of soundness and Variety, where the CGC specifies a text description rather than a numeric limit. There is no meaningful direction for a qualitative threshold. See [threshold_direction: null](#threshold_direction-null) in the Special values section.

---

### `is_aggregate`

**Type:** boolean  
**Required:** yes

When `true`, this factor represents a combined total of two or more sibling factors. The `aggregates` field lists which factor IDs contribute to this total.

```json
"is_aggregate": true
```

See [Aggregate factors](#aggregate-factors-is_aggregate-and-aggregates) in the Special values section for guidance on how to use this field.

---

### `aggregates`

**Type:** array of strings, or null  
**Required:** no

Lists the `factor_id` values of the sibling factors that are combined to produce this aggregate total. Present only when `is_aggregate` is `true`; `null` otherwise.

```json
"is_aggregate": true,
"aggregates": ["shrunken", "broken"]
```

This means the `total_shrunken_and_broken` factor's threshold applies to the sum of the `shrunken` and `broken` factor values. A sample could pass both individual factor thresholds while still failing the aggregate total threshold.

---

### `footnote_ref`

**Type:** string or null  
**Required:** no

References a footnote in the grain record's `footnotes` object. The value is the footnote key (e.g. `"fnt1"`). Indicates that the CGC source table marks this factor with a footnote that affects how it should be interpreted.

```json
"footnote_ref": "fnt1"
```

Consumers should surface the referenced footnote text alongside this factor where clarity is important. `null` when no footnote applies to this factor.

---

### `thresholds`

**Type:** object  
**Required:** yes

The per-grade threshold values for this factor. Keys are grade name strings exactly matching the entries in the grain record's `grades` array. Values are threshold objects — see [Threshold fields](#threshold-fields) below.

```json
"thresholds": {
  "No. 1 CWRS": { "value_type": "numeric", "value": 0.04, "value_alt": null, "threshold_note": null },
  "No. 2 CWRS": { "value_type": "numeric", "value": 0.04, "value_alt": null, "threshold_note": null },
  "No. 3 CWRS": { "value_type": "numeric", "value": 0.04, "value_alt": null, "threshold_note": null },
  "CW Feed":    { "value_type": "numeric", "value": 0.10, "value_alt": null, "threshold_note": null }
}
```

Every grade in the grain record's `grades` array will have a corresponding key in this object.

---

### `fallthrough`

**Type:** string, array of condition objects, or null  
**Required:** no

Specifies the grade assigned to a sample when its measured value for this factor exceeds the threshold of every named grade — including the lowest catch-all grade. Three possible shapes:

**Simple string** — a single outcome applies regardless of the measured value or region:

```json
"fallthrough": "Wheat, Sample CW Account Ergot"
```

**Array of condition objects** — the outcome depends on the measured value and/or the production region. Each condition object contains:

| Field | Type | Description |
|---|---|---|
| `condition` | string | The measured value condition that triggers this outcome |
| `region` | string or null | `"west"`, `"east"`, or `null` if region-agnostic |
| `grade` | string | The grade assigned when this condition is met |

```json
"fallthrough": [
  { "condition": "<= 2.5%", "region": "west", "grade": "Canola, Rejected (grade) Account Stones" },
  { "condition": "<= 2.5%", "region": "east", "grade": "Canola, Sample Canada Account Stones" },
  { "condition": "> 2.5%",  "region": null,   "grade": "Canola, Sample Salvage" }
]
```

```json
"fallthrough": [
  { "condition": "<= 10%", "region": null, "grade": "Wheat, Sample CW Account Fusarium Damage" },
  { "condition": "> 10%",  "region": null, "grade": "Wheat, Commercial Salvage" }
]
```

**null** — no specific downgrade outcome is defined for this factor in the CGC source table. This occurs for factors where exceeding the threshold rolls the sample into a broader outcome handled at the grain level (e.g. the sample simply fails to grade) or where no fallthrough column entry exists.

```json
"fallthrough": null
```

See [fallthrough: string vs array](#fallthrough-string-vs-array) in the Special values section for fuller guidance.

---

## Threshold fields

A threshold object describes the value at which a factor passes or fails for a specific grade.

---

### `value_type`

**Type:** string (enum)  
**Required:** yes

Describes the nature of the threshold value and how it should be interpreted.

| Value | Description |
|---|---|
| `"numeric"` | A number. Compare the sample's measured value against `value` using `threshold_direction`. |
| `"no_limit"` | No ceiling or floor applies at this grade level. The factor is not a limiting factor for this grade. |
| `"qualitative"` | A text description. The CGC specifies a prose standard rather than a numeric limit. Not directly machine-comparable. |
| `"qualitative_judgment"` | A text instruction that replaces a numeric threshold at a specific grade, indicating the grader must exercise judgment. |
| `"not_applicable"` | This factor does not apply at this grade level at all — it is not assessed. |

See [no_limit vs not_applicable](#no_limit-vs-not_applicable) in the Special values section for the important distinction between the last two numeric-adjacent types.

---

### `value`

**Type:** number, string, or null  
**Required:** no

The threshold value. Its type depends on `value_type`:

| value_type | value type | Notes |
|---|---|---|
| `"numeric"` | number | The threshold number in the primary unit |
| `"no_limit"` | null | No value; limit does not exist |
| `"qualitative"` | string | The full CGC prose description |
| `"qualitative_judgment"` | string | The CGC instruction text (e.g. `"Consider overall appearance"`) |
| `"not_applicable"` | null | No value; factor does not apply |

```json
{ "value_type": "numeric", "value": 0.04 }
{ "value_type": "no_limit", "value": null }
{ "value_type": "qualitative", "value": "Reasonably well matured, reasonably free from damaged kernels" }
{ "value_type": "qualitative_judgment", "value": "Consider overall appearance" }
{ "value_type": "not_applicable", "value": null }
```

---

### `value_alt`

**Type:** number or null  
**Required:** no

The threshold value expressed in the secondary unit (`unit_alt`). Present only on test weight thresholds, where the CGC expresses the same limit in both kg/hL and g/0.5L. `null` in all other cases.

```json
{ "value_type": "numeric", "value": 75, "value_alt": 365 }
```

This means the No. 1 CWRS test weight minimum is 75 kg/hL, which is equivalent to 365 g/0.5L.

---

### `threshold_note`

**Type:** string or null  
**Required:** no

A qualifying annotation that modifies how the threshold value should be interpreted, without replacing the value itself. Used when the CGC adds a condition or exclusion to a threshold that cannot be expressed as a number alone.

```json
{ "value_type": "no_limit", "value": null, "threshold_note": "within broken tolerances" }
{ "value_type": "numeric", "value": 8, "threshold_note": "excluding frost" }
```

`null` in the vast majority of cases. When present, the note is essential context — a consumer should not ignore it.

---

## Special values

### `threshold_direction: null`

`threshold_direction` is `null` on any factor where the CGC specifies a text description instead of a numeric limit. This is intentional and not a data error.

The most common examples are Degree of soundness and Variety. For these factors, the CGC defines what a sample must look like or be, not a number it must exceed or fall below. There is no meaningful "maximum" or "minimum" for a prose description.

Consumers building a grading calculator should treat `threshold_direction: null` factors as informational — they cannot be automatically compared against a sample measurement. A grader must assess them visually or by knowledge of the variety and record the resulting grade tier directly.

---

### `no_limit` vs `not_applicable`

These two `value_type` values look similar but represent meaningfully different situations:

**`no_limit`** means the factor is assessed for this grade, but there is no ceiling or floor — the sample cannot fail this grade on account of this factor alone. The factor still applies; it just has no threshold.

Example: Dark immature kernels in CWRS CW Feed have `value_type: "no_limit"`. A sample graded CW Feed can contain any percentage of dark immature kernels — this factor will not further downgrade it. But the factor is still a real consideration at No. 1, 2, and 3.

**`not_applicable`** means the factor is not assessed at this grade level at all. It is not that the tolerance is unlimited — the factor simply does not exist for this grade.

Example: The Wrinkled factor in Red Lentils has `value_type: "not_applicable"` at Extra No. 3 and No. 3. Wrinkled is a quality characteristic that only distinguishes the top two grades. At lower grades, it is not evaluated.

**For consumers:** `no_limit` means "no threshold to fail"; `not_applicable` means "do not assess this factor for this grade." These require different handling in a grading tool.

---

### `fallthrough`: string vs array

The `fallthrough` field has two distinct shapes because CGC downgrade outcomes are sometimes simple and sometimes conditional.

**Simple string** is used when one outcome applies unconditionally — regardless of how far the sample exceeds the threshold, or where it was grown:

```json
"fallthrough": "Wheat, Sample CW Account Ergot"
```

**Array of condition objects** is used in two situations:

*Regional branching* — the outcome differs between western and eastern Canada for the same threshold breach. Western Canadian grain above the stones threshold is assigned a "Rejected" grade (the producer can reclean and resubmit); eastern Canadian grain receives a "Sample" grade (a harder outcome). The condition `"<= 2.5%"` applies to the stones percentage itself, not to the grade:

```json
"fallthrough": [
  { "condition": "<= 2.5%", "region": "west", "grade": "Canola, Rejected (grade) Account Stones" },
  { "condition": "<= 2.5%", "region": "east", "grade": "Canola, Sample Canada Account Stones" },
  { "condition": "> 2.5%",  "region": null,   "grade": "Canola, Sample Salvage" }
]
```

*Value-tiered branching* — the outcome escalates based on how severely the threshold is exceeded. Fusarium damage uses this: moderate excess produces a recoverable outcome; severe excess produces a salvage outcome:

```json
"fallthrough": [
  { "condition": "<= 10%", "region": null, "grade": "Wheat, Sample CW Account Fusarium Damage" },
  { "condition": "> 10%",  "region": null, "grade": "Wheat, Commercial Salvage" }
]
```

When `region` is `null` within a condition object, that outcome applies regardless of region.

**For consumers:** Evaluate conditions in order. Apply the first condition that matches the sample's measured value and region.

---

### Aggregate factors (`is_aggregate` and `aggregates`)

Some factors in the CGC tables are totals of two or more other factors in the same group. These aggregate factors exist because a sample can pass each individual sub-factor threshold while still failing the combined total.

Example: A CWRS sample might have 4% shrunken (under the 4% limit) and 5% broken (under the 5% No. 1 limit) — but 9% total shrunken and broken, which exceeds the 7% No. 1 total limit.

When `is_aggregate` is `true`:
- `aggregates` lists the `factor_id` values of the contributing factors
- The threshold in this factor applies to the **sum** of those contributing factors' measurements
- A sample must pass both the individual factor thresholds **and** the aggregate threshold to achieve a given grade

**For consumers building a grading tool:** Evaluate individual factors first, then evaluate aggregate factors against the sum of the referenced measurements. A sample's grade is determined by the most restrictive factor — whichever individual or aggregate factor assigns the lowest grade wins.

---

### Grade floor rules and precedence

`grade_floor_rules` are CGC rules that prevent a sample from being graded below a certain level for a specific reason, even when its factor measurements would otherwise place it lower.

Example: CWRS samples will be graded no lower than No. 3 CWRS on account of mildew. If a CWRS sample has mildew characteristics that would normally produce a CW Feed grade, the floor rule overrides the factor outcome and the sample is assigned No. 3 CWRS instead.

**Precedence:** Grade floor rules take effect **after** all factor thresholds have been evaluated. The process is:

1. Evaluate all factors and determine the grade each factor would assign
2. The lowest grade from step 1 is the preliminary grade
3. Check whether any `grade_floor_rules` apply to the account (reason) that produced the preliminary grade
4. If a floor rule applies, the final grade is the floor grade — not the preliminary grade

**For consumers:** Floor rules are account-specific. A floor that applies "on account of mildew" does not protect a sample from being downgraded on account of light weight or sprouting. Check the `account` field of each rule against the reason for downgrade before applying the floor.

When `grade_floor_rules` is an empty array, no floor rules apply and the lowest factor-determined grade is final.
