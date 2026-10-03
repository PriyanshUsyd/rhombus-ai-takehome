# Phase 1 — Setup & discovery

Goal: repo skeleton exists, cloud buckets exist with least-privilege access, and every unknown about the Rhombus app is answered with evidence.

## Checklist

### Repo
- [ ] **[YOU]** Create an empty public GitHub repo and clone it. Copy `CLAUDE.md`, `PLAN.md`, `phases/` into it.
- [ ] **[CLAUDE]** Create folders: `ui-tests/`, `api-tests/`, `data-validation/`, `datasets/`, `observations/evidence/`, `scripts/`.
- [ ] **[CLAUDE]** Create `pyproject.toml` with pinned deps (pytest, pytest-playwright, requests, pandas, boto3, google-cloud-storage, python-dotenv, ruff) and pytest markers `live`.
- [ ] **[CLAUDE]** Create `.gitignore`: `.env`, `.venv/`, `playwright/.auth/`, `*.har`, `test-results/`, `traces/`, `evidence-raw/`, `*.json` keyfiles for GCP service accounts, `__pycache__/`.
- [ ] **[CLAUDE]** Create `.env.example` (names only):
  `RHOMBUS_BASE_URL, RHOMBUS_EMAIL, RHOMBUS_PASSWORD, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET, S3_SOURCE_KEY, GCP_PROJECT_ID, GCS_BUCKET, GCS_OUTPUT_KEY, GOOGLE_APPLICATION_CREDENTIALS, RUN_TIMEOUT_SECONDS, POLL_INTERVAL_SECONDS`
- [ ] **[CLAUDE]** Create a README stub with the four required sections (filled in later).
- [ ] **[YOU]** Create venv, `pip install -e .`, `playwright install chromium`. Paste any errors to Claude.
- [ ] **[YOU]** First commit + push. Confirm `.env` is not tracked (`git status`).

### Accounts & cloud
- [ ] **[YOU]** Sign up for Rhombus AI with the email the invitation was sent to.
- [ ] **[YOU]** AWS: create a private S3 bucket (block public access on). Create an IAM user/policy limited to that bucket only.
- [ ] **[YOU]** GCP: create a private GCS bucket. Create a service account with access to that bucket only; download key to a path outside the repo or a gitignored path.
- [ ] **[CLAUDE]** Once you tell Claude what credentials Rhombus asks for, draft the exact minimal IAM policy / GCS role.
- [ ] **[CLAUDE]** Write cloud cleanup steps into README (delete buckets, IAM user, service account, pause schedule).
- [ ] **[YOU]** Fill your real values into `.env` (never commit).

### Discovery (answer every open question in PLAN.md with evidence)
- [ ] **[YOU]** Click through the app by hand: S3 connection screen, AI builder, GCS destination, schedule, run history, logs, chatbot. Take screenshots into a local `evidence-raw/` folder (gitignored).
- [ ] **[YOU]** With DevTools → Network open, perform: login, list pipelines, view a pipeline/run. For each useful request: right-click → Copy as cURL, **remove tokens/cookies/passwords**, paste to Claude.
- [ ] **[CLAUDE]** Write `api-tests/network-contract.md` from the pasted requests only (method, path, auth mechanism shape, status, redacted response shape, date captured).
- [ ] **[YOU]** Run `playwright codegen <app URL>` through the journey; paste the generated script to Claude (discovery only).
- [ ] **[CLAUDE]** Note candidate stable locators (`get_by_role`/`get_by_label`/test IDs) from codegen + screenshots. Codegen output is not copied verbatim into tests.
- [ ] **[YOU]** Answer each row of "Open questions" in `PLAN.md` (credentials format, schedule intervals, manual run, templated output key, limits, config export, logs location, chatbot location, login method).
- [ ] **[CLAUDE]** Update `PLAN.md` with the answers and flag any that change later phases.

## Done when
- Repo pushed with skeleton, `.env` untracked.
- Both buckets exist, least-privilege creds work.
- All "Open questions" answered or marked "not available in app" with evidence.
- `api-tests/network-contract.md` contains only observed, redacted requests.
