from datetime import date

from pydantic import BaseModel, ConfigDict

SCHEMA_VERSION = "1.0"


class ChangelogEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    crop_year: str
    effective_date: date
    grain_ids_affected: list[str]
    summary: str
    source_memo_url: str | None


class ChangelogResponse(BaseModel):
    schema_version: str = SCHEMA_VERSION
    count: int
    entries: list[ChangelogEntry]
