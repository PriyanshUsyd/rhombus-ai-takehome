# Phase 5 — Code: validation, UI tests, API tests

Order: validator is built **before Phase 3 runs** (offline, against local files). UI and API tests are written only after Phase 1 discovery evidence exists.

## A. `data-validation/` — [CLAUDE] writes, [YOU] runs on real outputs
- [x] CLI: `python data-validation/validate.py --scenario <id> --input <S3 input csv> --output <downloaded GCS csv> --baseline-output <baseline output csv> --report observations/evidence/validation-<id>.json`
- [x] Exit codes: `0` pass · `1` validation fail · `2` bad invocation/config · `3` input/output file missing.
- [x] Every check returns `pass` | `fail` | `not_applicable` (+reason) | `blocked_by_schema` (+reason). When the schema is broken, downstream checks are `not_applicable` / `blocked_by_schema`, not `fail`. `overall = fail` if any check fails.
- [x] Checks:
  - **Schema** — expected columns and types.
  - **Reconciliation per rule** — `input_count`, `expected_removed`, `actual_removed`, `unaccounted_rows`. Dedup uses normalised keys per `cleaning-policy.md`; invalid values follow reject/repair/null policy.
  - **Cleaning rules applied** — one check per rule in the policy.
  - **Determinism** — `raw_output_sha256` + `canonical_data_sha256` across runs of the same input.
  - **Semantic anomaly detector** vs baseline output: sum, median, quantiles, null rate, distinct count, duplicate-key count, allowed-value distribution, date range, date-parse success rate, cross-field failures.
- [x] Rules: dates parsed with an explicit format (never inferred); money via `Decimal`; `total` check = `total` vs `price × qty` rounded to 2 dp (ROUND_HALF_UP) in `Decimal`, never float (per `cleaning-policy.md` total rule — avoids float false-rejects); expectations come from the input + policy, never from the output. Call it an anomaly detector, not proof of correctness.
- [x] Offline unit tests (`pytest -m "not live"`) with small hand-built fixtures for every status, including the combined-case `blocked_by_schema` path.
- [x] Implemented in `data-validation/validate.py` + `data-validation/cleaning_policy.py` (policy engine); tests in `data-validation/tests/`. Report nests checks under `"checks"` alongside `files` (raw/canonical SHA-256), `expected` (policy summary), `semantic_fingerprint` and `overall`. Policy gap handled as: missing/non-integer `id` → row rejected (cannot be deduplicated).
- [ ] **[YOU]** Run the validator on every real output (baseline, determinism runs, each drift case).
- [x] Example report shape (combined case, abridged — matches `validate.py`):
```json
{
  "scenario": "schema-combined",
  "files": {"input": {"sha256": "..."}, "output": {"raw_output_sha256": "...", "canonical_data_sha256": "..."}},
  "expected": null,
  "checks": {
    "input_contract": {"status": "fail", "violations": ["required column id is missing"]},
    "schema": {"status": "fail", "violations": ["required column id is missing"]},
    "deduplication": {"status": "not_applicable", "reason": "deduplication key is absent"},
    "row_count_reconciliation": {"status": "blocked_by_schema", "reason": "source contract broken: required column id is missing — expectations cannot be derived safely"}
  },
  "semantic_fingerprint": {"output": {"row_count": 0}, "baseline_output": null},
  "overall": "fail"
}
```

## B. `ui-tests/` — Playwright for Python, marked `live`
Prerequisite: Phase 1 screenshots + codegen output. **No selector is written without evidence.**
- [ ] **[YOU]** (moved from Phase 1) Run `playwright codegen <app URL>` through the journey; paste the generated script to Claude (discovery only).
- [ ] **[CLAUDE]** (moved from Phase 1) Note candidate stable locators (`get_by_role`/`get_by_label`/test IDs) from codegen + screenshots. Codegen output is not copied verbatim into tests.
- [ ] **[CLAUDE]** `conftest.py`: login fixture that saves/reuses storage state (path gitignored); re-login if state lands on login page.
- [ ] **[CLAUDE]** Page objects (actions + locators only; assertions in tests). Locators: `get_by_role` → `get_by_label` → real test IDs → CSS last resort.
- [ ] **[CLAUDE]** Tests covering the journey with real-outcome assertions: S3 connection, AI-built pipeline, GCS destination, schedule.
- [ ] **[CLAUDE]** Deviation D1 (see `PLAN.md`): the UI test may automate the S3 connection form up to the access-denied error and assert on that error (text taken from captured evidence only).
- [ ] Waits: `expect(..., timeout=...)` only. No `time.sleep(N)` / `wait_for_timeout`.
- [ ] Out-of-band completion: bounded condition poll on GCS (deadline + interval + last observed state in error). README explains why this is not a fixed sleep.
- [ ] Traces/screenshots kept on failure only (gitignored).
- [ ] **[YOU]** Run `pytest ui-tests -m live`; paste failures to Claude; iterate until green or document why not.

## C. `api-tests/` — `requests`, marked `live`
Prerequisite: `api-tests/network-contract.md`.
- [ ] **[YOU]** (moved from Phase 1) With DevTools → Network open, perform: login, list pipelines, view a pipeline/run (and the failing S3 connect, for D1). For each useful request: right-click → Copy as cURL, **remove tokens/cookies/passwords/SAS strings**, paste to Claude.
- [ ] **[CLAUDE]** (moved from Phase 1) Write `api-tests/network-contract.md` from the pasted requests only (method, path, auth mechanism shape, status, redacted response shape, date captured).
- [ ] **[CLAUDE]** ≥2 tests on captured endpoints; ≥1 negative (no token or invalid token / invalid credentials).
- [ ] Deviation D1 (see `PLAN.md`): the failing S3 connect request is a candidate negative API test — only if it is captured in `network-contract.md`.
- [ ] Assert status code **and** response content, matching what was observed.
- [ ] Each test docstring cites its captured endpoint + capture date.
- [ ] Credentials from `.env`; never printed.
- [ ] **[YOU]** Run `pytest api-tests -m live`; report results.

## D. Repo-wide
- [ ] `ruff check .` clean.
- [ ] `pytest -m "not live" --junitxml=test-results/offline.xml` green with no credentials set.

## Done when
Validator runs on baseline + every drifted output; UI and API suites run from CLI; offline suite green.
