import hashlib
import secrets

from fastapi import APIRouter, HTTPException

from api.db import supabase
from api.models.register import RegisterRequest, RegisterResponse

router = APIRouter()


@router.post("/register", response_model=RegisterResponse)
def register(body: RegisterRequest):
    """
    Generate a new API key linked to the provided email address.

    The raw key is returned once and never stored — save it immediately.
    Pass the key as the X-API-Key header on all other requests.
    """
    api_key = "gf_live_" + secrets.token_hex(16)
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()

    result = (
        supabase.table("api_keys")
        .insert({"key_hash": key_hash, "email": str(body.email)})
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to register API key.")

    return RegisterResponse(
        api_key=api_key,
        email=str(body.email),
        message="Store this key securely — it will not be shown again.",
    )
