from fastapi import APIRouter, Depends, Query

from api.db import supabase
from api.dependencies import verify_api_key
from api.models.changelog import ChangelogEntry, ChangelogResponse

router = APIRouter()


@router.get("/changelog", response_model=ChangelogResponse)
def get_changelog(
    grain_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    _key: str = Depends(verify_api_key),
):
    query = (
        supabase.table("changelog")
        .select("*")
        .order("effective_date", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
    )

    if grain_id:
        query = query.contains("grain_ids_affected", [grain_id])

    result = query.execute()
    entries = [ChangelogEntry(**row) for row in result.data]
    return ChangelogResponse(count=len(entries), entries=entries)
