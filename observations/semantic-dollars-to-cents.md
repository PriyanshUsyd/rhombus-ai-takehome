# Semantic drift: dollars to cents (`semantic-dollars-to-cents`)

| | |
|---|---|
| **Run type** | `manual` ▶ run (D2: the scheduler never fired). No `retest`, because there was no error or warning. |
| **Project / workflow** | `rhombus-takehome-v2` / 5257 |
| **Date** | 2026-10-04 |
| **Verdicts** | Platform: **missed** · Validator: **caught** · Final data risk: **High** |
| **Severity (proposed)** | **High**: see section 11 |

**Summary.** `price` and `total` were multiplied by 100 in the input; the structure is unchanged and price × qty = total still holds. The run reported **"Pipeline completed successfully" with no warning** and delivered **every money value inflated 100×** to the destination: total revenue 309,572.79 → 30,957,279.0. Our validator's semantic detector flagged it (4 metrics, each exactly ×100). Every policy-based check stays silent, because the data is internally consistent.

## 1. Change

- **Dataset:** `datasets/semantic_dollars_to_cents.csv`, SHA-256 `2e459bbe8a861f89da195b8b79c26bdae3b5ac6c9cc4b6d1030332133a5ccef1` (manifest `datasets/semantic_dollars_to_cents.manifest.json`).
- **Derived from:** `datasets/baseline.csv` (SHA-256 `f2c301dc…c2a2`).
- **Exact change:**
  - Every numeric `price` (230 ids) and every non-empty `total` (231 ids) multiplied by 100, keeping the same text format (2 decimals, any `$` kept). For example `222.97` → `22297.00`, and `$334.32` → `$33432.00`.
  - Empty and text cells are unchanged.
  - Header, column order, row count (250) and every other cell are identical to the baseline.
  - price × qty = total still holds wherever it held before.
- **Uploaded via:** Data Input → "From Device".
- **Upload time:** TODO.

## 2. Expected behaviour

Our expectation, not a Rhombus claim.
- **Under the cleaning rules,** the input is valid: every value is a number and the cross-field rule holds. A pipeline that only applies those rules would correctly output 218 rows with values ×100.
- **What a robust platform could do** is notice that a monetary column's scale jumped 100× from previous runs, and warn before delivering. For example, compare against previous runs' distributions, or let the user set a value range.

The brief's question is whether Rhombus notices a change in meaning when the structure is identical.

## 3. Actual behaviour

| Time (AEDT) | Event | What reached Azure `output` |
|---|---|---|
| 16:14:26 | Log: "Pipeline failed at src_output: A destination is required when remote export is selected". Probably triggered by clicking Apply (see Limitations). | Nothing |
| 16:14:31–16:14:34 | **`manual` run: "Pipeline completed successfully", no warning** | `RhombusAI_output_1791090876827.csv` → `outputs/semantic-dollars-to-cents.csv` |

Compared with baseline run 4 (`outputs/manual-dryrun-4.csv`):
- **Rows:** 218, with the same ids in the same order.
- **Price and total:** all 218 `price` and all 218 `total` cells are **exactly 100×** the baseline value; there are no other differences. For example, id 1001: price `222.97` → `22297.0`, total `1114.85` → `111485.0`.
- **Other columns:** identical to the baseline.
- **Cross-field rule:** total = price × qty still holds on every row (0 cross-field failures).

**Money formatting:**
- All 436 money cells are written with one decimal (`22297.0`), so `output_format` flags 436 cells against the baseline's 70.
- This is the **known trailing-zero baseline defect**, not a new finding. Every value ×100 ends in `.00`, so the defect now hits every money cell.
- The other known defect (3 `None` names: 1017, 1039, 1198) is also present unchanged.

## 4. Pre-state / post-state

- **Pre-state:**
  - The pipeline was the baseline version, restored after case 5 (TODO: confirm with a Version Control snapshot).
  - The AI Builder history was cleared before the case (D2 method note).
  - TODO: schedule status, latest objects in `output`, last successful run.
- **Post-state:** TODO, same fields. No pipeline change was made: there was no chatbot step.

## 5. Run identity

| Run | Started–finished | Status | Output object | Local copy SHA-256 |
|---|---|---|---|---|
| (Apply-triggered, not a test run) | 16:14:26 | failed at `src_output` | none | — |
| `manual` | 16:14:31–16:14:34 | completed successfully | `RhombusAI_output_1791090876827.csv` | `0d4ab83ac114be1e9a798970e16c1e3caab6169c97f44563c878047c700997a5` (19,166 bytes) |

## 6. Logs

- **Test run:** "Pipeline completed successfully". There is no warning, and nothing about value ranges or a change in scale. TODO: paste a short sanitised excerpt.
- **Earlier failed run (16:14:26):** "Pipeline failed at src_output: A destination is required when remote export is selected". TODO: paste the excerpt. The message suggests the export node had no destination configured at that moment. Why is **not observed**: the Azure destination was configured, and the run 5 seconds later wrote to it.
- **Clear?** For the test run, there was nothing to explain from the platform's side. The silence *is* the finding.

## 7. Chatbot

Not used: the run had no error or warning. There was no fix, config diff or retest.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used a manual run. Schedule state after the case: TODO.

## 9. Validation results

Report: `observations/evidence/validation-semantic-dollars-to-cents.json` (compared against baseline run 4). Overall: **fail**.

| Check | Status | Note |
|---|---|---|
| `input_contract`, `schema`, `deduplication` | pass | |
| `row_count_reconciliation` | pass | expected 218 = actual 218 |
| 13 of 14 `rule_*` checks | pass | price, total and date rules all pass on the ×100 values |
| `rule_name_missing_kept_null` | fail | 3: the known `None` names baseline defect |
| `values_match_policy` | fail | 3, all in `name` (the known defect). **Price and total match the policy**, because the policy is applied to the ×100 input. |
| `output_format` | fail | 436 `money_two_decimals`: the known trailing-zero defect, now hitting every money cell |
| `manifest_consistency` | not_applicable | the default manifest describes the baseline |
| `determinism` | not_applicable | the input isn't the baseline dataset |
| `semantic_anomaly` | **fail** | 4 metrics, below |

| Metric | Baseline (run 4) | This run | Ratio | Rule |
|---|---|---|---|---|
| `price.sum` | 54012.32 | **5401232.0** | ×100 | ratio outside [0.5, 2.0] |
| `price.p50` | 237.29 | **23729.0** | ×100 | ratio outside [0.5, 2.0] |
| `total.sum` | 309572.79 | **30957279.0** | ×100 | ratio outside [0.5, 2.0] |
| `total.p50` | 1052.17 | **105217.0** | ×100 | ratio outside [0.5, 2.0] |

- **Not tripped:** row count, null rates, country, status and date distributions, the duplicate-key count, and cross-field failures (0).
- **Only the semantic detector catches it.** Every policy-based check passes for price and total, because the policy derives its expectations from the (×100) input. It confirms the pipeline cleaned the data correctly, not that the data means the right thing.

## 10. Three verdicts

| Detector | Verdict | Evidence |
|---|---|---|
| **Platform behaviour** | **Missed** | "Pipeline completed successfully", no warning, and the 100× values were delivered to Azure `output`. |
| **Validator behaviour** | **Caught** | `semantic_anomaly` = fail on 4 metrics (price and total sum and median), each exactly ×100 the baseline. The policy checks were correctly silent. |
| **Final data risk** | **High** | Every monetary value in the destination is 100× too large, but internally consistent (total = price × qty), so downstream sanity checks on the row itself won't catch it. Revenue figures would be overstated 100×. |

## 11. Severity

**Proposed: High.** This is **silent incorrect output**. The platform reported success with no warning, and delivered every monetary value 100× too large to the destination. That is the rubric's High case. The rubric's principle that silent semantic corruption ranks above a visible failure puts it above the failing cases like case 5.

I considered Critical (material corruption, silent) and didn't propose it:
- The corruption came from the input. The pipeline applied its rules correctly.
- An independent check (our semantic detector, with run 4 as reference) catches it at once.
- The fix is to correct the source file and re-run.

It would be Critical in a setup without such a check: nothing on the platform side would ever flag it.

## 12. Reproduction steps

From a clean baseline:
1. In `rhombus-takehome-v2`, confirm the pipeline is the baseline version, and that a manual ▶ run on `datasets/baseline.csv` matches baseline run 4 (SHA-256 `ebedc745…cdda`).
2. Clear the AI Builder chat history.
3. Replace the input via Data Input → "From Device" with `datasets/semantic_dollars_to_cents.csv`. **Don't click Apply on any node.**
4. Trigger a manual ▶ run. Expected observation: "Pipeline completed successfully", no warning, and a new object in `output`.
5. Download the output and validate it against the baseline:
   ```
   python data-validation/validate.py --scenario semantic-dollars-to-cents --input datasets/semantic_dollars_to_cents.csv --output <file> --baseline-output outputs/manual-dryrun-4.csv --report <report.json>
   ```
   Expected: `semantic_anomaly` fails on `price.sum`, `price.p50`, `total.sum` and `total.p50` (each ×100).
6. Restore: upload `datasets/baseline.csv`. No pipeline change needs reverting.

## 13. Evidence

- `observations/evidence/validation-semantic-dollars-to-cents.json`: validator report.
- `datasets/semantic_dollars_to_cents.csv` and `.manifest.json`: the input.
- TODO (sanitised):
  - the run log showing "Pipeline completed successfully" with no warning (16:14:31–16:14:34);
  - the 16:14:26 `src_output` failure log.
- The output itself is in `outputs/` (gitignored).

## Limitations

- **Extra failed run.** A failed run at **16:14:26** ("A destination is required when remote export is selected") came 5 seconds before the test run. It was probably triggered by clicking Apply, which the protocol says not to do between the file swap and the run.
  - It failed at `src_output` and wrote nothing, so it doesn't affect the measured run, which started at 16:14:31.
  - The message itself (a missing destination while one was configured) is unexplained and not observed further.
- **Scale-check sensitivity.** The validator's scale check compares against one reference run (baseline run 4). It flags a ×100 change easily, but it would miss smaller unit changes within its [0.5, 2.0] ratio bounds.
