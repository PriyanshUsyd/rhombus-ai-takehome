# Schema drift: rename column (`schema-rename-column`)

| | |
|---|---|
| **Run type** | `manual` ▶ run (D2: the scheduler never fired), then one `retest` after the chatbot fix |
| **Project / workflow** | `rhombus-takehome-v2` / 5257 |
| **Date** | 2026-10-04 |
| **Severity (proposed)** | **High**: see section 11 |

**Summary.** With `transaction_date` renamed to `order_date`, the first run **failed closed**: no output was written, but the error was a raw Python message. The chatbot didn't read the input file. It guessed the column was "likely date or txn_date" and auto-applied a `column_guard` alias map that doesn't cover `order_date`. The retest then wrote an **empty file to Azure: the header and zero rows**. The run showed a warning, "No results found after applying this LLM transformation", but the log said "Pipeline completed successfully" at the same time. All 218 expected rows were lost, and the run reported success.

## 1. Change

- **Dataset:** `datasets/schema_rename_column.csv`, SHA-256 `741a11242e625701782b057255c2d7389c52bea8fefb32276b982dc75b515623` (manifest `datasets/schema_rename_column.manifest.json`).
- **Derived from:** `datasets/baseline.csv` (SHA-256 `f2c301dc…c2a2`).
- **Exact change:** header `transaction_date` renamed to `order_date`. Every value is identical to the baseline (250 rows, 9 columns).
- **Uploaded via:** Data Input → "From Device".
- **Upload time:** not recorded.

## 2. Expected behaviour

Our expectation, not a Rhombus claim. `transaction_date` is a required input column (`datasets/cleaning-policy.md` §1), and the cleaning rules depend on it (date reformatting, rejection of missing or invalid dates). A good pipeline would do one of two things:
- stop or warn, naming the missing column and ideally suggesting the likely match `order_date`; or
- map `order_date` to `transaction_date` explicitly and visibly, and produce the same 218 rows as the baseline.

It should never deliver an empty or partial file under a success status.

## 3. Actual behaviour

| Run | Outcome | What reached Azure `output` |
|---|---|---|
| First `manual` run | **Stopped** at step `clean_transactions` with `['transaction_date'] not in index`. Same `code_sha` (`5e6c1f84d511`) as the first run of case 1. The raw trace was shown in the log. | Nothing (no output written). |
| `retest` after the chatbot fix | **Contradictory status.** It warned "No results found after applying this LLM transformation", and at the same time the log said "Pipeline completed successfully". | `RhombusAI_output_1791089709537.csv`: **62 bytes, header only, 0 data rows** |

Retest output, in full (`outputs/schema-rename-column-retest.csv`):
```
id,name,email,country,price,qty,total,transaction_date,status
```

- The header has the 9 contract columns, including `transaction_date`, so the file *looks* structurally valid.
- The baseline output for the same data has 218 rows. All of them are missing.
- **Why the rows were dropped is not observed directly.** The chatbot's own description of its fix makes the likely mechanism clear (section 7). The alias map has no `order_date`, and missing columns are added as NaN. So `transaction_date` would arrive empty, and the existing "date missing → reject row" rule would reject every row. The run log doesn't state the rejection reason, so this remains inferred.

Known baseline defects (`None` names, missing trailing zeros) can't show up here because there are no rows. They aren't findings for this case.

## 4. Pre-state / post-state

- **Pre-state:**
  - Input: section 1.
  - Pipeline: **restored from the saved version** before this case. Confirmed: the canvas showed no `column_guard`. The first run had the same `code_sha` as case 1's first run, which is consistent with that.
  - Schedule: Active, hourly, never fired (see `PLAN.md` → "Findings log").
  - Last successful run (latest output blob before the case): `RhombusAI_output_1791089361234.csv` (15:49:21, case 1 retest). The mistaken run on `baseline.csv` (`RhombusAI_output_1791089499109.csv`, 15:51:39) is excluded (see Limitations).
  - Snapshot: not captured.
- **Post-state:**
  - Pipeline: contains the chatbot's `column_guard` alias map.
  - Schedule: Active, hourly, never fired (see `PLAN.md` → "Findings log").
  - Latest output: `RhombusAI_output_1791089709537.csv` (15:55:09).

## 5. Run identity

| Run | Started | Status | Output object | Local copy SHA-256 |
|---|---|---|---|---|
| `manual` | 15:53:35–15:53:39 (log) | failed (`['transaction_date'] not in index`); the log also shows "Pipeline execution completed successfully." at 15:53:39 | none | — |
| `retest` | 15:54:52–15:55:07 (log); object 15:55:09 | completed with a warning | `RhombusAI_output_1791089709537.csv` | `260801d0552dc4ca9a28f8c641e41984e1e5e7c3dac33a45f8703a25df0afb3c` (`outputs/schema-rename-column-retest.csv`, 62 bytes) |

## 6. Logs

- **First run** (`observations/evidence/schema-rename-column-log.txt`): `Pipeline failed at clean_transactions: LLM execution failed (code_sha=5e6c1f84d511): "['transaction_date'] not in index" …`, followed by the raw generated code.
- **Retest** (`observations/evidence/schema-rename-column-chatbot.txt`): the warning "No results found after applying this LLM transformation" plus "Pipeline completed successfully".
- **Clear?**
  - **First run: partly.** It names the missing column, but as a raw Python/pandas `KeyError` with code. It doesn't say the input schema changed, and it doesn't suggest `order_date`.
  - **Retest: no, misleading.** It reports success while delivering zero rows. The only signal is a warning that doesn't say every row was dropped or why.

## 7. Chatbot

- **Prompt:** "Please help me fix the following error:" + the error text, sent by the "Ask Chatbot" button on the failed log entry.
- **Diagnosis: partly correct, and a guess.** It said `transaction_date` "is likely called something like date or txn_date". It didn't read the input file: the actual name, `order_date`, was in the uploaded file's header.
- **Change:** a **persistent** `column_guard` that:
  - renames aliases: `date→transaction_date`, `quantity→qty`, `customer_name→name`, `txn_status→status`. **`order_date` is not in the list.**
  - adds missing columns as NaN.
- **Claim:** that the pipeline "will now handle … a file with renamed columns".
- **Applied:** **automatically, with no confirmation shown.**
- **Cost:** 5 credits (4948 → 4943).
- **Config diff:** not captured. No Version Control snapshot was taken per fix; the fix is described from the chatbot's own reply (limitation, see README).
- **Retest:** completed with a warning; header-only output (section 3).
- **Fix grade:** **didn't work, harmful.** It replaced a loud failure that wrote nothing with a "successful" run that delivered an empty file to the destination.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used manual runs. Schedule state after the case: Active, hourly, never fired (see `PLAN.md` → "Findings log").

**Risk if a schedule did fire:** with this fix in place, each scheduled run on a renamed input would keep delivering empty files marked as successful.

## 9. Validation results

Retest report: `observations/evidence/validation-schema-rename-column-retest.json` (compared against baseline run 4). Overall: **fail**.

| Check | Status | Note |
|---|---|---|
| `input_contract` | fail | required column `transaction_date` missing; extra column `order_date` |
| `schema` | pass | the output header has the 9 contract columns |
| `output_format` | pass | trivially: there are no rows to check |
| `deduplication`, `row_count_reconciliation`, `manifest_consistency`, all 14 `rule_*` checks, `values_match_policy` | blocked_by_schema | the input contract is broken |
| `determinism` | not_applicable | the input isn't the baseline dataset |
| `semantic_anomaly` | **fail** | 6 metrics, below |

| Metric | Baseline (run 4) | Retest | Rule |
|---|---|---|---|
| `row_count` | 218 | **0** | relative change > 0.10 |
| `price.sum` | 54012.32 | **0** | ratio outside [0.5, 2.0] |
| `total.sum` | 309572.79 | **0** | ratio outside [0.5, 2.0] |
| `country.distribution` | 8 countries | **empty** | total variation distance > 0.25 |
| `status.distribution` | 4 statuses | **empty** | total variation distance > 0.25 |
| `transaction_date.month_histogram` | 6 months | **empty** | total variation distance > 0.25 |

The validator catches this clearly: `row_count` 218 → 0. The platform's only signal was a warning sitting next to a success message.

## 10. Three verdicts

Not a semantic case; this section doesn't apply.

## 11. Severity

**Proposed: High.** The chatbot's auto-applied fix is a **failed recovery path** that causes **data loss**. A header-only file with 0 of 218 rows was written to the destination under "Pipeline completed successfully". A downstream consumer checking only the run status would accept it. That matches the rubric's High ("data loss, or failed recovery path").

Not Critical:
- Nothing existing was corrupted; the output is visibly empty.
- A warning was shown.
- Recovery is possible: restore the pipeline and re-run.

Not Medium either: although a warning appeared, the success status and the empty file reaching the destination go beyond "stops or warns".

Separately: the first run's raw Python error is a **Medium** diagnostics issue, the same as case 1.

## 12. Reproduction steps

From a clean baseline:
1. In `rhombus-takehome-v2`, confirm a manual ▶ run on `datasets/baseline.csv` matches baseline run 4 (SHA-256 `ebedc745…cdda`).
2. Save a Version Control snapshot.
3. Replace the input via Data Input → "From Device" with `datasets/schema_rename_column.csv`. Check that the input preview shows `order_date`. Don't click Apply on any node.
4. Trigger a manual ▶ run. Expected observation: it fails at `clean_transactions` with `['transaction_date'] not in index`, and no new object appears in `output`.
5. In the Logs tab, use "Ask Chatbot" on the error. Record the diagnosis, the alias names it proposes, and whether the change is applied automatically.
6. Trigger a manual ▶ run (`retest`). Record the warning and the final status. Download the new object from `output`.
7. Validate:
   ```
   python data-validation/validate.py --scenario schema-rename-column-retest --input datasets/schema_rename_column.csv --output <file> --baseline-output outputs/manual-dryrun-4.csv --report <report.json>
   ```
8. Restore: upload `datasets/baseline.csv`, restore the pre-fix pipeline from the snapshot, then trigger a manual ▶ run and confirm it matches run 4.

## 13. Evidence

- `observations/evidence/validation-schema-rename-column-retest.json`: validator report for the retest.
- `datasets/schema_rename_column.csv` and `.manifest.json`: the input.
- `observations/evidence/schema-rename-column-log.txt`: first-run log excerpt (sanitised).
- `observations/evidence/schema-rename-column-chatbot.txt`: chatbot exchange and retest messages (sanitised summary).
- [`observations/evidence/rename-retest-warning.png`](evidence/rename-retest-warning.png): it shows, together:
  - the retest warning "No results found after applying this LLM transformation";
  - "Pipeline completed successfully" at 15:55:07;
  - the first run's failure (15:53:39);
  - the chatbot's `column_guard` alias map reply (`date → transaction_date`, `quantity → qty`, `customer_name → name`, `txn_status → status`), with the extra node on the canvas;
  - the credit balance (4,943).
- **Also visible but not attributed:** a failure at 15:53:10 with `['country'] not in index`.
- Raw (gitignored): `evidence-raw/case2-log.txt`, `evidence-raw/case2-chatbot.txt`.
- The retest output itself is in `outputs/` (gitignored). It is only a 62-byte header, reproduced in full in section 3.

## Limitations

- **Mistaken run excluded.** One extra run was mistakenly made on `datasets/baseline.csv` instead of the renamed file. Its output (`outputs/schema-rename-column-INVALID.csv`) is excluded from all findings above. It was byte-identical to baseline run 4, as expected for a baseline input.
- **Root cause not observed.** Why the retest dropped every row hasn't been confirmed (section 3).
