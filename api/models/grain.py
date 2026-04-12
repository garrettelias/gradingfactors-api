from datetime import datetime

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "1.0"


class GradeFloorRule(BaseModel):
    account: str
    floor_grade: str
    note: str


class VarietyTrack(BaseModel):
    track_id: str
    grades: list[str]


class ThresholdObject(BaseModel):
    value_type: str
    value: float | str | None = None
    value_alt: float | None = None
    threshold_note: str | None = None


class FallthroughCondition(BaseModel):
    condition: str
    region: str | None
    grade: str


class FactorModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    factor_id: str
    factor_label: str
    unit: str | None
    unit_alt: str | None
    threshold_direction: str | None
    is_aggregate: bool
    aggregates: list[str] | None
    footnote_ref: str | None
    thresholds: dict[str, ThresholdObject]
    fallthrough: str | list[FallthroughCondition] | None


class FactorGroupModel(BaseModel):
    group_id: str
    group_label: str
    factors: list[FactorModel]


class GrainSummary(BaseModel):
    grain_id: str
    grain_name: str
    kind: str
    region: str | None
    use_class: str | None
    effective_crop_year: str
    coverage_status: str
    grades: list[str]


class GrainsListResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    count: int
    grains: list[GrainSummary]


class GrainDetailResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    grain_id: str
    grain_name: str
    kind: str
    region: str | None
    use_class: str | None
    variety_tracks: list[VarietyTrack] | None
    colour_modifier: bool
    size_modifier: bool
    source_url: str
    effective_crop_year: str
    last_scraped: datetime
    coverage_status: str
    fallthrough_label: str | None
    grade_floor_rules: list[GradeFloorRule]
    grades: list[str]
    factor_groups: list[FactorGroupModel]
    footnotes: dict[str, str] | None
