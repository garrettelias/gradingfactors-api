"""
HTTP fetch with rate limiting and retry logic.

All fetches go through fetch(). A module-level timestamp enforces a minimum
2-second gap between consecutive calls regardless of where in the scraper
the call originates.
"""
import time

import httpx

_MIN_DELAY = 2.0   # seconds between requests
_MAX_RETRIES = 3
_TIMEOUT = 30.0    # seconds

_state: dict = {"last_fetch_time": 0.0}


def fetch(url: str) -> str:
    """Fetch a URL and return the response body as text.

    Enforces a 2-second minimum gap between consecutive calls.
    Retries up to 3 times with exponential backoff (2s, 4s, 8s) on
    connection error or non-200 response.

    Raises RuntimeError after exhausting all retries.
    """
    elapsed = time.monotonic() - _state["last_fetch_time"]
    if elapsed < _MIN_DELAY:
        time.sleep(_MIN_DELAY - elapsed)

    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = httpx.get(url, follow_redirects=True, timeout=_TIMEOUT)
            _state["last_fetch_time"] = time.monotonic()
            if response.status_code == 200:
                return response.text
            raise httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            _state["last_fetch_time"] = time.monotonic()
            if attempt < _MAX_RETRIES - 1:
                backoff = 2 ** (attempt + 1)
                print(
                    f"  Fetch failed (attempt {attempt + 1}/{_MAX_RETRIES}): {exc}. "
                    f"Retrying in {backoff}s..."
                )
                time.sleep(backoff)

    raise RuntimeError(
        f"Failed to fetch {url} after {_MAX_RETRIES} attempts: {last_exc}"
    )
