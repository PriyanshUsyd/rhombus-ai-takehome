# CLAUDE.md — Rhombus AI Take-Home (project rules for Claude)

Read this file and `PLAN.md` before doing anything. Then open the current phase file in `phases/`.

## What this project is
A take-home exercise for the Rhombus AI "Software Engineer Intern (LLM Observability & QA)" role.
Test Rhombus AI as a scheduled ETL pipeline: Amazon S3 (source) → AI-built cleaning pipeline → Google Cloud Storage (destination), then break the input on purpose (schema drift, semantic drift) and report how the platform responds.
They grade judgement, test quality and clarity of reporting — not the platform.

## Division of work
- **YOU (human):** every live action — sign-ups, cloud consoles, Rhombus UI, AI builder prompts, chatbot conversations, uploading drifted files, waiting for runs, screenshots, DevTools captures, demo video, final email.
- **CLAUDE:** code, datasets, configs, docs, observation drafts, README, checklists. Claude cannot log into Rhombus/AWS/GCP and must not pretend it did.

## Hard rules (never break)
1. **No hallucination.** Never invent Rhombus UI elements, selectors, endpoints, request/response shapes, log text, schedule options or chatbot behaviour. If unknown, write `TODO: verify in app` and ask the human for evidence (screenshot, copied text, DevTools "Copy as cURL" with secrets removed).
2. **Only verified Rhombus facts** (from https://doc.rhombusai.com/): sources include Amazon S3 / Azure Blob / GCS / Snowflake / file upload; pipelines are built in plain English; export to S3 / Azure Blob / GCS / Snowflake; pipelines can be run and scheduled. Everything else = verify in app.
3. **Do not confuse Rhombus AI with Rhombus Systems** (security cameras, `rhombussystems.com`, `rhombus.community`). Never use those sources.
4. **Python only.** Playwright for Python has no `expect.poll` / `to_pass` (those are JS). Use `expect(..., timeout=...)` and a bounded condition poll for out-of-band state.
5. **No fixed sleeps** in UI tests. No `time.sleep(N)` / `wait_for_timeout` as a wait strategy. Bounded condition polling (deadline + interval + last observed state in the error) is allowed and must be documented in the README.
6. **AI builder only** for pipeline transformations. Never add manual transformations or post-process output to "fix" it.
7. **Secrets never committed:** `.env`, Playwright auth state, HAR files, traces, raw screenshots/logs, cloud keys. Only `.env.example` with variable names.
8. **Report only observed behaviour.** Unknown = "not observed". Never predict platform behaviour as fact.
9. Before marking any checklist item done, the evidence/file must exist. Update `PLAN.md` tracker when a phase item completes.

## Stack (pinned in pyproject.toml)
pytest, pytest-playwright, requests, pandas, boto3, google-cloud-storage, python-dotenv, ruff. Stdlib: `decimal`, `hashlib`, `json`. Reports: `pytest --junitxml`.
- Live tests: `pytest -m live` (opt-in). Default: `pytest -m "not live"` (offline, local files, no cloud calls).

## Required repo layout (from the brief)
```
/ui-tests/            Playwright tests: S3 connection, AI-built pipeline, GCS destination, schedule
/api-tests/           ≥2 tests on DevTools-captured endpoints, ≥1 negative
/data-validation/     validator comparing GCS output vs S3 input
/datasets/            baseline + every drifted version
/observations/        one .md per drift case
/observations/evidence/  sanitised screenshots, log excerpts, validation JSON
README.md
```
Extra: `scripts/`, `phases/`, `.env.example`, `.gitignore`, `pyproject.toml`.

## Validator check statuses
Every check returns: `pass` | `fail` | `not_applicable` (input absent, with reason) | `blocked_by_schema` (contract broken, with reason). Downstream checks on a broken schema must not report ordinary `fail`. `overall` = `fail` if any check fails.

## Severity rubric
- **Critical:** confirmed material corruption or data exposure that is silent or inadequately contained and lacks a reliable recovery path.
- **High:** silent incorrect output, schedule failure, data loss, or failed recovery path.
- **Medium:** stops or warns, but diagnostics incomplete/misleading or recovery hard.
- **Low:** minor issue with safe recovery.
- **Info:** handled well, or non-blocking improvement.
- Principle: silent semantic corruption ranks above a visible failure.

## Run-mode rule
Required scheduled scenarios: 1 baseline + 7 drift scenarios = 8 scheduled runs. Additional determinism and chatbot-fix runs are labelled separately as manual or retest runs (only if the app offers manual runs).

## Submission (from the invitation email)
New email to careers@rhombusai.com, subject exactly: `Rhombus AI – Take-Home Exercise`, include the GitHub repo link. Queries: rhombusinsights@rhombusai.com.
