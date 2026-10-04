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
- **Upload time:** TODO.

## 2. Expected behaviour

Our expectation, not a Rhombus claim. The build prompt says "Keep exactly these 9 columns, in this order, with these names. Do not add any other columns", and the approved policy does the same (`datasets/cleaning-policy.md`). So a correct pipeline:
- ignores or drops `channel`;
- produces exactly the baseline output (218 rows);
- ideally mentions that an unexpected input column was dropped.

## 3. Actual behaviour

| Run | Outcome | What reached Azure `output` |
|---|---|---|
| `manual` | **Carried on, no error.** No warning reported (TODO: confirm the Logs tab shows no warning). | `RhombusAI_output_1791090284446.csv` (16:04:44) → `outputs/schema-add-column.csv` |

- **Header:** `id,name,email,country,price,qty,total,transaction_date,status`. **`channel` is absent.** None of the values `web`, `store` or `app` appear anywhere in the file.
- **Byte-identical to baseline run 4:** both files are 18,660 bytes with SHA-256 `ebedc745b23296ff1c77ced008d0dd27e051d7c1f091c1cd1efa43147310cdda`. They are therefore data-identical too: 218 rows, the same ids, order and cell values.
- **Known baseline defects** are present unchanged and are not new findings: 3 `None` names (ids 1017, 1039, 1198), and 70 money cells missing a trailing zero.

**Limitation of this evidence:** for this input, the correct output is the same as the baseline output. So the output alone can't show the run read `schema_add_column.csv` rather than the earlier baseline input. The fresh object name and time show it was a new run, not that it used the new input. TODO: add a screenshot of the Data Input preview showing the `channel` column, or a log line naming the file.

## 4. Pre-state / post-state

- **Pre-state:**
  - The pipeline was restored to the baseline version after case 3 (TODO: confirm with a Version Control snapshot).
  - **The AI Builder chat history was cleared before this case.** This is a method change: the chatbot re-applied reverted fixes in case 3, and clearing the history stops it doing that again.
  - TODO: schedule status, latest objects in `output`, last successful run.
- **Post-state:** TODO, same fields. The pipeline config didn't change during this case: there was no chatbot step.

## 5. Run identity

| Run | Started | Status | Output object | Local copy SHA-256 |
|---|---|---|---|---|
| `manual` | 16:04:44 (object time) | completed (TODO: exact status text) | `RhombusAI_output_1791090284446.csv` | `ebedc745b23296ff1c77ced008d0dd27e051d7c1f091c1cd1efa43147310cdda` (18,660 bytes) |

## 6. Logs

- **Errors or warnings:** none reported. TODO: paste a short sanitised excerpt of the run log.
- **Clear?** There's nothing to explain about a failure. But the run doesn't say that an extra input column was dropped, which a user would want to know. TODO: confirm from the log.

## 7. Chatbot

Not used: the run had no error or warning. There was no fix, config diff or retest.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used a manual run. Schedule state after the case: TODO.

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
- TODO (sanitised):
  - a screenshot of the Data Input preview showing `channel`, which proves the drifted input was used;
  - the run log or status for `RhombusAI_output_1791090284446.csv`.
- The output itself is in `outputs/` (gitignored). It's byte-identical to baseline run 4.

## Limitations

- **Input use not proven.** The correct output for this input equals the baseline output, so the output alone can't prove the drifted input was read (section 3). The Data Input preview screenshot would close this gap.
- **Method change.** The AI Builder history was cleared before this case, so cases 1–3 and cases 4–7 ran under different conditions for the chatbot. That doesn't affect this case, which didn't use the chatbot.
