import time
from collections import defaultdict, deque

from fastapi import APIRouter, FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from api.routers import changelog, grains, register

_RATE_LIMIT = 100
_RATE_WINDOW = 3600  # seconds
_EXEMPT_PATHS = {"/api/register", "/health"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    # NOTE: This in-memory store is only suitable for single-instance deployments.
    # If the app is scaled to multiple instances, replace with a shared store (e.g. Redis).
    def __init__(self, app):
        super().__init__(app)
        self._windows: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            return await call_next(request)

        now = time.time()
        window = self._windows[api_key]

        while window and window[0] <= now - _RATE_WINDOW:
            window.popleft()

        if len(window) >= _RATE_LIMIT:
            retry_after = int(_RATE_WINDOW - (now - window[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded. 100 requests per hour per API key."},
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        return await call_next(request)


app = FastAPI(
    title="Grading Factors API",
    description="Machine-readable CGC grain grade determinant tables.",
    version="1.0.0",
)

app.add_middleware(RateLimitMiddleware)

api_router = APIRouter(prefix="/api")
api_router.include_router(register.router)
api_router.include_router(grains.router)
api_router.include_router(changelog.router)

app.include_router(api_router)


@app.get("/health", include_in_schema=False)
def health_check():
    return {"status": "ok"}
