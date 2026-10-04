"""Live API tests for endpoints captured on 2026-10-04 (see api-tests/network-contract.md).

Every assertion matches what discovery observed on that date; nothing is assumed.
Config comes from .env: RHOMBUS_API_BASE, RHOMBUS_BEARER_TOKEN, RHOMBUS_ORG_ID,
RHOMBUS_PROJECT_ID. Tests skip if any is missing. The bearer token is never printed:
assertion messages include only status codes and response keys, never request headers.

A 401 on a positive test means the DevTools token has expired (they are short-lived), so
those tests skip with a clear message instead of reporting a platform failure.

Run: pytest api-tests -m live
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

pytestmark = pytest.mark.live

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")

REQUIRED = ["RHOMBUS_API_BASE", "RHOMBUS_BEARER_TOKEN", "RHOMBUS_ORG_ID", "RHOMBUS_PROJECT_ID"]
TIMEOUT = 30
UNAUTHORIZED_BODY = {"detail": "Unauthorized"}  # observed for no token and "Bearer invalid"

PROFILE_KEYS = {"first_name", "last_name"}
CREDITS_KEYS = {"balance", "tier_info", "topup_packages"}
BALANCE_KEYS = {"balance", "subscription_credits", "purchased_credits", "tier",
                "monthly_allocation", "topup_enabled", "is_unlimited", "usage_this_period"}
DATASET_ITEM_KEYS = {
    "is_temp", "id", "organization", "title", "description", "file", "file_size",
    "content_type", "is_local", "is_sample", "client_id", "client_secret", "object_url",
    "user_id", "project_id", "data_array", "transformations", "parameters",
}


@pytest.fixture(scope="module")
def env() -> dict[str, str]:
    missing = [n for n in REQUIRED if not os.environ.get(n)]
    if missing:
        pytest.skip(f"missing in .env: {', '.join(missing)}")
    return {n: os.environ[n] for n in REQUIRED}


def url(env: dict[str, str], name: str) -> str:
    paths = {
        "profile": "/api/accounts/users/profile",
        "credits": "/api/accounts/users/credits",
        "datasets": f"/api/dataset/analyzer/v2/projects/{env['RHOMBUS_PROJECT_ID']}/datasets",
    }
    return env["RHOMBUS_API_BASE"].rstrip("/") + paths[name]


def get(env: dict[str, str], name: str, authorization: str | None) -> requests.Response:
    headers = {"x-org-id": env["RHOMBUS_ORG_ID"]}
    if authorization is not None:
        headers["Authorization"] = authorization
    return requests.get(url(env, name), headers=headers, timeout=TIMEOUT)


def get_authorised(env: dict[str, str], name: str) -> requests.Response:
    resp = get(env, name, f"Bearer {env['RHOMBUS_BEARER_TOKEN']}")
    if resp.status_code == 401:
        pytest.skip("RHOMBUS_BEARER_TOKEN was rejected (401): the DevTools token has most "
                    "likely expired. Copy a fresh one into .env and re-run.")
    return resp


# ---------------------------------------------------------------- positive


def test_profile_returns_observed_keys(env):
    """GET /api/accounts/users/profile with a valid token -> 200 (captured 2026-10-04)."""
    resp = get_authorised(env, "profile")
    assert resp.status_code == 200, resp.status_code
    body = resp.json()
    assert set(body) == PROFILE_KEYS, sorted(body)
    assert all(v is None or isinstance(v, str) for v in body.values())


def test_credits_returns_observed_shape(env):
    """GET /api/accounts/users/credits with a valid token -> 200 (captured 2026-10-04)."""
    resp = get_authorised(env, "credits")
    assert resp.status_code == 200, resp.status_code
    body = resp.json()
    assert set(body) == CREDITS_KEYS, sorted(body)
    assert set(body["balance"]) == BALANCE_KEYS, sorted(body["balance"])
    assert isinstance(body["balance"]["balance"], int)
    assert isinstance(body["topup_packages"], list)


def test_datasets_lists_uploaded_files(env):
    """GET /api/dataset/analyzer/v2/projects/{project_id}/datasets -> 200 (captured 2026-10-04).

    The list contains the From Device uploads; baseline.csv was observed in it.
    """
    resp = get_authorised(env, "datasets")
    assert resp.status_code == 200, resp.status_code
    items = resp.json()
    assert isinstance(items, list) and items
    for item in items:
        assert set(item) == DATASET_ITEM_KEYS, sorted(set(item) ^ DATASET_ITEM_KEYS)
        assert str(item["project_id"]) == env["RHOMBUS_PROJECT_ID"]
        assert item["file"] == item["title"]
        assert item["content_type"] == "text/csv"
    assert "baseline.csv" in {item["file"] for item in items}


def test_datasets_do_not_expose_client_credentials(env):
    """Datasets list: client_id / client_secret were present but empty (captured 2026-10-04).

    Guards against credential exposure in the listing. Only emptiness is checked; values
    are never printed.
    """
    items = get_authorised(env, "datasets").json()
    leaked = [i["id"] for i in items if i["client_id"] or i["client_secret"]]
    assert leaked == [], f"dataset ids with non-empty client credentials: {leaked}"


# ---------------------------------------------------------------- negative

ENDPOINTS = ["profile", "credits", "datasets"]


@pytest.mark.parametrize("name", ENDPOINTS)
def test_no_authorization_header_is_rejected(env, name):
    """No Authorization header -> 401 {"detail": "Unauthorized"} (captured 2026-10-04)."""
    resp = get(env, name, authorization=None)
    assert resp.status_code == 401, resp.status_code
    assert resp.json() == UNAUTHORIZED_BODY


@pytest.mark.parametrize("name", ENDPOINTS)
def test_invalid_token_is_rejected(env, name):
    """Authorization: Bearer invalid -> 401 {"detail": "Unauthorized"} (captured 2026-10-04)."""
    resp = get(env, name, authorization="Bearer invalid")
    assert resp.status_code == 401, resp.status_code
    assert resp.json() == UNAUTHORIZED_BODY
