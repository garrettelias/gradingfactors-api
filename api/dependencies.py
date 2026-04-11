import hashlib

from fastapi import Header, HTTPException
from fastapi.security import APIKeyHeader

from api.db import supabase

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_UNAUTHORIZED = HTTPException(status_code=401, detail="Invalid or missing API key.")


def verify_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> str:
    if not x_api_key:
        raise _UNAUTHORIZED

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    result = (
        supabase.table("api_keys")
        .select("id")
        .eq("key_hash", key_hash)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )

    if not result.data:
        raise _UNAUTHORIZED

    # Update last_used_at without blocking the response
    supabase.table("api_keys").update({"last_used_at": "now()"}).eq(
        "id", result.data["id"]
    ).execute()

    return x_api_key
