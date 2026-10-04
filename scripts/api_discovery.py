"""One-off discovery of the Rhombus API endpoints captured in DevTools (phase 5, section C).

Calls each endpoint three ways (valid token, no Authorization header, "Bearer invalid") and
prints only what network-contract.md needs: status code, content type, and the response
SHAPE (keys and value types, never values). For error responses (4xx), the body is also
printed, truncated and with emails and long digit runs masked, because the negative tests
must assert the observed error body. For successful responses, the only strings checked are
this repo's dataset file names (datasets/*.csv), reported as JSON paths where they occur.

The bearer token is read from .env and is never printed, logged or written anywhere.

Usage:
    python scripts/api_discovery.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
REQUIRED = ["RHOMBUS_API_BASE", "RHOMBUS_BEARER_TOKEN", "RHOMBUS_ORG_ID", "RHOMBUS_PROJECT_ID"]
TIMEOUT = 30
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
DIGITS_RE = re.compile(r"\d{4,}")


def endpoints(project_id: str) -> dict[str, str]:
    return {
        "profile": "/api/accounts/users/profile",
        "credits": "/api/accounts/users/credits",
        "datasets": f"/api/dataset/analyzer/v2/projects/{project_id}/datasets",
    }


def shape(value, depth: int = 0):
    """Keys and value types only; no values."""
    if isinstance(value, dict):
        if depth >= 4:
            return "dict"
        return {k: shape(v, depth + 1) for k, v in value.items()}
    if isinstance(value, list):
        inner = shape(value[0], depth + 1) if value else "empty"
        return {"list_len": len(value), "item": inner}
    if value is None:
        return "null"
    return type(value).__name__


def string_paths(value, wanted: set[str], path: str = "$") -> list[tuple[str, str]]:
    """JSON paths (list indices collapsed to []) of strings equal to one of `wanted`."""
    hits = []
    if isinstance(value, dict):
        for k, v in value.items():
            hits += string_paths(v, wanted, f"{path}.{k}")
    elif isinstance(value, list):
        for v in value:
            hits += string_paths(v, wanted, f"{path}[]")
    elif isinstance(value, str) and value in wanted:
        hits.append((path, value))
    return hits


def mask(text: str) -> str:
    return DIGITS_RE.sub("<digits>", EMAIL_RE.sub("<email>", text))[:400]


def describe(resp: requests.Response, wanted: set[str]) -> dict:
    out = {"status": resp.status_code, "content_type": resp.headers.get("Content-Type", "")}
    try:
        body = resp.json()
    except ValueError:
        body = None
        out["body_is_json"] = False
    if body is not None:
        out["shape"] = shape(body)
        if resp.ok:
            out["dataset_name_hits"] = sorted(set(string_paths(body, wanted)))
    if not resp.ok:
        out["error_body_masked"] = mask(resp.text)
    return out


def main() -> int:
    load_dotenv(REPO / ".env")
    missing = [n for n in REQUIRED if not os.environ.get(n)]
    if missing:
        print(f"missing in .env: {', '.join(missing)}", file=sys.stderr)
        return 2
    base = os.environ["RHOMBUS_API_BASE"].rstrip("/")
    token = os.environ["RHOMBUS_BEARER_TOKEN"]
    org = os.environ["RHOMBUS_ORG_ID"]
    stems = {p.stem for p in (REPO / "datasets").glob("*.csv")}
    wanted = stems | {f"{s}.csv" for s in stems}

    auth_modes = {
        "valid_token": {"Authorization": f"Bearer {token}"},
        "no_authorization": {},
        "invalid_token": {"Authorization": "Bearer invalid"},
    }
    report = {}
    for name, path in endpoints(os.environ["RHOMBUS_PROJECT_ID"]).items():
        report[name] = {"method": "GET", "path_template": path.replace(
            os.environ["RHOMBUS_PROJECT_ID"], "{project_id}")}
        for mode, headers in auth_modes.items():
            resp = requests.get(f"{base}{path}", headers={**headers, "x-org-id": org},
                                timeout=TIMEOUT)
            report[name][mode] = describe(resp, wanted)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
