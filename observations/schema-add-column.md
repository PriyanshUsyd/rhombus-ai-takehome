# Schema drift: add column (`schema-add-column`)

| | |
|---|---|
| **Run type** | `manual` ▶ run (D2: the scheduler never fired). No `retest`, because there was no error. |
| **Project / workflow** | `rhombus-takehome-v2` / 5257 |
| **Date** | 2026-10-04 |
| **Severity (proposed)** | **Info**: see section 11 |

**Summary.** With a new column `channel` appended, the run completed with no error. The output **drops `channel`** and is **byte-identical to baseline run 4**: same 218 rows, same 9 columns, same values. The pipeline handled an additive schema change correctly. The only gap is that it dropped the new column without telling the user.

## 1. Change

- **Dataset:** `datasets/schema_add_column.csv`, SHA-256 `3616d51123e91c5ae262bd0a1f990b91dbbe260008a3159ff33db42d9a631d31` (manifest `datasets/schema_add_column.manifest.json`).
- **Derived from:** `datasets/baseline.csv` (SHA-256 `f2c301dc…c2a2`).
- **Exact change:** new column `channel` added as the **last** column. Its values are `web` / `store` / `app` (taken from the id), never empty. The first 9 columns are identical to the baseline (250 rows, 10 columns).
- **Uploaded via:** Data Input → "From Device".
- **Upload time:** not recorded.

## 2. Expected behaviour

Our expectation, not a Rhombus claim. The build prompt says "Keep exactly these 9 columns, in this order, with these names. Do not add any other columns", and the approved policy does the same (`datasets/cleaning-policy.md`). So a correct pipeline:
- ignores or drops `channel`;
- produces exactly the baseline output (218 rows);
- ideally mentions that an unexpected input column was dropped.

## 3. Actual behaviour

| Run | Outcome | What reached Azure `output` |
|---|---|---|
| `manual` | **Carried on, no error.** No warning reported; Logs tab contents not recorded. | `RhombusAI_output_1791090284446.csv` (16:04:44) → `outputs/schema-add-column.csv` |

- **Header:** `id,name,email,country,price,qty,total,transaction_date,status`. **`channel` is absent.** None of the values `web`, `store` or `app` appear anywhere in the file.
- **Byte-identical to baseline run 4:** both files are 18,660 bytes with SHA-256 `ebedc745b23296ff1c77ced008d0dd27e051d7c1f091c1cd1efa43147310cdda`. They are therefore data-identical too: 218 rows, the same ids, order and cell values.
- **Known baseline defects** are present unchanged and are not new findings: 3 `None` names (ids 1017, 1039, 1198), and 70 money cells missing a trailing zero.

**Input confirmed by a re-run at 18:30.** For this input the correct output equals the baseline output, so the 16:04 output alone couldn't show which input was read.
- [`observations/evidence/case4-input-preview.png`](evidence/case4-input-preview.png) shows the Data Input panel with **`schema_add_column.csv` selected**, and the input node labelled `schema_add_col…`.
- Two ▶ runs at 18:30 (logged 18:30:12–18:30:15 and 18:30:25–18:30:29) wrote `RhombusAI_output_1791099018130.csv` (18:30:18) and `RhombusAI_output_1791099031596.csv` (18:30:31).
- Both are **byte-identical to baseline run 4**, checked by Claude via the container listing.

This reproduces the case 4 result with the drifted input visibly selected. The screenshot was taken at 18:30, so it doesn't directly show the input of the original 16:04 run.

## 4. Pre-state / post-state

- **Pre-state:**
  - Pipeline: **restored from the saved version** before this case.
  - **The AI Builder chat history was cleared before this case.** This is a method change: the chatbot re-applied reverted fixes in case 3, and clearing the history stops it doing that again.
  - Schedule: Active, hourly, never fired (see `PLAN.md` → "Findings log").
  - Last successful run (latest output blob before the case): `RhombusAI_output_1791090280649.csv` (16:04:40). It and `RhombusAI_output_1791090265384.csv` (16:04:25) are 18,660-byte objects not attributed to a recorded run. The latest attributed run was case 3's retest (16:02:39).
  - Snapshot: not captured.
- **Post-state:**
  - Pipeline: unchanged (no chatbot step).
  - Schedule: Active, hourly, never fired (see `PLAN.md` → "Findings log").
  - Latest output: `RhombusAI_output_1791090284446.csv` (16:04:44).

## 5. Run identity

| Run | Started | Status | Output object | Local copy SHA-256 |
|---|---|---|---|---|
| `manual` | 16:04:44 (object time) | completed (exact status text not recorded) | `RhombusAI_output_1791090284446.csv` | `ebedc745b23296ff1c77ced008d0dd27e051d7c1f091c1cd1efa43147310cdda` (18,660 bytes) |

## 6. Logs

- **Errors or warnings:** none reported. No log excerpt was captured.
- **Clear?** There's nothing to explain about a failure. But the run doesn't say that an extra input column was dropped, which a user would want to know. Whether the log mentions it: not recorded.

## 7. Chatbot

Not used: the run had no error or warning. There was no fix, config diff or retest.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used a manual run. Schedule state after the case: Active, hourly, never fired (see `PLAN.md` → "Findings log").

## 9. Validation results

Report: `observations/evidence/validation-schema-add-column.json` (compared against baseline run 4). Overall: **fail, from the known baseline defects only.**

| Check | Status | Note |
|---|---|---|
| `input_contract` | pass | warning: extra column `channel` (policy: the output keeps only the 9 contract columns) |
| `schema`, `deduplication`, `row_count_reconciliation` | pass | expected 218 = actual 218 |
| 13 of 14 `rule_*` checks | pass | |
| `rule_name_missing_kept_null` | fail | 3: the known `None` names baseline defect |
| `values_match_policy` | fail | 3: the same `None` names |
| `output_format` | fail | 70 `money_two_decimals`: the known trailing-zero baseline defect |
| `manifest_consistency` | not_applicable | the default manifest describes the baseline |
| `determinism` | not_applicable | the input isn't the baseline dataset |
| `semantic_anomaly` | pass | no anomalies against run 4 |

## 10. Three verdicts

Not a semantic case; this section doesn't apply.

## 11. Severity

**Proposed: Info.** The additive schema change was **handled well**: the output exactly matches the baseline and follows the "keep exactly these 9 columns" rule. The only point is a non-blocking improvement: the platform could tell the user that an unexpected input column was dropped. That fits the rubric's Info ("handled well, or non-blocking improvement").

## 12. Reproduction steps

From a clean baseline:
1. In `rhombus-takehome-v2`, confirm the pipeline is the baseline version, and that a manual ▶ run on `datasets/baseline.csv` matches baseline run 4 (SHA-256 `ebedc745…cdda`).
2. Clear the AI Builder chat history (method used from this case on).
3. Replace the input via Data Input → "From Device" with `datasets/schema_add_column.csv`. Check that the input preview shows `channel`. Don't click Apply on any node.
4. Trigger a manual ▶ run. Expected observation: no error, and a new object in `output`.
5. Download it and check it's byte-identical to `outputs/manual-dryrun-4.csv`:
   ```
   sha256sum <file> outputs/manual-dryrun-4.csv
   ```
6. Validate:
   ```
   python data-validation/validate.py --scenario schema-add-column --input datasets/schema_add_column.csv --output <file> --baseline-output outputs/manual-dryrun-4.csv --report <report.json>
   ```
7. Restore: upload `datasets/baseline.csv`. No pipeline change needs reverting.

## 13. Evidence

- `observations/evidence/validation-schema-add-column.json`: validator report.
- `datasets/schema_add_column.csv` and `.manifest.json`: the input.
- [`observations/evidence/case4-input-preview.png`](evidence/case4-input-preview.png): `schema_add_column.csv` selected; logs from the 18:30 re-runs (section 3).
- Run log or status for the 16:04 run (`RhombusAI_output_1791090284446.csv`): **not captured** (see Limitations).
- The output itself is in `outputs/` (gitignored). It's byte-identical to baseline run 4.

## Limitations

- **Input of the 16:04 run.** The drifted input is visibly selected in an 18:30 re-run that produced byte-identical output (section 3). There's no screenshot from the original 16:04 run itself.
- **No log for the 16:04 run.** Its run log and status text were not captured. The run is evidenced by its Azure object (16:04:44), its hash and the validator report.
- **Method change.** The AI Builder history was cleared before this case, so cases 1–3 and cases 4–7 ran under different conditions for the chatbot. That doesn't affect this case, which didn't use the chatbot.
