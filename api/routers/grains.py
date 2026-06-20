from fastapi import APIRouter, Depends
from starlette.responses import JSONResponse

from api.db import supabase
from api.dependencies import verify_api_key
from api.models.grain import (
    FactorGroupModel,
    FactorModel,
    GrainDetailResponse,
    GrainSummary,
    GrainsListResponse,
)

router = APIRouter()


@router.get("/grains", response_model=GrainsListResponse)
def list_grains(_key: str = Depends(verify_api_key)):
    """
    Return a summary of all available grain classes.

    Each item includes grain_id, grain_name, kind, region, use_class,
    effective_crop_year, coverage_status, and the ordered grades array.
    Factor data is not included — use GET /api/grains/{grain_id} for the full record.
    """
    result = (
        supabase.table("grain_classes")
        .select(
            "grain_id, grain_name, kind, region, use_class, "
            "effective_crop_year, coverage_status, grades"
        )
        .execute()
    )
    grains = [GrainSummary(**row) for row in result.data]
    return GrainsListResponse(count=len(grains), grains=grains)


@router.get("/grains/{grain_id}")
def get_grain(grain_id: str, _key: str = Depends(verify_api_key)):
    """
    Return the full grading factor table for a single grain class.

    Includes all factor groups, factors with per-grade thresholds, grade floor
    rules, footnotes, and grain metadata. grain_id is case-insensitive.
    Returns 404 with a helpful message if the grain_id is not found.
    """
    # Normalize to uppercase — all grain_ids in the DB are uppercase.
    # Using eq() rather than ilike() avoids LIKE wildcard issues with underscores
    # (e.g. BARLEY_GP contains a _ which is a LIKE wildcard character).
    grain_result = (
        supabase.table("grain_classes")
        .select("*")
        .eq("grain_id", grain_id.upper())
        .maybe_single()
        .execute()
    )

    if not grain_result.data:
        return JSONResponse(
            status_code=404,
            content={
                "error": (
                    f"Grain class '{grain_id}' not found. "
                    "Call GET /api/grains for available grain IDs."
                )
            },
        )

    grain = grain_result.data

    # Fetch factor groups ordered by sort_order
    groups_result = (
        supabase.table("factor_groups")
        .select("*")
        .eq("grain_class_id", grain["id"])
        .order("sort_order")
        .execute()
    )
    groups = groups_result.data

    # Fetch all factors for these groups in one query
    factors_by_group: dict[str, list] = {g["id"]: [] for g in groups}
    if groups:
        factors_result = (
            supabase.table("factors")
            .select("*")
            .in_("factor_group_id", [g["id"] for g in groups])
            .order("sort_order")
            .execute()
        )
        for factor in factors_result.data:
            factors_by_group[factor["factor_group_id"]].append(factor)

    factor_groups = [
        FactorGroupModel(
            group_id=g["group_id"],
            group_label=g["group_label"],
            factors=[FactorModel(**f) for f in factors_by_group[g["id"]]],
        )
        for g in groups
    ]

    return GrainDetailResponse(
        grain_id=grain["grain_id"],
        grain_name=grain["grain_name"],
        kind=grain["kind"],
        region=grain["region"],
        use_class=grain["use_class"],
        variety_tracks=grain["variety_tracks"],
        colour_modifier=grain["colour_modifier"],
        size_modifier=grain["size_modifier"],
        source_url=grain["source_url"],
        effective_crop_year=grain["effective_crop_year"],
        last_scraped=grain["last_scraped"],
        coverage_status=grain["coverage_status"],
        fallthrough_label=grain["fallthrough_label"],
        grade_floor_rules=grain["grade_floor_rules"],
        grades=grain["grades"],
        factor_groups=factor_groups,
        footnotes=grain["footnotes"],
    )
