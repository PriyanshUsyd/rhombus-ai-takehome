# Rhombus AI Take-Home Exercise

TODO

## Setup and how to run

TODO

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

1. **The chatbot's auto-applied fixes made things worse.** In every failing case it changed the pipeline without reading the input file, and turned a safe failure into silent bad output: corrupted prices in drop column, an empty file reported as success in rename column, and re-applied reverted fixes in type change. In combined, it made up column names.
2. **Wrong or empty output was delivered as "successful".** Money values ×100 and 37% swapped dates were delivered with "Pipeline completed successfully" and no warning. A run that rejected every row, or delivered 0 of 218 rows, also completed with at most a warning.
3. **The scheduler never fired.** An active hourly schedule on workflow 5257 produced no run, log or output at three expected times, while manual runs of the same pipeline succeeded. So the brief's scheduled-pipeline scenario couldn't be tested at all.

## Usability feedback

TODO

## Demo video link

TODO

## Limitations

TODO

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

- **Amazon S3 source was blocked.** Rhombus reported "AWS denied Rhombus AI access to the selected Folder / path..." even after the Rhombus-generated bucket policy was applied exactly (folder-scoped on one bucket, whole-bucket on another). Details: `observations/setup-s3-connection-blocked.md`. Rhombus support was contacted on 2026-10-03.
- **Google Cloud Storage was not used** because GCP billing requires a card, and none was available.
- **Azure Blob was tried as the source and dropped.** After initial setup, the Azure Blob source's auto-sync removed the file from Rhombus, although the file was still in Azure (the SAS list API returned `baseline.csv`, 21538 bytes). This reproduced several times on 2026-10-04 and was reported to Rhombus.
- **Input is now a local upload** via Data Input → "From Device" (`datasets/baseline.csv`), in project `rhombus-takehome-v2` (workflow 5257). For each drift case, the drifted CSV is uploaded the same way before the run.
- **The baseline and drift cases use manual runs, not scheduled runs.** On 2026-10-04 an active hourly schedule on workflow 5257 never fired. Hourly runs were set at minute 20, 27 and 40, and at 15:20, 15:27 and 15:40 AEDT there was no log entry, no execution and no output. "Next run" went blank after each expected time. Manual ▶ runs of the same pipeline succeeded. The baseline and every drift run are therefore manual ▶ runs, labelled `manual` in their evidence and observations. The schedule is left on in case it fires later.
- **The baseline is manual run 4** (`outputs/manual-dryrun-4.csv`). Runs 1, 2 and 4 produced byte-identical output, which is the determinism evidence.
- **The destination is Azure Blob Storage** container `output`. Verified: `RhombusAI_output_1791083010935.csv` was written on 2026-10-04 at 14:03:30.
- The earlier project `rhombus-takehome` (workflow 5251) is kept as evidence of the chatbot fix attempts.
- Everything else in the exercise (schema and semantic drift cases, chatbot fixes, validation) is unchanged.
