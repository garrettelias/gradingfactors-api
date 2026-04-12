"""
Pytest tests for all three API endpoints.

All tests use FastAPI's TestClient with:
  - dependency_overrides to control auth (see conftest.py)
  - patch.object to replace the supabase client in each router module with a
    MagicMock shaped to return the data each test needs

No live database or network calls are made.
"""
import secrets
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import api.routers.changelog
import api.routers.grains
import api.routers.register

from tests.conftest import TEST_KEY

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

MOCK_GRAIN_ROWS = [
    {
        "grain_id": "CWRS",
        "grain_name": "Canada Western Red Spring",
        "kind": "wheat",
        "region": "western",
        "use_class": None,
        "effective_crop_year": "2025/26",
        "coverage_status": "complete",
        "grades": ["No. 1 CWRS", "No. 2 CWRS", "No. 3 CWRS", "CW Feed"],
    },
    {
        "grain_id": "CANOLA",
        "grain_name": "Canola, Canada (CAN)",
        "kind": "oilseed",
        "region": None,
        "use_class": None,
        "effective_crop_year": "2025/26",
        "coverage_status": "complete",
        "grades": ["No. 1 Canada", "No. 2 Canada", "No. 3 Canada"],
    },
]

_GRAIN_UUID = "00000000-0000-0000-0000-000000000001"
_GROUP_UUID = "00000000-0000-0000-0000-000000000002"

MOCK_GRAIN_CLASS = {
    "id": _GRAIN_UUID,
    "grain_id": "CWRS",
    "grain_name": "Canada Western Red Spring",
    "kind": "wheat",
    "region": "western",
    "use_class": None,
    "variety_tracks": None,
    "colour_modifier": False,
    "size_modifier": False,
    "source_url": (
        "https://www.grainscanada.gc.ca/en/grain-quality/official-grain-grading-guide"
        "/04-wheat/primary-grade-determination/cwrs-wheat.html"
    ),
    "effective_crop_year": "2025/26",
    "last_scraped": "2026-04-11T00:00:00+00:00",
    "coverage_status": "complete",
    "fallthrough_label": "Grade, if specs for CW Feed not met",
    "grade_floor_rules": [
        {
            "account": "mildew",
            "floor_grade": "No. 3 CWRS",
            "note": "Samples graded no lower than No. 3 CWRS on account of mildew.",
        }
    ],
    "grades": ["No. 1 CWRS", "No. 2 CWRS", "No. 3 CWRS", "CW Feed"],
    "footnotes": {"fnt1": "See Frost and Mildew for applicable standard"},
}

MOCK_FACTOR_GROUP = {
    "id": _GROUP_UUID,
    "grain_class_id": _GRAIN_UUID,
    "group_id": "foreign_material",
    "group_label": "Foreign material",
    "sort_order": 0,
}

MOCK_FACTOR = {
    "id": "00000000-0000-0000-0000-000000000003",
    "factor_group_id": _GROUP_UUID,
    "factor_id": "ergot",
    "factor_label": "Ergot",
    "unit": "%",
    "unit_alt": None,
    "threshold_direction": "maximum",
    "is_aggregate": False,
    "aggregates": None,
    "footnote_ref": None,
    "thresholds": {
        "No. 1 CWRS": {"value_type": "numeric", "value": 0.04, "value_alt": None, "threshold_note": None},
        "No. 2 CWRS": {"value_type": "numeric", "value": 0.04, "value_alt": None, "threshold_note": None},
        "No. 3 CWRS": {"value_type": "numeric", "value": 0.04, "value_alt": None, "threshold_note": None},
        "CW Feed": {"value_type": "numeric", "value": 0.10, "value_alt": None, "threshold_note": None},
    },
    "fallthrough": "Wheat, Sample CW Account Ergot",
    "sort_order": 0,
}

MOCK_CHANGELOG_ENTRIES = [
    {
        "id": "00000000-0000-0000-0000-000000000010",
        "crop_year": "2025/26",
        "effective_date": "2025-08-01",
        "grain_ids_affected": ["CWRS"],
        "summary": "Initial data load for 2025/26 crop year.",
        "source_memo_url": None,
        "created_at": "2025-08-01T00:00:00Z",
    },
    {
        "id": "00000000-0000-0000-0000-000000000011",
        "crop_year": "2025/26",
        "effective_date": "2025-09-01",
        "grain_ids_affected": ["CANOLA"],
        "summary": "Initial canola data.",
        "source_memo_url": None,
        "created_at": "2025-09-01T00:00:00Z",
    },
]

# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

_BUILDER_METHODS = (
    "table", "select", "eq", "neq", "in_", "order", "limit",
    "maybe_single", "single", "contains", "upsert", "insert", "update", "delete",
)


def _make_mock(*results):
    """Return a supabase-shaped MagicMock whose execute() yields results in call order.

    All builder methods (table, select, eq, …) return the same mock so the
    fluent chain always resolves to the same object. execute() uses side_effect
    to return results[0] on the first call, results[1] on the second, etc.
    """
    m = MagicMock()
    for method in _BUILDER_METHODS:
        getattr(m, method).return_value = m
    m.execute.side_effect = list(results)
    return m


def _make_repeating_mock(result):
    """Return a mock whose execute() always returns the same result.

    Used when a test needs an unbounded number of identical execute() calls
    (e.g. rate-limit test making 100+ requests).
    """
    m = MagicMock()
    for method in _BUILDER_METHODS:
        getattr(m, method).return_value = m
    m.execute.return_value = result
    return m


@contextmanager
def _db(mock_sb):
    """Patch the supabase client in all router modules simultaneously."""
    with (
        patch.object(api.routers.grains, "supabase", mock_sb),
        patch.object(api.routers.changelog, "supabase", mock_sb),
        patch.object(api.routers.register, "supabase", mock_sb),
    ):
        yield mock_sb


# ---------------------------------------------------------------------------
# GET /api/grains
# ---------------------------------------------------------------------------

class TestListGrains:
    def test_happy_path(self, client):
        mock_sb = _make_mock(MagicMock(data=MOCK_GRAIN_ROWS))
        with _db(mock_sb):
            r = client.get("/api/grains", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 200
        body = r.json()
        assert body["schema_version"] == "1.0"
        assert body["count"] == 2
        assert len(body["grains"]) == 2
        assert body["grains"][0]["grain_id"] == "CWRS"

    def test_no_api_key_returns_401(self, client):
        r = client.get("/api/grains")
        assert r.status_code == 401

    def test_invalid_api_key_returns_401(self, client):
        r = client.get("/api/grains", headers={"X-API-Key": "gf_live_wrongkey"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/grains/{grain_id}
# ---------------------------------------------------------------------------

class TestGetGrain:
    def _grain_mock(self):
        return _make_mock(
            MagicMock(data=MOCK_GRAIN_CLASS),
            MagicMock(data=[MOCK_FACTOR_GROUP]),
            MagicMock(data=[MOCK_FACTOR]),
        )

    def test_happy_path(self, client):
        with _db(self._grain_mock()):
            r = client.get("/api/grains/CWRS", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 200
        body = r.json()
        assert body["schema_version"] == "1.0"
        assert body["grain_id"] == "CWRS"
        assert body["kind"] == "wheat"
        assert body["region"] == "western"
        assert len(body["factor_groups"]) == 1
        assert body["factor_groups"][0]["group_id"] == "foreign_material"
        assert body["factor_groups"][0]["factors"][0]["factor_id"] == "ergot"

    def test_case_insensitive(self, client):
        with _db(self._grain_mock()):
            r = client.get("/api/grains/cwrs", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 200
        assert r.json()["grain_id"] == "CWRS"

    def test_not_found(self, client):
        mock_sb = _make_mock(MagicMock(data=None))
        with _db(mock_sb):
            r = client.get("/api/grains/XYZ", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 404
        body = r.json()
        assert "XYZ" in body["error"]
        assert "GET /api/grains" in body["error"]

    def test_no_api_key_returns_401(self, client):
        r = client.get("/api/grains/CWRS")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/changelog
# ---------------------------------------------------------------------------

class TestChangelog:
    def test_happy_path(self, client):
        mock_sb = _make_mock(MagicMock(data=MOCK_CHANGELOG_ENTRIES))
        with _db(mock_sb):
            r = client.get("/api/changelog", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 200
        body = r.json()
        assert body["schema_version"] == "1.0"
        assert body["count"] == 2
        assert len(body["entries"]) == 2

    def test_grain_id_filter(self, client):
        mock_sb = _make_mock(MagicMock(data=[MOCK_CHANGELOG_ENTRIES[0]]))
        with _db(mock_sb):
            r = client.get("/api/changelog?grain_id=CWRS", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 200
        assert r.json()["count"] == 1
        mock_sb.contains.assert_called_once_with("grain_ids_affected", ["CWRS"])

    def test_limit_param(self, client):
        mock_sb = _make_mock(MagicMock(data=[MOCK_CHANGELOG_ENTRIES[0]]))
        with _db(mock_sb):
            r = client.get("/api/changelog?limit=5", headers={"X-API-Key": TEST_KEY})
        assert r.status_code == 200
        assert r.json()["count"] <= 5
        mock_sb.limit.assert_called_once_with(5)

    def test_no_api_key_returns_401(self, client):
        r = client.get("/api/changelog")
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/register
# ---------------------------------------------------------------------------

class TestRegister:
    def test_happy_path(self, client):
        mock_sb = _make_mock(MagicMock(data=[{"id": "00000000-0000-0000-0000-000000000099"}]))
        with _db(mock_sb):
            r = client.post("/api/register", json={"email": "dev@example.com"})
        assert r.status_code == 200
        body = r.json()
        assert body["api_key"].startswith("gf_live_")
        assert body["email"] == "dev@example.com"
        assert "not be shown again" in body["message"]

    def test_raw_key_is_never_stored(self, client):
        """The insert payload must contain a SHA-256 hash, not the raw key."""
        mock_sb = _make_mock(MagicMock(data=[{"id": "00000000-0000-0000-0000-000000000099"}]))
        with _db(mock_sb):
            r = client.post("/api/register", json={"email": "sec@example.com"})
        assert r.status_code == 200
        api_key = r.json()["api_key"]
        stored_hash = mock_sb.insert.call_args[0][0]["key_hash"]
        assert stored_hash != api_key, "Raw API key must not be stored"
        assert len(stored_hash) == 64, "SHA-256 hex digest must be 64 characters"

    def test_invalid_email_returns_422(self, client):
        r = client.post("/api/register", json={"email": "not-an-email"})
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimit:
    def test_rate_limit_triggers_at_101(self, rate_limit_client, monkeypatch):
        # Generate a fresh key so this test's window starts at zero regardless
        # of how many times the test suite has been run in this process.
        key = "gf_live_" + secrets.token_hex(16)

        mock_sb = _make_repeating_mock(MagicMock(data=MOCK_GRAIN_ROWS))
        monkeypatch.setattr(api.routers.grains, "supabase", mock_sb)

        for i in range(100):
            r = rate_limit_client.get(
                "/api/grains", headers={"X-API-Key": key}
            )
            assert r.status_code == 200, f"Request {i + 1} unexpectedly failed: {r.status_code}"

        r = rate_limit_client.get("/api/grains", headers={"X-API-Key": key})
        assert r.status_code == 429
        assert "Retry-After" in r.headers
        assert "Rate limit" in r.json()["error"]
