# PLAN.md — Phase tracker

Owner tags: **[YOU]** = human does it live · **[CLAUDE]** = Claude produces it · **[BOTH]** = Claude prepares, human runs/confirms.
Status: ⬜ not started · 🟨 in progress · ✅ done · ⛔ blocked (write reason)

| # | Phase | File | Status | Notes |
|---|-------|------|--------|-------|
| 1 | Setup & discovery | `phases/phase-1-setup.md` | ✅ | 2026-10-03. Route changed (D1). DevTools network capture + codegen moved to Phase 5. |
| 2 | Baseline pipeline | `phases/phase-2-baseline.md` | 🟨 | Generator + manifest done; policy approved 2026-10-03; AI builder prompt drafted, awaiting review. |
| 3 | Schema drift (5 cases) | `phases/phase-3-schema-drift.md` | ⬜ | |
| 4 | Semantic drift (2 cases) | `phases/phase-4-semantic-drift.md` | ⬜ | |
| 5 | Code: validation, UI, API | `phases/phase-5-code.md` | 🟨 | Validator (section A) built + offline tests green; UI/API pending. |
| 6 | Documentation | `phases/phase-6-documentation.md` | ⬜ | |
| 7 | Bonus dashboard (optional) | `phases/phase-7-dashboard.md` | ⬜ | Only after 1–6 |
| 8 | Submit | `phases/phase-8-submit.md` | ⬜ | |

Note: Phase 5 code (generator, validator) is started early — the dataset generator in Phase 2 and the validator before Phase 3 runs. UI/API tests are written once Phase 1 discovery evidence exists.

## Deviations

### D1 — S3 blocked, GCS not used; route is Azure Blob → Azure Blob (decided 2026-10-03)
- **Amazon S3 source BLOCKED.**
  - Error: "AWS denied Rhombus AI access to the selected Folder / path..." despite applying the Rhombus-generated bucket policy exactly.
  - Tried folder-scoped policy on `priyansh-rhombus-takehome-src` and whole-bucket policy on `priyansh-rhombus-src-v2` (both ap-southeast-2). IsPublic=false, no Deny statement.
  - AWS account is a member account in AWS's new "Projects" org setup; Organizations console unavailable to the user.
  - Rhombus support emailed 2026-10-03.
- **Google Cloud Storage NOT used:** GCP requires a card for billing; none available.
- **Actual route:** Azure Blob Storage source → Azure Blob Storage destination.
  - Storage account `priyanshrhombus` (Australia East, LRS, private).
  - Container `source` = input (SAS: read, list).
  - Container `output` = destination (SAS: read, write, create, list, delete).
  - Auth = SAS connection strings (Rhombus-recommended).
- **Scope:** everything else in all phases unchanged. Wherever a phase says S3 → read Azure `source`; GCS → read Azure `output`.
- **Repo changes:** `.env.example` uses `AZURE_*` variables (AWS/GCP dropped); `pyproject.toml` uses `azure-storage-blob` instead of `boto3` / `google-cloud-storage`.
- **Documentation:** `observations/setup-s3-connection-blocked.md` + README "Deviations" note (Phase 6). Candidate negative API/UI test (Phase 5).

## Scenario run tracker

| Scenario ID | Dataset | Run type | Run done | Output downloaded | Validator run | Observation file | Severity |
|---|---|---|---|---|---|---|---|
| baseline | `datasets/baseline.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/baseline.md` | |
| determinism-1..3 | `datasets/baseline.csv` | manual/scheduled | ⬜ | ⬜ | ⬜ | (in baseline.md) | |
| schema-drop-column | `datasets/schema_drop_column.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-drop-column.md` | |
| schema-rename-column | `datasets/schema_rename_column.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-rename-column.md` | |
| schema-type-change | `datasets/schema_type_change.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-type-change.md` | |
| schema-add-column | `datasets/schema_add_column.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-add-column.md` | |
| schema-combined | `datasets/schema_combined.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-combined.md` | |
| semantic-dollars-to-cents | `datasets/semantic_dollars_to_cents.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/semantic-dollars-to-cents.md` | |
| semantic-date-swap | `datasets/semantic_date_swap.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/semantic-date-swap.md` | |

## Open questions (answered in Phase 1, 2026-10-03)
Evidence: observed in the app by the user on 2026-10-03 unless marked TODO. Sanitised screenshots go to `observations/evidence/` as they are prepared.

| Question | Answer | Evidence |
|---|---|---|
| Login method | Email (the invited address). | Observed |
| Credentials Rhombus needs for S3 | No access keys. Bucket + region (+ optional folder, source name, KMS ARN). Rhombus generates a read-only bucket policy or CloudFormation. (Blocked — see D1.) | Observed |
| Credentials Rhombus needs for Azure Blob | SAS connection string + container name. | Observed |
| Schedule intervals offered | Hourly (minute of hour 0–59), Daily, Weekly, Monthly, Custom. Shortest = Hourly. Notify-on-failure option exists. Schedules are managed per project. A schedule cannot be created until the input node has a dataset ("Some input nodes need a source selection before the pipeline can run."). | Observed |
| Manual "run now" exists? | ▶ button on canvas (TODO: confirm). Clicking Apply on the Data Output node also triggers a pipeline run (observed 4:32 PM). | Observed / TODO |
| Output object key templatable? | "Custom Filename" field (default `RhombusAI_output`), CSV/XLSX. Rhombus docs say exports go to container root with a timestamp added to the filename (TODO: verify on first run). | Observed / docs / TODO |
| Upload / row limits | Data Input sampling enabled by default (100,000 rows, streaming). | Observed |
| Pipeline config exportable? | No export seen. Wrench menu has Version Control (use it to snapshot before chatbot fixes), Undo/Redo, Mode Design/Big Data. | Observed |
| Where run logs are shown | "Logs" tab on canvas; filter success/warning/error; each entry has "Ask Chatbot". | Observed |
| Where the chatbot is accessed | "AI Builder" tab (Ask Rhombo). Credits limited: 50 per period; one question used 6 credits. Voucher available if exhausted. | Observed |
| Azure source sync behaviour | Azure source syncs files into Rhombus ("Manual incremental syncing will be available once the initial setup is complete"). Drift swaps may need a manual sync before the scheduled run (TODO: verify in Phase 3). | Observed / TODO |

**Observed quirk:** Azure blob `connection-test.csv` (28 B) is listed in Rhombus as `connection_test` (21.0 B).

### Answers that change later phases
- **Apply triggers a run** → Phase 3/4 protocol: do not edit/Apply nodes between a file swap and the scheduled run.
- **Azure sync** → Phase 3/4: a manual sync may be needed after each swap (TODO: verify in Phase 3).
- **Chatbot credits (50/period, ~6 per question)** → roughly 8 questions per period; budget chatbot questions across the drift cases.
- **No config export** → config "diffs" in Phase 3 use Version Control snapshots + screenshots.
- **Hourly is the shortest schedule** → at most one scheduled scenario per hour.
- **Output filename gets a timestamp (per docs, unverified)** → `fetch_output.py` must pick the right blob in `output`, not assume a fixed name.
- **Hyphen → underscore quirk** → dataset filenames use underscores.
