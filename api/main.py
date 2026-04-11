from fastapi import APIRouter, Depends, FastAPI

from api.dependencies import verify_api_key
from api.routers import register

app = FastAPI(
    title="Grading Factors API",
    description="Machine-readable CGC grain grade determinant tables.",
    version="1.0.0",
)

v1 = APIRouter(prefix="/api/v1")

v1.include_router(register.router)


@v1.get("/ping", include_in_schema=False)
def ping(_key: str = Depends(verify_api_key)):
    return {"authenticated": True}


app.include_router(v1)


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}
