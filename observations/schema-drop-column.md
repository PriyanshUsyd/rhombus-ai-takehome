# Schema drift: drop column (`schema-drop-column`)

| | |
|---|---|
| **Run type** | `manual` ▶ run (D2: the scheduler never fired), then one `retest` after the chatbot fix |
| **Project / workflow** | `rhombus-takehome-v2` / 5257 |
| **Date** | 2026-10-04 |
| **Severity (proposed)** | **High**: see section 11 |

**Summary.** With `country` removed, the first run **failed closed**: no output was written, but the error was a raw Python message. The chatbot diagnosed the cause correctly and auto-applied a `column_guard` fix. The retest then **completed silently with incorrect data**:
- `country` is empty on all 222 rows.
- 4 rows that should be rejected for a missing or non-numeric price were kept.
- 3 valid `$`-prefixed prices were wiped to empty.

A loud failure was turned into silent bad output.

## 1. Change

- **Dataset:** `datasets/schema_drop_column.csv`, SHA-256 `670db8d3969e30a911e265f391597b244794818dd11ab2e4b5412afac993f675` (manifest `datasets/schema_drop_column.manifest.json`).
- **Derived from:** `datasets/baseline.csv` (SHA-256 `f2c301dc…c2a2`).
- **Exact change:** column `country` removed; every other cell is identical to the baseline (250 rows, 8 columns).
- **Uploaded via:** Data Input → "From Device".
- **Upload time:** not recorded.

## 2. Expected behaviour

Our expectation, not a Rhombus claim. The cleaning policy (`datasets/cleaning-policy.md` §1) lists `country` as a required input column, so a missing column breaks the input contract. A good pipeline would:
- stop, or warn clearly, naming the missing column;
- not write output that looks normal;
- not change how any other column is cleaned.

## 3. Actual behaviour

| Run | Outcome | What reached Azure `output` |
|---|---|---|
| First `manual` run | **Stopped.** Failed at step `clean_transactions` with `['country'] not in index`. | Nothing (no output written). |
| `retest` after the chatbot fix | **Carried on.** Completed; no error seen. Whether a warning was shown: not recorded. | `RhombusAI_output_1791089361234.csv` |

### What is wrong in the retest output

Compared with the baseline output (manual run 4, `outputs/manual-dryrun-4.csv`):

| Problem | Rows | Detail |
|---|---|---|
| `country` present but empty | all 222 | The guard re-added the column as empty. In the baseline, 213 of 218 rows had a country. |
| Rows kept that the policy rejects | 4 | ids 1139 and 1200 (input price empty) and 1164, 1199 (input price `abc` / `ten`). They now appear with an empty price and a total. The baseline correctly rejected them. Row count is **222 instead of 218**. |
| Valid prices wiped | 3 | ids 1100, 1203 and 1207 had `$`-prefixed input prices (`$334.32`, `$131.96`, `$242.08`). The baseline output had `334.32`, `131.96`, `242.08`; the retest has an **empty** price. The totals are kept, so these rows now have a total but no price. |
| Everything else | — | No other cell differs from the baseline, and row order is the same. |

The 3 wiped prices and 4 un-rejected rows involve `price`, not `country`. So the fix changed how a column unrelated to the drift is cleaned. Why it did is **not observed**: the config diff (section 7) would show it.

Known baseline defects, not new findings: the 3 `None` names (ids 1017, 1039, 1198) and the missing trailing zeros on money values. The retest has 71 such money cells instead of 70; the extra one is total `2562.0` on id 1200, a row that shouldn't be in the output at all.

## 4. Pre-state / post-state

- **Pre-state:**
  - Input: section 1.
  - Pipeline: not separately recorded. This was the first drift case after baseline run 4.
  - Schedule: Active, hourly, never fired (see `PLAN.md` → "Findings log").
  - Last successful run (latest output blob before the case): `RhombusAI_output_1791087076533.csv` (15:11:16, baseline run 4).
  - Snapshot: not captured.
- **Post-state:**
  - Pipeline: contains the chatbot's `column_guard` node.
  - Schedule: Active, hourly, never fired (see `PLAN.md` → "Findings log").
  - Latest output: `RhombusAI_output_1791089361234.csv` (15:49:21).

## 5. Run identity

| Run | Started | Status | Output object | Local copy SHA-256 |
|---|---|---|---|---|
| `manual` | 15:46:21–15:46:26 (log) | failed; the log also shows "Pipeline execution completed successfully." at 15:46:26 | none | — |
| `retest` | 15:49:21 (object time) | completed | `RhombusAI_output_1791089361234.csv` | `9a6c4db4cca57097a13e2b6c9439c4e56aa1d0968e91501fc2b1b0d3970a2729` (`outputs/schema-drop-column-retest.csv`) |

## 6. Logs

- **Excerpt** (`observations/evidence/schema-drop-column-log.txt`): `Pipeline failed at clean_transactions: LLM execution failed (code_sha=5e6c1f84d511): "['country'] not in index" --- Generated code --- import pandas as pd import numpy as np def _safe_to_timedelta_wrapper(arg, *args, **kwargs): …`
- The user-facing log entry contains the raw generated pipeline code after the error.
- **Clear?** **Partly.** It names the missing column, so a developer can work out the cause. But it's a raw Python/pandas `KeyError` message plus generated code. It doesn't say "input column `country` is missing", and it doesn't point to the input file or the schema change.

## 7. Chatbot

- **Prompt:** "Please help me fix the following error:" + the error text, sent by the "Ask Chatbot" button on the failed log entry.
- **Diagnosis: correct** (`observations/evidence/schema-drop-column-chatbot.txt`). `src` loads `schema_drop_column.csv`, which has no `country`, and the generated code ends with `output_df = df[final_columns].copy()`, raising a `KeyError`.
- **Change:** a new `column_guard` node between `src` and `clean_transactions` that adds any missing expected column as empty (`np.nan`). The pipeline became `src → column_guard → clean_transactions → src_output`.
- **Applied: automatically, with no confirmation asked.**
- **Also suggested:** switching `src` back to `baseline.csv`.
- **Cost:** 15 credits (4963 → 4948).
- **Config diff:** not captured. No Version Control snapshot was taken per fix; the fix is described from the chatbot's own reply (limitation, see README). So why price handling changed is not established.
- **Retest:** completed. Output as described in section 3.
- **Fix grade:** **didn't work, harmful.** The run completes, but:
  - the output is silently wrong: `country` is empty everywhere and nothing tells the user;
  - it breaks price rejection (4 rows) and `$` stripping (3 rows), which are unrelated to the drift.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used manual runs. Schedule state after the case: Active, hourly, never fired (see `PLAN.md` → "Findings log").

## 9. Validation results

Retest report: `observations/evidence/validation-schema-drop-column-retest.json` (compared against baseline run 4). Overall: **fail**.

| Check | Status | Note |
|---|---|---|
| `input_contract` | fail | required column `country` missing |
| `schema` | pass | the output has all 9 columns because the guard re-added `country` |
| `deduplication`, `row_count_reconciliation`, `manifest_consistency`, all 14 `rule_*` checks, `values_match_policy` | blocked_by_schema | the input contract is broken, so the validator doesn't derive expectations |
| `output_format` | fail | 71 money cells missing their trailing zero: 70 are the known baseline defect, and 1 is in id 1200, a row that should have been rejected |
| `determinism` | not_applicable | the input isn't the baseline dataset |
| `semantic_anomaly` | **fail** | `country.null_rate` 0.022936 → **1.0** (rule: absolute increase > 0.05); `country.distribution` 8 countries → **empty** (rule: total variation distance > 0.25) |

The semantic detector caught the empty `country`. It didn't catch the 4 extra rows (a 1.8% row-count change, below the 10% threshold) or the 3 wiped prices (price null rate 0 → 7/222 ≈ 3.2%, below the 0.05 threshold).

**Found manually:** I found the extra rows and wiped prices by comparing the output cell by cell with baseline run 4, not through a validator check. This is a validator gap: with the contract broken, its row-level checks are blocked, so nothing compares the remaining columns.

## 10. Three verdicts

Not a semantic case; this section doesn't apply.

## 11. Severity

**Proposed: High.** The platform failed closed on the drift, which is good. But the chatbot's auto-applied fix turned it into **silent incorrect output**: `country` is blanked for every row, 4 untrustworthy rows are kept, and 3 valid prices are wiped. Nothing in the run reported a problem. That is the rubric's High case ("silent incorrect output … failed recovery path").

I considered Critical and didn't propose it:
- The corruption is limited to 7 rows plus one column that is visibly empty.
- Recovery is possible: remove the guard node and re-run.

**Kept at High.** The check that could raise it to Critical can't be done (see Limitations).

Separately: the raw Python error on the first run is a **Medium** usability issue, because the diagnostics are incomplete.

## 12. Reproduction steps

From a clean baseline:
1. In `rhombus-takehome-v2`, confirm a manual ▶ run on `datasets/baseline.csv` matches baseline run 4 (SHA-256 `ebedc745…cdda`).
2. Save a Version Control snapshot.
3. Replace the input via Data Input → "From Device" with `datasets/schema_drop_column.csv`. Don't click Apply on any node.
4. Trigger a manual ▶ run. Expected observation: it fails at `clean_transactions` with `['country'] not in index`, and no new object appears in `output`.
5. In the Logs tab, use "Ask Chatbot" on the error. Record the diagnosis and the change it applies.
6. Trigger a manual ▶ run (`retest`). Download the new object from `output`.
7. Validate:
   ```
   python data-validation/validate.py --scenario schema-drop-column-retest --input datasets/schema_drop_column.csv --output <file> --baseline-output outputs/manual-dryrun-4.csv --report <report.json>
   ```
8. Compare the output with `outputs/manual-dryrun-4.csv` by id: price on ids 1100, 1203, 1207; extra ids 1139, 1164, 1199, 1200.
9. Before restoring, run `datasets/baseline.csv` through the fixed pipeline once and keep the output. This was **not done** in this test (see Limitations). Then upload `datasets/baseline.csv`, restore the pre-fix pipeline from the snapshot, trigger a manual ▶ run, and confirm it matches run 4.

## 13. Evidence

- `observations/evidence/validation-schema-drop-column-retest.json`: validator report for the retest.
- `datasets/schema_drop_column.csv` and `.manifest.json`: the input.
- `observations/evidence/schema-drop-column-log.txt`: run log excerpt (sanitised).
- `observations/evidence/schema-drop-column-chatbot.txt`: chatbot exchange (sanitised summary).
- [`observations/evidence/drop-column-guard.png`](evidence/drop-column-guard.png): it shows, together:
  - the failed run (15:46:21 started; 15:46:26 failed, next to a "completed successfully" entry);
  - the chatbot's reply, "Fix applied: A new column_guard node was inserted between src and clean_transactions", with its suggestion to switch `src` back to `baseline.csv`;
  - the extra node on the canvas;
  - the credit balance (4,948).
- Retest run screenshot: **not captured** (see Limitations). The retest is identified by its output object and hash (section 5).
- Raw (gitignored, not published): `evidence-raw/case1-log.txt`, `evidence-raw/case1-chatbot.txt`.
- [`observations/evidence/schema-drop-column-retest-output.csv`](evidence/schema-drop-column-retest-output.csv): the retest output, published unchanged (SHA-256 `9a6c4db4…2729`). It contains only synthetic data; its emails use reserved `example.*` domains.

## Limitations

- **No screenshot of the retest run.** It was not captured; the retest is evidenced by its Azure object (`RhombusAI_output_1791089361234.csv`, 15:49:21), its hash and the validator report.
- **Fixed pipeline not tested on the baseline.** The pipeline was restored before the baseline could be run through the version with the chatbot's `column_guard`. So it's **not observed** whether that version would also blank `$` prices and keep bad-price rows on the baseline input, which would mean silent corruption on every future run. Severity stays at High. If it had, it would have been Critical.
