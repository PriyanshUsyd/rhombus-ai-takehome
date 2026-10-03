# Phase 5 — Code: validation, UI tests, API tests

Order: validator is built **before Phase 3 runs** (offline, against local files). UI and API tests are written only after Phase 1 discovery evidence exists.

## A. `data-validation/` — [CLAUDE] writes, [YOU] runs on real outputs
- [ ] CLI: `python data-validation/validate.py --scenario <id> --input <S3 input csv> --output <downloaded GCS csv> --baseline-output <baseline output csv> --report observations/evidence/validation-<id>.json`
- [ ] Exit codes: `0` pass · `1` validation fail · `2` bad invocation/config · `3` input/output file missing.
- [ ] Every check returns `pass` | `fail` | `not_applicable` (+reason) | `blocked_by_schema` (+reason). When the schema is broken, downstream checks are `not_applicable` / `blocked_by_schema`, not `fail`. `overall = fail` if any check fails.
- [ ] Checks:
  - **Schema** — expected columns and types.
  - **Reconciliation per rule** — `input_count`, `expected_removed`, `actual_removed`, `unaccounted_rows`. Dedup uses normalised keys per `cleaning-policy.md`; invalid values follow reject/repair/null policy.
  - **Cleaning rules applied** — one check per rule in the policy.
  - **Determinism** — `raw_output_sha256` + `canonical_data_sha256` across runs of the same input.
  - **Semantic anomaly detector** vs baseline output: sum, median, quantiles, null rate, distinct count, duplicate-key count, allowed-value distribution, date range, date-parse success rate, cross-field failures.
- [ ] Rules: dates parsed with an explicit format (never inferred); money via `Decimal`; expectations come from the input + policy, never from the output. Call it an anomaly detector, not proof of correctness.
- [ ] Offline unit tests (`pytest -m "not live"`) with small hand-built fixtures for every status, including the combined-case `blocked_by_schema` path.
- [ ] Example report shape (combined case):
```json
{
  "schema": {"status": "fail", "violations": ["required column id is missing"]},
  "deduplication": {"status": "not_applicable", "reason": "deduplication key is absent"},
  "row_count_reconciliation": {"status": "blocked_by_schema", "reason": "source contract cannot be evaluated safely"},
  "overall": "fail"
}
```

## B. `ui-tests/` — Playwright for Python, marked `live`
Prerequisite: Phase 1 screenshots + codegen output. **No selector is written without evidence.**
- [ ] **[CLAUDE]** `conftest.py`: login fixture that saves/reuses storage state (path gitignored); re-login if state lands on login page.
- [ ] **[CLAUDE]** Page objects (actions + locators only; assertions in tests). Locators: `get_by_role` → `get_by_label` → real test IDs → CSS last resort.
- [ ] **[CLAUDE]** Tests covering the journey with real-outcome assertions: S3 connection, AI-built pipeline, GCS destination, schedule.
- [ ] Waits: `expect(..., timeout=...)` only. No `time.sleep(N)` / `wait_for_timeout`.
- [ ] Out-of-band completion: bounded condition poll on GCS (deadline + interval + last observed state in error). README explains why this is not a fixed sleep.
- [ ] Traces/screenshots kept on failure only (gitignored).
- [ ] **[YOU]** Run `pytest ui-tests -m live`; paste failures to Claude; iterate until green or document why not.

## C. `api-tests/` — `requests`, marked `live`
Prerequisite: `api-tests/network-contract.md` from Phase 1.
- [ ] **[CLAUDE]** ≥2 tests on captured endpoints; ≥1 negative (no token or invalid token / invalid credentials).
- [ ] Assert status code **and** response content, matching what was observed.
- [ ] Each test docstring cites its captured endpoint + capture date.
- [ ] Credentials from `.env`; never printed.
- [ ] **[YOU]** Run `pytest api-tests -m live`; report results.

## D. Repo-wide
- [ ] `ruff check .` clean.
- [ ] `pytest -m "not live" --junitxml=test-results/offline.xml` green with no credentials set.

## Done when
Validator runs on baseline + every drifted output; UI and API suites run from CLI; offline suite green.
