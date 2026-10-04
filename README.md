# Rhombus AI Take-Home Exercise

QA of Rhombus AI as an ETL pipeline. A cleaning pipeline was built in plain English with the AI builder, run on a synthetic transactions dataset, and then fed deliberately broken inputs: 5 schema-drift and 2 semantic-drift cases. The aim was to see whether the platform stops, warns or carries on, whether its logs and chatbot help, and what reaches the destination.

- **Route:** a local upload ("From Device") → AI-built pipeline → Azure Blob Storage container `output`. The brief asked for S3 → GCS; see [Deviations](#deviations) for why.
- **Runs:** all runs are manual ▶ runs, because the scheduler never fired (Deviations).
- **What's here:**
  - `observations/`: one report per case, plus the S3 setup note and `baseline.md`;
  - `data-validation/`: a validator that compares each output with the input and the approved cleaning policy;
  - `ui-tests/` and `api-tests/`: live Playwright and API tests;
  - `datasets/`: the generated baseline and the 7 drift files, each with a manifest.
- **Results:** in [Observations summary](#observations-summary).

## Setup and how to run

Requires Python 3.11 or newer. Developed on Python 3.14, Windows.

```
python -m venv .venv
.venv\Scripts\activate                # macOS/Linux: source .venv/bin/activate
python -m pip install -e .            # pinned deps from pyproject.toml
playwright install chromium
copy .env.example .env                # macOS/Linux: cp .env.example .env, then fill in values
```

`.env` holds credentials and is gitignored; `.env.example` lists the variable names only.

| Variables | Used by |
|---|---|
| `AZURE_OUTPUT_CONNECTION_STRING`, `AZURE_OUTPUT_CONTAINER` (default `output`) | UI test 6 (Azure output check) |
| `RHOMBUS_API_BASE`, `RHOMBUS_BEARER_TOKEN`, `RHOMBUS_ORG_ID`, `RHOMBUS_PROJECT_ID` | API tests and `scripts/api_discovery.py` |
| `RHOMBUS_BASE_URL` (default `https://rhombusai.com`) | UI tests |

**Offline suite** (no network): dataset generator, drift files, validator and policy engine.
```
pytest -m "not live"
ruff check .
```

**Datasets.** The generator is deterministic (seed 20261003), and its tests check that the committed files match a fresh run byte for byte.
```
python scripts/generate_datasets.py   # writes datasets/baseline.csv, the 7 drift files and their manifests
```

**Validator.** Compares a pipeline output with its input and the approved policy (`datasets/cleaning-policy.md`). Exit codes: 0 pass · 1 validation fail · 2 bad invocation · 3 file missing.
```
python data-validation/validate.py --scenario <id> --input datasets/<input>.csv \
    --output outputs/<output>.csv --baseline-output outputs/manual-dryrun-4.csv \
    --report observations/evidence/validation-<id>.json
```

**API tests (live).** They need a bearer token copied from DevTools; the tokens are short-lived, and the positive tests skip on 401. The captured contract is in `api-tests/network-contract.md`.
```
pytest api-tests -m live
```

### UI tests (`ui-tests/`, live)

```
pytest ui-tests -m live --headed                  # 5 read-only journey tests
pytest ui-tests -m live --headed --run-pipeline   # + presses ▶ Run once and checks Azure output
```

- **The `--run-pipeline` test can fail on an intermittent platform behaviour.** The Data Output panel shows Azure `output` selected ([screenshot](observations/evidence/data-output-selected.png)), yet some ▶ runs log "Pipeline failed at src_output: A destination is required when remote export is selected." On 2026-10-04 the outcomes varied: failure and no export (~17:07), no failure and export (17:23, 17:24), and failure plus a correct export 20 s later (18:06). The test fails whenever this run logs that failure, and its message says whether anything was exported. The cause is not observed; see `PLAN.md` → "Findings log".
- **Login:** the tests reuse a saved login state, `playwright/.auth/user.json` (gitignored), because login needs an emailed one-time code. If the file is missing, or the app shows the login page (expired session), the tests skip with a message saying so.
- **Nothing is changed:** no test clicks Apply, Create, Delete or a dataset. Clicking Apply on a node starts a pipeline run.
- **Failure artifacts:** traces and screenshots are kept for failing tests only, in `test-results/` (gitignored).
- **Waits:** UI waits use `expect(..., timeout=...)` only. There is no `time.sleep` or `wait_for_timeout` in UI code.
- **Why the Azure check is a bounded poll, not a fixed sleep.** The export to Azure happens outside the browser, so the UI has nothing to `expect` on. `ui-tests/azure_output.py` polls the `output` container instead:
  - it returns as soon as a new `RhombusAI_output_*.csv` appears;
  - it fails at a hard deadline (300 s);
  - its error states the last observed state (blob count and newest blob).

  The 5 s pause between polls only spaces out requests to Azure; it never decides whether the test passes. A fixed sleep would always wait the full time, and would pass or fail on timing alone.

Note: the reference policy engine in `data-validation/cleaning_policy.py` only computes the **expected** output for comparison; it never modifies the pipeline output. The brief's "AI builder only, no manual transformations" rule applies to the pipeline, and is respected.

## Observations summary

All runs are **manual ▶ runs** in project `rhombus-takehome-v2` (workflow 5257), because the scheduler never fired (see Deviations). They are compared against baseline manual run 4. The baseline itself has two known defects, which are not counted below:
- missing names written as `None`;
- money values that lose a trailing zero (`2151.20` → `2151.2`).

| Case | Change | Pipeline stopped? | Chatbot fix worked? | Severity | Details |
|---|---|---|---|---|---|
| Drop column | `country` removed | **Yes**: raw error `['country'] not in index`, nothing written | **No, harmful.** Auto-applied a guard: `country` is empty on all rows, 4 rows that should be rejected were kept, and 3 valid `$` prices were wiped | High | [schema-drop-column.md](observations/schema-drop-column.md) |
| Rename column | `transaction_date` → `order_date` | **Yes**: raw error, nothing written | **No, harmful.** It guessed the column name without reading the file. The retest wrote a **header-only file (0 of 218 rows)** while the log said "Pipeline completed successfully" | High | [schema-rename-column.md](observations/schema-rename-column.md) |
| Type change | `price` numeric → text (`USD 222.97`) | **No**: no error. Every row was rejected and an empty file was written, with only the warning "No results found…" | **No, harmful.** Told to "change nothing else", it re-applied every fix that had been reverted. Still 0 rows | High | [schema-type-change.md](observations/schema-type-change.md) |
| Add column | `channel` appended | **No**, and correctly: output identical to the baseline, extra column dropped | Not needed | Info | [schema-add-column.md](observations/schema-add-column.md) |
| Combined | `id` dropped, rename, price → text, column added | **Yes**: the error named only 2 of the 4 changes, nothing written | **No.** It made up a cause (`ID`, `Transaction_Date`, neither of which exists in the file); the retest gave the identical error | Medium | [schema-combined.md](observations/schema-combined.md) |
| Dollars → cents | `price`, `total` ×100 | **No**: "Pipeline completed successfully", no warning, all money values ×100 delivered | Not used (no error) | High | [semantic-dollars-to-cents.md](observations/semantic-dollars-to-cents.md) |
| Date swap | day/month swapped (day ≤ 12) | **No**: "Pipeline completed successfully", no warning, 81 of 218 dates wrong but valid | Not used (no error) | High | [semantic-date-swap.md](observations/semantic-date-swap.md) |

Severities follow the rubric in this README. They were proposed during review and are justified in each observation file.

### Top three findings

1. **The chatbot's fixes made things worse.**
   - In cases 2, 3 and 5 it diagnosed without reading the input file. In combined (case 5) it made up column names.
   - In cases 1 and 2 its auto-applied fix turned a safe failure into silent bad output: corrupted prices in drop column, and an empty file reported as success in rename column.
   - In case 3 it re-applied reverted fixes despite "change nothing else".
2. **Wrong or empty output was delivered as "successful".** Money values ×100 and 37% swapped dates were delivered with "Pipeline completed successfully" and no warning. A run that rejected every row, or delivered 0 of 218 rows, also completed with at most a warning.
3. **The scheduler never fired.** An active hourly schedule on workflow 5257 produced no run, log or output at three expected times, while manual runs of the same pipeline succeeded ([screenshot](observations/evidence/schedule-never-fired.png)). So the brief's scheduled-pipeline scenario couldn't be tested at all.

## Usability feedback

What worked well. The natural-language AI builder was genuinely impressive: one plain-English prompt describing six cleaning steps produced a working pipeline that removed duplicates, rejected invalid rows and standardised formats correctly (218 of 218 expected rows, with two minor formatting defects). Manual runs were fast, outputs landed in Azure Blob with timestamped filenames, and the same input produced byte-identical output across runs, which made validation easy. The per-entry "Ask Chatbot" button in the logs is a good idea, and the S3 connection form's generated, least-privilege bucket policy is a thoughtful design.

What was frustrating, and how it could improve. Most of my time went into getting data in and runs to happen rather than testing. The S3 source was denied even with Rhombus's whole AWS account allowed; the Azure source's sync made the file disappear; and the hourly schedule never fired, with no execution history and a blank "Next run". When things went wrong, the logs often showed raw Python traces, or "completed successfully" next to a failure in the same second, and runs that silently dropped every row or delivered ×100 prices were reported as successes. The chatbot diagnosed some errors correctly but usually guessed without reading the input, applied fixes without asking, and in several cases made the data worse while saying it was fixed. Concrete suggestions: show the chatbot's proposed change as a diff and ask before applying it; have it read the actual input header before diagnosing; treat "0 rows output" or large distribution shifts as a warning or failure, not a success; show a single, accurate status per run; and add schedule execution history and alerts so a schedule that never fires is visible.

## Demo video link

TODO

## Limitations

**Run mode.** The plan required: "Required scheduled scenarios: 1 baseline + 7 drift scenarios = 8 scheduled runs. Additional determinism and chatbot-fix runs are labelled separately as manual or retest runs." In practice, **0 scheduled runs** happened, because the scheduler never fired (Deviations). All 8 required runs are manual ▶ runs, and chatbot-fix runs are labelled `retest`.

**Runs per case** (outputs matched to Azure blobs by name and time):

| Case | Runs |
|---|---|
| Baseline | 4 manual dry runs. Run 4 is the baseline. Runs 1, 2 and 4 are byte-identical (determinism); run 3 came from a modified pipeline that was then reverted. |
| Drop column, Rename column, Type change, Combined | 1 manual run + 1 retest each. Rename column also had 1 mistaken run on `baseline.csv`, excluded. Type change has 2 extra header-only blobs that aren't attributed to a recorded run. |
| Add column, Dollars → cents, Date swap | 1 manual run each |

Each drift case ran once, so whether drift outputs are repeatable wasn't tested.

**Evidence gaps**
- **Config diffs:** not captured. No Version Control snapshot was taken per chatbot fix, so each fix is described from the chatbot's own reply, not from a before/after diff. Why the case 1 fix also changed price handling is therefore not established.
- **Upload times and most run start times:** not recorded. Run times come from Azure blob creation times and the log times quoted in each observation.
- **Restores:** the pipeline was restored from the saved version before each of cases 2–6 (not needed before case 7: case 6 applied no fix). Restores were confirmed on the canvas, not by a config diff.
- **Chatbot history:** the AI Builder history was cleared before each case from case 4 on (method change, `PLAN.md` D2). Cases 1–3 kept their chat history.
- **Add column input:** the drifted input is confirmed by an 18:30 re-run with `schema_add_column.csv` visibly selected, which produced byte-identical output. There's no screenshot from the original 16:04 run.
- **Screenshots:** 7 sanitised screenshots are published in `observations/evidence/`.
  - **Not captured:** the drop column retest run, and the add column 16:04 run log.
  - **Not published (raw evidence retained privately):** the full S3 CloudTrail JSONs and three S3 setup screenshots. Their key fields are in `observations/setup-s3-connection-blocked.md`.
  - **Transcribed:** the log and chatbot text evidence is the tester's transcriptions (`observations/evidence/*.txt`).

**Not verified on the platform**
- Whether pipelines with a From Device input can be scheduled at all.
- The cause of the intermittent ▶ Run `src_output` failure, and of runs logged when a page is only opened.
- The S3 and GCS routes, and the Azure Blob source after the auto-sync problem.

**Test-suite limits**
- **UI tests** need a manually saved login state; login uses an emailed one-time code.
- **API tests** use a short-lived DevTools token. They cover only three endpoints observed for one account on 2026-10-04.
- **The validator's input contract checks column names, not types.** A column-wide type change (`price` → text) looks like ordinary row defects.
- **When the input contract is broken,** row-level checks are `blocked_by_schema`. The extra rows and wiped prices in Drop column were found by a manual cell-by-cell comparison, not by the validator.

**Validator heuristics**
- The validator's semantic anomaly thresholds are documented, **untuned heuristics** (constants at the top of `data-validation/validate.py`), compared against the baseline output:
  - row count: relative change > 10%;
  - money (`price`, `total`): median or sum ratio outside 0.5–2.0;
  - null rate: absolute increase > 0.05 in any column;
  - date parse success rate: drop > 0.01;
  - dates outside the baseline output's date range;
  - month histogram or `country`/`status` distribution: total variation distance > 0.25, or values not seen in the baseline;
  - any increase in duplicate-key count or `total ≠ price × qty` failures.
- **Swapped dates are invisible row by row.** A day/month swap on a date with day ≤ 12 gives another valid date (`2025-05-03` → `2025-03-05`). No check can flag an individual row, and the policy checks pass because they confirm the dates were cleaned, not that they're correct. The validator can only see a shift in the overall distribution, compared with one baseline run. In `semantic-date-swap`, 40 of the 81 wrong dates fell inside the normal date range and showed up in no metric.
- **The date-swap catch depends on the dataset's date window.** The validator flagged `semantic-date-swap` only through the date-range check, because the baseline covers January–June 2025 and some swapped dates moved into July–December. The month histogram stayed under its threshold (total variation distance 0.188 vs 0.25). On data covering a whole year, the validator would most likely report **pass** with 37% of dates wrong. See `observations/semantic-date-swap.md` §9.

## Deviations

The brief specifies Amazon S3 (source) → Google Cloud Storage (destination). This project uses **a local file upload (source) → Azure Blob Storage (destination)** instead:

- **Amazon S3 source was blocked.**
  - **Attempts:** three buckets. A folder-scoped policy on one bucket, then whole-bucket policies on two more. Each time the Rhombus-generated bucket policy was applied exactly.
  - **Final error** (fresh bucket, Folder / path blank): "AWS denied Rhombus AI access to the whole bucket. Folder / path is blank. The required whole-bucket read-only policy is missing or does not match this bucket…" ([screenshot](observations/evidence/s3-denied.png)).
  - **CloudTrail:** Rhombus's `GetBucketLocation` calls were denied (403) even with a test policy allowing Rhombus's whole AWS account. That rules out the generated policy. The remaining causes are on Rhombus's side or in an AWS Organizations policy, and can't be determined from this account.
  - **Support:** Rhombus support was contacted on 2026-10-03 and replied with the S3 guide.
  - Details: `observations/setup-s3-connection-blocked.md`.
- **Google Cloud Storage was not used** because GCP billing requires a card, and none was available.
- **Azure Blob was tried as the source and dropped.** After initial setup, the Azure Blob source's auto-sync removed the file from Rhombus, although the file was still in Azure (the SAS list API returned `baseline.csv`, 21538 bytes). This reproduced several times on 2026-10-04. It is documented here; it was not reported to Rhombus during the exercise.
- **Input is now a local upload** via Data Input → "From Device" (`datasets/baseline.csv`), in project `rhombus-takehome-v2` (workflow 5257). For each drift case, the drifted CSV is uploaded the same way before the run.
- **The baseline and drift cases use manual runs, not scheduled runs.** On 2026-10-04 an active hourly schedule on workflow 5257 never fired. Hourly runs were set at minute 20, 27 and 40, and at 15:20, 15:27 and 15:40 AEDT there was no log entry, no execution and no output. "Next run" went blank after each expected time. Manual ▶ runs of the same pipeline succeeded. The baseline and every drift run are therefore manual ▶ runs, labelled `manual` in their evidence and observations. The schedule is left on in case it fires later.
- **The baseline is manual run 4** (`outputs/manual-dryrun-4.csv`). Runs 1, 2 and 4 produced byte-identical output, which is the determinism evidence.
- **The destination is Azure Blob Storage** container `output`. Verified: `RhombusAI_output_1791083010935.csv` was written on 2026-10-04 at 14:03:30.
- The earlier project `rhombus-takehome` (workflow 5251) is kept as evidence of the chatbot fix attempts.
- Everything else in the exercise (schema and semantic drift cases, chatbot fixes, validation) is unchanged.
