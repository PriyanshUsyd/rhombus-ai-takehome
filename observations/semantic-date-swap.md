# Semantic drift: day/month swap (`semantic-date-swap`)

| | |
|---|---|
| **Run type** | `manual` ▶ run (D2: the scheduler never fired). No `retest`, because there was no error or warning. |
| **Project / workflow** | `rhombus-takehome-v2` / 5257 |
| **Date** | 2026-10-04 |
| **Verdicts** | Platform: **missed** · Validator: **caught, weakly** (one range metric; per-row errors invisible) · Final data risk: **High** |
| **Severity (proposed)** | **High**: see section 11 |

**Summary.** Day and month were swapped in 88 valid ISO dates where the day was 12 or less, so every date stays valid. The run reported **"Pipeline completed successfully" with no warning**. It delivered **81 of 218 rows (37%) with the wrong transaction date**: every one an exact day/month swap of the correct date.

Our validator flagged it through **one metric only**, the date range: the latest date moved from 2025-06-30 to 2025-12-06. It can't tell which rows are wrong. **40 of the 81 wrong dates fall inside the normal date range** and look entirely plausible.

## 1. Change

- **Dataset:** `datasets/semantic_date_swap.csv`, SHA-256 `056e9e44602190e4e740b4bd32fa7f98ac325218b2bb9af946486fd6d5ada04d` (manifest `datasets/semantic_date_swap.manifest.json`).
- **Derived from:** `datasets/baseline.csv` (SHA-256 `f2c301dc…c2a2`).
- **Exact change:** `transaction_date` in valid ISO dates with day ≤ 12 rewritten as `YYYY-DD-MM` (day and month swapped). That is **88 ids** in the input. For example `2025-05-03` → `2025-03-05`, and `2025-02-12` → `2025-12-02`.
- **Unchanged:**
  - 6 dates where day = month;
  - dates with day > 12;
  - non-ISO, impossible and empty dates;
  - every other cell, the header and the row count (250).
- **Swap results are all valid:** the original month (1–6) becomes the day, and the original day (≤ 12) becomes the month. No slash formats are used, so the baseline policy rejects nothing new.
- **Uploaded via:** Data Input → "From Device".
- **Upload time:** TODO.

## 2. Expected behaviour

Our expectation, not a Rhombus claim.
- **Under the cleaning rules,** every swapped date is a valid ISO date, so a pipeline that applies those rules correctly outputs 218 rows with the swapped dates.
- **Telling a swapped date from a real one** is impossible row by row: both are valid.
- **A platform could only notice in aggregate:** dates outside the dataset's usual period, or a changed month distribution compared with previous runs. It could then warn before delivering.

## 3. Actual behaviour

| Time (AEDT) | Event | What reached Azure `output` |
|---|---|---|
| 16:16:47 | Log: "Pipeline execution started" | — |
| 16:16:52 | Log: "Pipeline execution started" (a **second** start entry) | — |
| 16:16:54 | **"Pipeline completed successfully"**, no warning (one completion entry) | `RhombusAI_output_1791091017015.csv` → `outputs/semantic-date-swap.csv` |

Compared with baseline run 4 (`outputs/manual-dryrun-4.csv`):
- **Rows:** 218, with the same ids in the same order. The file size is the same (18,660 bytes), but the content differs.
- **Only `transaction_date` differs, on 81 rows.** Every difference is an exact day/month swap of the baseline date. For example id 1001: `2025-05-03` → `2025-03-05`; id 1008: `2025-02-12` → `2025-12-02`.
- **The 81 rows are exactly** the swapped ids that survive cleaning. The other 7 swapped ids (1036, 1073, 1093, 1107, 1139, 1164, 1171) are rejected or deduplicated in the baseline too.
- **The 6 unchanged dates** where day = month are in the output and identical to the baseline.
- **Known baseline defects** are present unchanged and are not new findings: 3 `None` names, and 70 money cells missing a trailing zero.

**Log oddity:**
- **Two "Pipeline execution started" entries** (16:16:47 and 16:16:52) appeared for **one** completion (16:16:54).
- Whether two runs were started and only one finished or logged, or one run was logged twice, is **not observed**. Only one output object was produced.
- TODO: check the Executions tab for this time window.

## 4. Pre-state / post-state

- **Pre-state:**
  - The pipeline was the baseline version (TODO: confirm with a Version Control snapshot).
  - The AI Builder history was cleared before the case (D2 method note).
  - TODO: schedule status, latest objects in `output`, last successful run.
- **Post-state:** TODO, same fields. No pipeline change was made: there was no chatbot step.

## 5. Run identity

| Run | Started–finished | Status | Output object | Local copy SHA-256 |
|---|---|---|---|---|
| `manual` | 16:16:47 or 16:16:52 (two start entries) – 16:16:54 | completed successfully | `RhombusAI_output_1791091017015.csv` | `1b01de957a33703047bac1e8a3885de2afba3934e9bb55578dabeaaeeb785664` (18,660 bytes) |

## 6. Logs

- **Run log:** two "Pipeline execution started" entries, then "Pipeline completed successfully". No warning, and nothing about the date range or distribution. TODO: paste a short sanitised excerpt.
- **Clear?**
  - For the data, the platform had nothing to report, and the silence is the finding.
  - The duplicate start entry makes the run history harder to trust: you can't tell from the log how many runs happened.

## 7. Chatbot

Not used: the run had no error or warning. There was no fix, config diff or retest.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used a manual run. Schedule state after the case: TODO.

## 9. Validation results

Report: `observations/evidence/validation-semantic-date-swap.json` (compared against baseline run 4). Overall: **fail**.

| Check | Status | Note |
|---|---|---|
| `input_contract`, `schema`, `deduplication` | pass | |
| `row_count_reconciliation` | pass | expected 218 = actual 218 |
| 13 of 14 `rule_*` checks | pass | including `rule_date_reformatted`: every date is valid ISO |
| `rule_name_missing_kept_null` | fail | 3: the known `None` names baseline defect |
| `values_match_policy` | fail | 3, all in `name` (the known defect). **Dates match the policy**, because the policy is applied to the swapped input. |
| `output_format` | fail | 70 `money_two_decimals`: the known trailing-zero baseline defect |
| `manifest_consistency` | not_applicable | the default manifest describes the baseline |
| `determinism` | not_applicable | the input isn't the baseline dataset |
| `semantic_anomaly` | **fail** | 1 metric, below |

| Metric | Baseline (run 4) | This run | Rule |
|---|---|---|---|
| `transaction_date.range` | 2025-01-01 – 2025-06-30 | 2025-01-01 – **2025-12-06** | dates outside the baseline output's range |

**Did not trip:**

| Metric | Baseline | This run | Why not |
|---|---|---|---|
| `transaction_date.month_histogram` | Jan–Jun only (34/34/40/30/40/40) | Jan–Dec (23/29/34/22/34/35, then 8/4/5/11/7/6) | total variation distance **0.188**, under the 0.25 threshold |
| `day_le_12_share` | 0.40367 | 0.40367 | not checked as a rule; also unchanged, because each swapped date still has day ≤ 12 (the new day is the old month, 1–6) |
| `parse_success_rate`, null rates, other columns | 1.0 / unchanged | 1.0 / unchanged | every swapped date is valid |

### What the detector can and can't see

- **Can't see:**
  - Which rows are wrong. Each swapped date is a valid date, so no single row can be flagged.
  - The policy checks confirm the dates were *cleaned* correctly, not that they are *correct*.
- **Can see:** only a shift in the overall distribution, compared with one earlier run.
  - Here that worked only because the baseline data covers January–June. 41 of the 81 swapped dates moved into July–December, outside that range.
  - The other **40 swapped dates landed inside January–June** and are invisible to every metric.
- **Fragile:**
  - The catch depends on the dataset's date window.
  - If the data covered a whole year, the range check wouldn't trip. The month histogram (0.188 here) would also probably stay below its threshold.
  - The detector would then report **pass** on an output with 37% of dates wrong.

## 10. Three verdicts

| Detector | Verdict | Evidence |
|---|---|---|
| **Platform behaviour** | **Missed** | "Pipeline completed successfully", no warning, and 81 swapped dates delivered to Azure `output`. |
| **Validator behaviour** | **Caught, weakly** | `semantic_anomaly` = fail on one metric (`transaction_date.range`, latest date 2025-06-30 → 2025-12-06). It can't identify the 81 wrong rows. It misses the 40 swaps that land inside the normal range. It would miss the whole change on full-year data. |
| **Final data risk** | **High** | 37% of transaction dates are wrong but valid, so no single row can be flagged. Anything grouped by date or month would be silently wrong (e.g. monthly revenue, December sales that didn't happen). The wrong rows can't be identified from the output alone, only by going back to the retained input. |

## 11. Severity

**Proposed: High.** This is **silent incorrect output**. The platform reported success with no warning, and delivered 81 of 218 rows with wrong, but valid, transaction dates. That is the rubric's High case. The rubric's principle that silent semantic corruption ranks above a visible failure puts it above the failing cases.

I considered Critical and didn't propose it, for consistency with `semantic-dollars-to-cents`:
- The corruption came from the input, and the pipeline applied its rules correctly.
- Recovery is to correct the source and re-run.

**This is the strongest Critical candidate of the seven cases:**
- Unlike the ×100 case, the wrong rows can't be identified in the output.
- Our own detector catches it only because of this dataset's date window.

**Why it stays High:**
- The rubric's Critical needs silent material corruption **and no reliable recovery path**.
- Here a recovery path exists. The input file is kept, the swapped rows are listed in its manifest, and the run can be redone from a corrected source to give the correct output.
- The corruption is silent and material, but recoverable.

## 12. Reproduction steps

From a clean baseline:
1. In `rhombus-takehome-v2`, confirm the pipeline is the baseline version, and that a manual ▶ run on `datasets/baseline.csv` matches baseline run 4 (SHA-256 `ebedc745…cdda`).
2. Clear the AI Builder chat history.
3. Replace the input via Data Input → "From Device" with `datasets/semantic_date_swap.csv`. Don't click Apply on any node.
4. Trigger a manual ▶ run. Expected observation: "Pipeline completed successfully", no warning, and a new object in `output`. Note how many "Pipeline execution started" entries appear.
5. Download the output and validate it:
   ```
   python data-validation/validate.py --scenario semantic-date-swap --input datasets/semantic_date_swap.csv --output <file> --baseline-output outputs/manual-dryrun-4.csv --report <report.json>
   ```
   Expected: `semantic_anomaly` fails on `transaction_date.range` only.
6. Compare with `outputs/manual-dryrun-4.csv` by id. Only `transaction_date` differs, on the 81 swapped ids still in the output (`semantic_date_swap.manifest.json` → `swapped_ids`).
7. Restore: upload `datasets/baseline.csv`. No pipeline change needs reverting.

## 13. Evidence

- `observations/evidence/validation-semantic-date-swap.json`: validator report.
- `datasets/semantic_date_swap.csv` and `.manifest.json`: the input, including the list of swapped ids.
- TODO (sanitised):
  - the run log showing both "Pipeline execution started" entries and the single completion;
  - the Executions tab for 16:16–16:17.
- The output itself is in `outputs/` (gitignored).

## Limitations

- **Duplicate start entry unexplained.** It's not known whether two runs were started (16:16:47 and 16:16:52). Only one output object is attributed to this case.
- **The validator's catch depends on the data.** The date-range check works only because the baseline covers January–June (section 9). This dataset's design flattered the detector, and that is reported rather than claimed as a strength.
