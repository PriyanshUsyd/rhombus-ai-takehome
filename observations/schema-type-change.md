# Schema drift: type change (`schema-type-change`)

| | |
|---|---|
| **Run type** | `manual` ▶ run (D2: the scheduler never fired), then one `retest` after the chatbot fix |
| **Project / workflow** | `rhombus-takehome-v2` / 5257 |
| **Date** | 2026-10-04 |
| **Severity (proposed)** | **High**: see section 11 |

**Summary.** `price` changed from numbers to text (`222.97` → `USD 222.97`). The first run **carried on with no error**: it rejected every row and wrote a **header-only file (0 of 218 rows)** to Azure. The only signal was the warning "No results found after applying this LLM transformation".

The chatbot didn't read the file and guessed the wrong column first. It also claimed the total check uses a 1e-9 tolerance, which contradicts the pipeline's own Custom node prompt ("…ROUND_HALF_UP via decimal.Decimal"; see section 7). When told the real cause and asked to "change nothing else", it **re-applied every earlier fix that had been reverted** and added a USD strip. The retest output is **byte-identical to the first run: still 0 rows**.

## 1. Change

- **Dataset:** `datasets/schema_type_change.csv`, SHA-256 `227b3d8a6876a3bd26e36c7d5bc503218ff27cf98bd0d8ce06deaaac0a14f7c9` (manifest `datasets/schema_type_change.manifest.json`).
- **Derived from:** `datasets/baseline.csv` (SHA-256 `f2c301dc…c2a2`).
- **Exact change:**
  - Every numeric `price` (230 ids, including the 3 with a leading `$`) is written as `USD <number>`, e.g. `222.97` → `USD 222.97` and `$334.32` → `USD 334.32`.
  - The 4 prices that were empty or already text (`abc`, `ten`) are unchanged.
  - Every other cell is identical to the baseline (250 rows, 9 columns, same header).
- **Uploaded via:** Data Input → "From Device".
- **Upload time:** not recorded.

## 2. Expected behaviour

Our expectation, not a Rhombus claim. The header is unchanged, so this drift is only visible in the values: the whole `price` column is no longer numeric.
- **Row by row,** the approved policy (`datasets/cleaning-policy.md`, STEP 4 of the build prompt) rejects any row whose price "is not a number". Applied literally, that rejects all 234 unique rows, so the expected output is **0 rows**. The validator computes exactly this (section 9).
- **At the pipeline level,** a good pipeline would notice that 100% of a column failed to parse. It would stop or warn clearly that `price` changed type, instead of quietly rejecting every row and delivering an empty file.

So the empty output follows the cleaning rules. The finding is that nothing treats "every row rejected" as a failure.

## 3. Actual behaviour

| Run | Outcome | What reached Azure `output` |
|---|---|---|
| First `manual` run | **Carried on, no error.** Warning: "No results found after applying this LLM transformation". Final run status text: not recorded. | `RhombusAI_output_1791089840449.csv` (15:57:20; matched to `outputs/schema-type-change.csv` by time and size): header-only, **62 bytes, 0 data rows** |
| `retest` after the chatbot fix | Run status and warnings: not recorded. | `RhombusAI_output_1791090159425.csv` (16:02:39): header-only, **62 bytes, 0 data rows** (`outputs/schema-type-change-retest.csv`) |

Both outputs consist only of this line:
```
id,name,email,country,price,qty,total,transaction_date,status
```

- **Identical files.** The two outputs are byte-identical (SHA-256 `260801d0…fb3c`), which is also the hash of case 2's header-only retest.
- **Retest is a genuine new run.** Any header-only file has this hash, so the hash alone couldn't show it was new. The object name and timestamp (`RhombusAI_output_1791090159425.csv`, 16:02:39) confirm it.
- **The USD strip had no effect:** every row was still dropped.
- **Unanswerable from this output:** whether prices match baseline run 4, whether the `None` names are fixed, and whether trailing zeros are fixed. There are no rows to check, in either output.

## 4. Pre-state / post-state

- **Pre-state:**
  - Input: section 1.
  - Pipeline: **restored from the saved version** before this case. Confirmed: the canvas showed only Data Input → Custom → Data Output, with no `column_guard`.
  - Schedule: Active, hourly, never fired (see `PLAN.md` → "Findings log").
  - Last successful run (latest output blob before the case): `RhombusAI_output_1791089709537.csv` (15:55:09, case 2 retest; header-only).
  - Snapshot: not captured.
- **Unattributed blobs:** two more header-only objects were written between the first run and the retest, `RhombusAI_output_1791090030565.csv` (16:00:30) and `RhombusAI_output_1791090068666.csv` (16:01:08). They aren't attributed to a recorded run.
- **Post-state:** schedule Active, hourly, never fired (see `PLAN.md` → "Findings log"); latest output `RhombusAI_output_1791090159425.csv` (16:02:39). The pipeline now contains:
  - the re-applied `column_guard`;
  - the re-applied prompt changes for `None` names and 2-decimal formatting;
  - a USD-strip step.

  **This is not the baseline pipeline.** It must be restored before case 4.

## 5. Run identity

| Run | Started | Status | Output object | Local copy SHA-256 |
|---|---|---|---|---|
| `manual` | 15:57:20 (object time) | completed with a warning (exact status text not recorded) | `RhombusAI_output_1791089840449.csv` | `260801d0552dc4ca9a28f8c641e41984e1e5e7c3dac33a45f8703a25df0afb3c` (62 bytes) |
| `retest` | 16:02:39 (object time) | not recorded | `RhombusAI_output_1791090159425.csv` | `260801d0552dc4ca9a28f8c641e41984e1e5e7c3dac33a45f8703a25df0afb3c` (62 bytes) |

## 6. Logs

- **First run:** no error. Warning: "No results found after applying this LLM transformation". No separate log excerpt was captured.
- **Clear? No.**
  - The warning doesn't say that every row was rejected, which rule rejected them (non-numeric price), or that `price` changed type.
  - The input has 250 rows and the output 0, and nothing in the run explains the gap.

## 7. Chatbot

- **Prompt (first question):** "My last run finished but clean_transactions shows "No results found after applying this LLM transformation". Why did all rows disappear, and what should I change?"
- **Follow-up:** "price is now text like USD 222.97 … change nothing else".
- **Applied (after the follow-up):** directly, with **no confirmation shown**.
- **Cost:** 1 credit for the first reply (4943 → 4942).
- **First diagnosis: wrong** (`observations/evidence/schema-type-change-chatbot.txt`).
  - It didn't read the input file.
  - It ranked the likely causes as the `transaction_date` format first, `price` second and `total` precision third, and asked "Tell me what type changed".
  - It didn't apply a fix automatically this time (unlike cases 1 and 2).
- **Contradiction:** the chatbot stated that the Step 4 total check uses a **1e-9 tolerance**. The pipeline's own Custom node prompt (read in the app on 2026-10-04) says: "total present but not equal to round(price times qty, 2) ROUND_HALF_UP via decimal.Decimal". The AI builder's build reply said "total is present but does not equal price × qty rounded to 2 decimal places (round-half-up)". The build prompt requires an exact decimal comparison (STEP 4). This case didn't test which is true.
- **After being told the real cause, with "change nothing else":** it reported re-adding `column_guard` plus three prompt fixes:
  - `None`/`nan`/`NaT` → `np.nan`;
  - strip 3-letter currency codes;
  - format price and total with `.2f`.

  So it **re-applied the earlier fixes that had been reverted**: the `column_guard` from cases 1 and 2 (the case 1 version blanked valid `$` prices and kept rows with bad prices), and the `None` and 2-decimal changes. The currency strip was the only change related to this case.

  The instruction to change nothing else was ignored.
- **Config diff:** not captured. No Version Control snapshot was taken per fix; the fix is described from the chatbot's own reply (limitation, see README).
- **Retest:** 0 rows (section 3).
- **Fix grade: didn't work, harmful.** The output is still empty, and the pipeline now carries unrequested changes. One of them (the `column_guard`) silently corrupted data in case 1.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used manual runs. Schedule state after the case: Active, hourly, never fired (see `PLAN.md` → "Findings log").

## 9. Validation results

Reports (both against baseline run 4):
- `observations/evidence/validation-schema-type-change.json`
- `observations/evidence/validation-schema-type-change-retest.json`

Both reports give the same result. Overall: **fail**, from `semantic_anomaly` only.

| Check | Status | Note |
|---|---|---|
| `input_contract` | **pass** | all 9 columns present; the validator doesn't check column types |
| `schema`, `deduplication`, `values_match_policy`, `output_format` | pass | trivially, with 0 rows |
| `row_count_reconciliation` | **pass** | expected 0 = actual 0: 16 duplicates removed, 2 rejected for missing price, **232 rejected for non-numeric price** |
| 14 `rule_*` checks | not_applicable | no expected output rows |
| `manifest_consistency` | not_applicable | the default manifest describes the baseline |
| `determinism` | not_applicable | the input isn't the baseline dataset |
| `semantic_anomaly` | **fail** | 6 metrics, below |

| Metric | Baseline (run 4) | This case | Rule |
|---|---|---|---|
| `row_count` | 218 | **0** | relative change > 0.10 |
| `price.sum` | 54012.32 | **0** | ratio outside [0.5, 2.0] |
| `total.sum` | 309572.79 | **0** | ratio outside [0.5, 2.0] |
| `country.distribution` | 8 countries | **empty** | total variation distance > 0.25 |
| `status.distribution` | 4 statuses | **empty** | total variation distance > 0.25 |
| `transaction_date.month_histogram` | 6 months | **empty** | total variation distance > 0.25 |

**Validator gap:**
- Every policy check passes because, under the policy, an empty output *is* correct for this input. Only the semantic detector flags the data loss.
- The input contract checks column names, not types. So a column-wide type change looks like 232 ordinary row defects rather than a broken contract.
- A future improvement would add a type check that blocks downstream checks when most of a column fails to parse.

**If the USD strip had worked,** the retest would output rows that the approved policy says to reject, so `row_count_reconciliation` would fail. Whether that output is "right" depends on whether `USD <number>` is accepted as a price, and the approved policy doesn't accept it.

## 10. Three verdicts

Not a semantic case; this section doesn't apply.

## 11. Severity

**Proposed: High.** A column-wide type change produced **data loss** (0 of 218 rows) delivered to the destination with no error, only an uninformative warning. The chatbot's recovery attempt then **failed** and silently re-applied reverted fixes, including one that corrupted data in case 1. That covers the rubric's High ("data loss, or failed recovery path").

Not Critical:
- The empty file is visible and nothing existing was corrupted in this case.
- Recovery is possible: restore the snapshot and re-run.

**Kept at High.** The check that could raise it to Critical can't be done (see Limitations).

## 12. Reproduction steps

From a clean baseline:
1. In `rhombus-takehome-v2`, confirm the pipeline is the reverted baseline version, and that a manual ▶ run on `datasets/baseline.csv` matches baseline run 4 (SHA-256 `ebedc745…cdda`).
2. Save a Version Control snapshot.
3. Replace the input via Data Input → "From Device" with `datasets/schema_type_change.csv`. Don't click Apply on any node.
4. Trigger a manual ▶ run. Expected observation: no error, the warning "No results found after applying this LLM transformation", and a 62-byte header-only object in `output`.
5. Ask the chatbot for a diagnosis. Record what it reads, its first guess, and whether it applies anything.
6. Give it the real cause (`price` is now text such as `USD 222.97`) and say "change nothing else". Record every change it applies.
7. Trigger a manual ▶ run (`retest`). Record the object name and timestamp, then download it.
8. Validate both outputs:
   ```
   python data-validation/validate.py --scenario <id> --input datasets/schema_type_change.csv --output <file> --baseline-output outputs/manual-dryrun-4.csv --report <report.json>
   ```
9. Before restoring, run `datasets/baseline.csv` through the post-chatbot pipeline once and keep the output. This was **not done** in this test (see Limitations). Then restore the pre-case snapshot, trigger a manual ▶ run, and confirm it matches run 4.

## 13. Evidence

- `observations/evidence/validation-schema-type-change.json`
- `observations/evidence/validation-schema-type-change-retest.json`
- `datasets/schema_type_change.csv` and `.manifest.json`: the input.
- `observations/evidence/schema-type-change-chatbot.txt`: chatbot exchange, covering the first guess, the 1e-9 claim, the "change nothing else" instruction and the changes applied (sanitised summary).
- First run: the logged warning "No results found after applying this LLM transformation" (quoted in section 3) and its output object `RhombusAI_output_1791089840449.csv` (15:57:20, 62 bytes). Screenshot: **not captured**.
- Raw (gitignored): `evidence-raw/case3-chatbot.txt`; the AI builder build reply is in `evidence-raw/ai-builder-baseline-reply.txt`.
- Both outputs are in `outputs/` (gitignored). Each is the 62-byte header line reproduced in section 3.

## Limitations

- **Post-chatbot pipeline not tested on the baseline.** The pipeline was restored before case 4, before the baseline could be run through the post-chatbot version. So it's **not observed** whether the re-applied `column_guard` would corrupt baseline rows again, as it did in case 1 (blanked `$` prices, kept bad-price rows). Severity stays at High. If it had corrupted them, it would have been Critical: silent corruption affecting every future run.
- **Retest unanswerable.** The retest produced no rows, so it couldn't show whether the re-applied `None` and 2-decimal fixes work.
