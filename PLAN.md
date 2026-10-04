# PLAN.md — Phase tracker

Owner tags: **[YOU]** = human does it live · **[CLAUDE]** = Claude produces it · **[BOTH]** = Claude prepares, human runs/confirms.
Status: ⬜ not started · 🟨 in progress · ✅ done · ⛔ blocked (write reason)

| # | Phase | File | Status | Notes |
|---|-------|------|--------|-------|
| 1 | Setup & discovery | `phases/phase-1-setup.md` | ✅ | 2026-10-03. Route changed (D1). DevTools network capture + codegen moved to Phase 5. |
| 2 | Baseline pipeline | `phases/phase-2-baseline.md` | 🟨 | Generator + manifest done; policy approved 2026-10-03; AI builder prompt drafted, awaiting review. |
| 3 | Schema drift (5 cases) | `phases/phase-3-schema-drift.md` | 🟨 | 2026-10-04: all 5 run (manual, D2); observations drafted. Open: sanitised log/chatbot evidence, pre/post-state TODOs. |
| 4 | Semantic drift (2 cases) | `phases/phase-4-semantic-drift.md` | 🟨 | 2026-10-04: both run (manual, D2); observations with three verdicts drafted. Open: sanitised log evidence. |
| 5 | Code: validation, UI, API | `phases/phase-5-code.md` | 🟨 | Validator (section A) built + offline tests green; UI/API pending. |
| 6 | Documentation | `phases/phase-6-documentation.md` | 🟨 | 7 drift observations + S3 setup note drafted; README Observations summary + top 3 done. Open: baseline.md, setup, usability, video, rest of Limitations. |
| 7 | Bonus dashboard (optional) | `phases/phase-7-dashboard.md` | ⬜ | Only after 1–6 |
| 8 | Submit | `phases/phase-8-submit.md` | ⬜ | |

Note: Phase 5 code (generator, validator) is started early — the dataset generator in Phase 2 and the validator before Phase 3 runs. UI/API tests are written once Phase 1 discovery evidence exists.

## Deviations

### D1 — S3 blocked, GCS not used; route is local upload → Azure Blob (decided 2026-10-03, updated 2026-10-04)
- **Amazon S3 source BLOCKED.**
  - Error: "AWS denied Rhombus AI access to the selected Folder / path..." despite applying the Rhombus-generated bucket policy exactly.
  - Tried folder-scoped policy on `priyansh-rhombus-takehome-src` and whole-bucket policy on `priyansh-rhombus-src-v2` (both ap-southeast-2). IsPublic=false, no Deny statement.
  - AWS account is a member account in AWS's new "Projects" org setup; Organizations console unavailable to the user.
  - Rhombus support emailed 2026-10-03.
- **Google Cloud Storage NOT used:** GCP requires a card for billing; none available.
- **Original route (2026-10-03):** Azure Blob Storage source → Azure Blob Storage destination.
  - Storage account `priyanshrhombus` (Australia East, LRS, private).
  - Container `source` = input (SAS: read, list).
  - Container `output` = destination (SAS: read, write, create, list, delete).
  - Auth = SAS connection strings (Rhombus-recommended).
- **Update 2026-10-04 — Azure Blob source dropped.**
  - Azure Blob source auto-sync removes the file after initial setup. The file is still present in Azure: the SAS list API returns `baseline.csv` (21538 bytes).
  - Reproduced several times on 2026-10-04. Documented; not reported to Rhombus during the exercise (draft email unsent).
- **Actual route (from 2026-10-04):** local upload via Data Input → "From Device" (`datasets/baseline.csv`) → AI-built pipeline → Azure Blob Storage container `output`.
  - New project `rhombus-takehome-v2` (workflow 5257).
  - Destination verified: `RhombusAI_output_1791083010935.csv` written to `output` 2026-10-04 14:03:30.
  - Drift cases: upload the drifted CSV via From Device before each manual ▶ run (D2; the scheduler never fired).
  - Old project `rhombus-takehome` (workflow 5251) kept as evidence of the chatbot fix attempts.
- **Scope:** everything else in all phases unchanged. Wherever a phase says S3 → read From Device upload of the dataset file; GCS → read Azure `output`.
- **Repo changes:** `.env.example` uses `AZURE_*` variables (AWS/GCP dropped); `pyproject.toml` uses `azure-storage-blob` instead of `boto3` / `google-cloud-storage`.
- **Documentation:** `observations/setup-s3-connection-blocked.md` + README "Deviations" note (Phase 6). Candidate negative API/UI test (Phase 5).

## Findings log

Issues observed outside the drift scenarios. Observed by the user in the app unless marked TODO.

| Date | Finding | Evidence |
|---|---|---|
| 2026-10-04 | S3 connection denied even with the generated policy and a whole-Rhombus-account test policy; error text says policy "missing or does not match". | `observations/setup-s3-connection-blocked.md` |
| 2026-10-04 | Reconnecting a source silently breaks the input node. The next run fails with a raw backend error in the user-facing logs: "No Dataset matches the given criteria: {'id': ..., 'project_id': 5251, 'user_id': <CustomUser:..." | Screenshot not captured |
| 2026-10-03 | Clicking Apply on the Data Output node triggers a pipeline run. | Observed 4:32 PM |
| 2026-10-04 | Only one third-party source is allowed at a time. | Screenshot not captured |
| 2026-10-04 | AI builder credits: build prompt cost 10, Rhombo question cost 6; credits also dropped 44 → 39 without a prompt being sent. | Screenshot not captured |
| 2026-10-04 | **Scheduler never fires** (workflow 5257, project `rhombus-takehome-v2`; input From Device, output Azure Blob). An active hourly schedule was set at minute 20, then edited to 27 (~15:25) and to 40 (~15:38). At 15:20, 15:27 and 15:40 AEDT: no log entry, Executions tab shows "No results", no output in Azure `output`, and "Next run" goes blank after each expected time. Manual runs of the same pipeline succeed (latest 15:11, output `RhombusAI_output_1791087076533.csv`). | [`observations/evidence/schedule-never-fired.png`](observations/evidence/schedule-never-fired.png): "Active", "Hourly", "At minute 40", "Next run:" blank; Executions tab "No results." |
| 2026-10-04 | **Chatbot schedule diagnosis is wrong or unverified.** It admitted it had no docs on schedule rules, then listed four causes: (1) a From Device upload isn't persistent for the server-side scheduler (unverified); (2) a blank "Next run" means the schedule errored, so re-save it (unverified; the schedule was edited and re-saved at ~15:25 and ~15:38 and still never fired); (3) the Azure output credentials may have expired (incorrect: the SAS is valid to 2026-10-24, and a manual run wrote output at 15:11); (4) timezone/UTC interpretation (doesn't fit an hourly-at-minute schedule). | `observations/evidence/chatbot-schedule.txt` (raw: `evidence-raw/chatbot-schedule.txt`) |
| 2026-10-04 | **"From Web URL" is a web scraper.** A direct Azure Blob SAS URL to `baseline.csv` fails with "Failed to scrape ... document_antibot". | `evidence-raw/` |
| 2026-10-04 | **Version Control has no automatic history.** It shows "No saved versions yet" until a version is saved manually. | `evidence-raw/` |
| 2026-10-04 | **AI builder auto-run is inconsistent.** The pipeline ran after the first build in v1 (`rhombus-takehome`), but not after the build in v2 (`rhombus-takehome-v2`). | `evidence-raw/` |
| 2026-10-04 | **Intermittent UI/backend state mismatch on ▶ Run: the UI shows the destination selected, but the backend sometimes reports none.** Workflow 5257; input `baseline.csv`. The Data Output panel shows the Azure Blob Storage destination `output` as selected ([`observations/evidence/data-output-selected.png`](observations/evidence/data-output-selected.png), captured at 18:30). Some ▶ runs log "Pipeline failed at src_output: A destination is required when remote export is selected." next to "Pipeline execution completed successfully.". The outcome varies (AEDT; blobs checked by Claude via the container listing): <br>• **~17:07, test 6, twice: failure logged, no export.** The first run's screenshot shows the `src_output` card at 05:07:32 PM, and the 300 s Azure poll timed out. No blob exists between 16:51:59 and 17:23:06. The second run's failure count used a page-wide locator that also matched old chat text, so only "no export" is established for it. Both one-press runs logged "Pipeline execution started." twice. <br>• **17:23, manual ▶ in a normal browser: no failure, exported** `RhombusAI_output_1791094986135.csv` (17:23:06). <br>• **17:24, test 6: no failure, exported** `…1791095070309.csv` (17:24:30), byte-identical to baseline run 4. <br>• **~18:03, test 6 (user run): no export.** No new blob at 18:04:33 or 18:05:38. Whether a `src_output` entry was logged isn't established (same page-wide locator issue). <br>• **18:06, test 6 with timestamp-scoped log checks: failure logged AND exported.** The log shows "Pipeline failed at src_output: …" at **06:06:43 PM**. `RhombusAI_output_1791097623381.csv` was created at **18:07:03**, 20 s later. It is byte-identical to baseline run 4 (validator: only the 3 known baseline failures; determinism pass). <br>• **18:52, ▶ Run (user report): failure logged AND exported.** The user reported a `src_output` failure entry for this run. `RhombusAI_output_1791100583085.csv` was created at **18:56:23** (07:56:23Z, 18 660 bytes; checked by Claude via blob properties), about 4 min after the run. It is byte-identical to baseline run 4 (SHA-256 `ebedc745…`; validator: only the 3 known baseline failures; determinism pass). No log excerpt or screenshot of the failure entry is saved in the repo. <br>• **Runs logged with no ▶ or Apply click:** 17:00:02 and 18:05:27, both during read-only Playwright sessions that only opened pages and panels. Both logged completion and produced no new blob. <br>Earlier, case 6's 16:14:26 `src_output` entry and case 7's double "started" entry were each followed by a successful ▶ export (intermittent log anomalies). **Cause not observed.** Not established: whether the Playwright session, the ~16:51 codegen actions (S3 Connect attempt, Apply on Data Output) or page loads are involved, or why a run that logged a `src_output` failure still exported. | `test-results/…run-pipeline…/test-failed-1.png` (gitignored; TODO sanitised copy); test 6 output; Azure listing; `outputs/ui-run-20261004-1806z.*`; `outputs/ui-run-20261004-1852z.*` |

### Decision D2 (2026-10-04) — baseline and drift cases use manual runs
- **What:** the baseline and drift cases run with manual ▶ runs. Each run is labelled `manual` in evidence and in the README.
- **Baseline:** manual run 4.
- **Why:** the scheduler never fired for workflow 5257 (see Findings log above).
- **Schedule:** left ON, in case it fires later.
- **CLAUDE.md:** the run-mode rule is updated to match.
- **Method note — AI Builder history cleared before each case, from case 4 (`schema-add-column`) onward.**
  - **Why:** in case 3 (`schema-type-change`) the chatbot was told to "change nothing else", yet it re-applied every earlier fix that had been reverted (`column_guard`, the `None`/2-decimal prompt changes). Clearing the history stops reverted fixes coming back.
  - **Effect:** cases 1–3 ran with the chat history kept; cases 4–7 ran with it cleared. Each affected observation states this.

## Scenario run tracker

| Scenario ID | Dataset | Run type | Run done | Output downloaded | Validator run | Observation file | Severity |
|---|---|---|---|---|---|---|---|
| baseline | `datasets/baseline.csv` | manual (D2) — run 4 | ✅ | ✅ `outputs/manual-dryrun-4.csv` | ✅ `validation-manual-dryrun-4.json` (fail: 2 known defects) | ✅ `observations/baseline.md` | High (`None` names) / Low (trailing zeros) |
| determinism | `datasets/baseline.csv` | manual (D2) — runs 1, 2, 4 | ✅ | ✅ | ✅ determinism pass (run 4 vs run 2) | (in baseline.md) | |
| schema-drop-column | `datasets/schema_drop_column.csv` | manual (D2) + retest | ✅ | ✅ retest only (first run wrote nothing) | ✅ retest | ✅ `observations/schema-drop-column.md` | High |
| schema-rename-column | `datasets/schema_rename_column.csv` | manual (D2) + retest | ✅ | ✅ retest only (first run wrote nothing) | ✅ retest | ✅ `observations/schema-rename-column.md` | High |
| schema-type-change | `datasets/schema_type_change.csv` | manual (D2) + retest | ✅ | ✅ both | ✅ both | ✅ `observations/schema-type-change.md` | High |
| schema-add-column | `datasets/schema_add_column.csv` | manual (D2) | ✅ | ✅ | ✅ | ✅ `observations/schema-add-column.md` | Info |
| schema-combined | `datasets/schema_combined.csv` | manual (D2) + retest | ✅ | — no output (both runs stopped) | — no output | ✅ `observations/schema-combined.md` | Medium |
| semantic-dollars-to-cents | `datasets/semantic_dollars_to_cents.csv` | manual (D2) | ✅ | ✅ | ✅ | ✅ `observations/semantic-dollars-to-cents.md` | High |
| semantic-date-swap | `datasets/semantic_date_swap.csv` | manual (D2) | ✅ | ✅ | ✅ | ✅ `observations/semantic-date-swap.md` | High |

### Baseline (decided 2026-10-04)
- **Baseline = manual run 4.** Output `outputs/manual-dryrun-4.csv`; report `observations/evidence/validation-manual-dryrun-4.json`.
- **Determinism evidence:**
  - Runs 2 and 4 are byte-identical (SHA-256 `ebedc745b23296ff1c77ced008d0dd27e051d7c1f091c1cd1efa43147310cdda`). Run 1 has the same hash.
  - The run-4 report's determinism check passes against run 2 (byte- and data-identical).
  - Run 3 differs; see `validation-manual-dryrun-3.json`.
- **Row count:** 218 expected, 218 produced. Dedup and every rejection rule match.
- **Known baseline defects** (the run-4 report fails only on these):
  1. **"None" names:** the 3 rows with a missing name (ids 1017, 1039, 1198) get the text `None` instead of an empty cell (`rule_name_missing_kept_null`, `values_match_policy`).
  2. **Dropped trailing zeros:** price and total lose a trailing zero (e.g. `2151.20` → `2151.2`), in 70 cells (21 price, 49 total) across 49 rows (`output_format`: `money_two_decimals`). The numeric values are correct.
- **Drift comparisons:** drift outputs are compared against this baseline. These two defects are expected in every drift output and are not new findings.

## Open questions (answered in Phase 1, 2026-10-03)
Evidence: observed in the app by the user on 2026-10-03 unless marked TODO. Sanitised screenshots go to `observations/evidence/` as they are prepared.

| Question | Answer | Evidence |
|---|---|---|
| Login method | Email (the invited address). | Observed |
| Credentials Rhombus needs for S3 | No access keys. Bucket + region (+ optional folder, source name, KMS ARN). Rhombus generates a read-only bucket policy or CloudFormation. (Blocked — see D1.) | Observed |
| Credentials Rhombus needs for Azure Blob | SAS connection string + container name. | Observed |
| Schedule intervals offered | Hourly (minute of hour 0–59), Daily, Weekly, Monthly, Custom. Shortest = Hourly. Notify-on-failure option exists. Schedules are managed per project. A schedule cannot be created until the input node has a dataset ("Some input nodes need a source selection before the pipeline can run."). | Observed |
| Manual "run now" exists? | Yes: the ▶ button on the canvas (`data-testid=run-pipeline`; confirmed 2026-10-04 and used by `ui-tests` test 6). Clicking Apply on the Data Output node also triggers a pipeline run (observed 4:32 PM). | Observed |
| Output object key templatable? | "Custom Filename" field (default `RhombusAI_output`), CSV/XLSX. Rhombus docs say exports go to container root with a timestamp added to the filename (TODO: verify on first run). | Observed / docs / TODO |
| Upload / row limits | Data Input sampling enabled by default (100,000 rows, streaming). | Observed |
| Pipeline config exportable? | No export seen. Wrench menu has Version Control (use it to snapshot before chatbot fixes), Undo/Redo, Mode Design/Big Data. | Observed |
| Where run logs are shown | "Logs" tab on canvas; filter success/warning/error; each entry has "Ask Chatbot". | Observed |
| Where the chatbot is accessed | "AI Builder" tab (Ask Rhombo). Credits limited: 50 per period; one question used 6 credits. Voucher available if exhausted. | Observed |
| Azure source sync behaviour | Azure source syncs files into Rhombus ("Manual incremental syncing will be available once the initial setup is complete"). Obsolete: the Azure source was dropped on 2026-10-04 (D1 update), so drift files are uploaded via From Device. | Observed |

**Observed quirk:** Azure blob `connection-test.csv` (28 B) is listed in Rhombus as `connection_test` (21.0 B).

### Answers that change later phases
- **Apply triggers a run** → Phase 3/4 protocol: do not edit/Apply nodes between a file swap and the scheduled run.
- **Azure sync** → obsolete: the Azure source was dropped (D1 update); drift files are uploaded via From Device.
- **Chatbot credits (50/period, ~6 per question)** → roughly 8 questions per period; budget chatbot questions across the drift cases.
- **No config export** → config "diffs" in Phase 3 use Version Control snapshots + screenshots.
- **Hourly is the shortest schedule** → at most one scheduled scenario per hour.
- **Output filename gets a timestamp (per docs, unverified)** → `fetch_output.py` must pick the right blob in `output`, not assume a fixed name.
- **Hyphen → underscore quirk** → dataset filenames use underscores.
