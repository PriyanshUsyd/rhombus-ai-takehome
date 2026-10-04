# Schema drift: combined, aggressive (`schema-combined`)

| | |
|---|---|
| **Run type** | `manual` ▶ run (D2: the scheduler never fired), then one `retest` after the chatbot fix |
| **Project / workflow** | `rhombus-takehome-v2` / 5257 |
| **Date** | 2026-10-04 |
| **Severity (proposed)** | **Medium**: see section 11 |

**Summary.** Four schema changes were made at once: the dedup key `id` dropped, `transaction_date` renamed to `order_date`, `price` changed to text, and `channel` added. The run **failed closed** with no output. But the error named only 2 of the 4 changes (`['id', 'transaction_date'] not in index`).

The chatbot **made up a root cause**: an upper-case `ID` and `Transaction_Date`, neither of which exists in the file. It then applied a header-lowercasing change to the prompt. The retest failed with the **identical error**. No bad data reached the destination, but neither the diagnostics nor the recovery path worked.

## 1. Change

- **Dataset:** `datasets/schema_combined.csv`, SHA-256 `6b890fa0b0a3d202e17270083929e5064f5808ab7458c1b520c12ca504229942` (manifest `datasets/schema_combined.manifest.json`).
- **Derived from:** `datasets/baseline.csv` (SHA-256 `f2c301dc…c2a2`).
- **Exact change, all four at once:**
  1. `id` (the dedup key) removed;
  2. `transaction_date` renamed to `order_date`, values unchanged;
  3. `price` changed to text: 230 numeric prices written as `USD <number>`;
  4. `channel` added as the last column (`web` / `store` / `app`).

  Every other cell is identical to the baseline (250 rows, 9 columns).
- **Input header:** `name,email,country,price,qty,total,order_date,status,channel`
- **Uploaded via:** Data Input → "From Device".
- **Upload time:** TODO.

## 2. Expected behaviour

Our expectation, not a Rhombus claim. With the dedup key gone, deduplication can't be done safely, so the only safe outcome is to **stop**. A good pipeline would stop with one message that names all the contract breaks:
- `id` missing;
- `transaction_date` missing, with `order_date` as the likely match;
- `price` no longer numeric;
- an unexpected column, `channel`.

It should not write output, and it should not rewrite the pipeline from a guessed cause.

## 3. Actual behaviour

| Run | Outcome | What reached Azure `output` |
|---|---|---|
| First `manual` run | **Stopped** at step `clean_transactions`: `['id', 'transaction_date'] not in index`. Same `code_sha` (`5e6c1f84d511`) as the first runs of cases 1 and 2. | Nothing (no output written). |
| `retest` after the chatbot fix | **Stopped** with the **identical error**. | Nothing (no output written). |

- **Failed closed:** no output reached Azure, so no corrupted or partial data reached the destination. That is the right outcome for a missing dedup key.
- **Only 2 of 4 changes reported.** The missing `id` and `transaction_date` are named. The `price` type change and the added `channel` column are not mentioned.
- **Inferred, not confirmed:** the run probably stops at the first missing-column lookup, before any check that could see the other two changes.

## 4. Pre-state / post-state

- **Pre-state:**
  - The pipeline was the baseline version, consistent with the same `code_sha` as earlier first runs (TODO: confirm with a Version Control snapshot).
  - The AI Builder chat history was cleared before case 4 (method change), so the chatbot started this case without the earlier fixes in its history.
  - TODO: schedule status, latest objects in `output`, last successful run.
- **Post-state:** TODO, same fields. The pipeline prompt now includes the chatbot's header-lowercasing change, so it **is not the baseline pipeline**. It must be restored before case 6.

## 5. Run identity

| Run | Started | Status | Output object |
|---|---|---|---|
| `manual` | TODO | failed (`['id', 'transaction_date'] not in index`) | none |
| `retest` | TODO | failed (identical error) | none |

## 6. Logs

- **First run:** `['id', 'transaction_date'] not in index` at `clean_transactions`, `code_sha` `5e6c1f84d511`. TODO: paste a short sanitised verbatim excerpt from `evidence-raw/case5-log.txt` (the file isn't in `evidence-raw/` yet).
- **Retest:** the identical error. TODO: excerpt from `evidence-raw/case5-retest-log.txt` (the file isn't in `evidence-raw/` yet).
- **Clear? Partly, and incomplete.**
  - It names 2 missing columns, but as a raw Python/pandas `KeyError`.
  - It doesn't mention the `price` type change or the added `channel` column.
  - It doesn't say that the input schema changed, or that `order_date` is the likely replacement.
  - A user fixing only what the error names would hit the next break on the following run.

## 7. Chatbot

- **Prompt:** TODO, verbatim, from `evidence-raw/case5-chatbot.txt` (the file isn't in `evidence-raw/` yet).
- **Diagnosis: made up.** The chatbot said the input had `ID` instead of `id`, and `Transaction_Date` instead of `transaction_date`.
  - **Neither exists in the file.** The real header is `name,email,country,price,qty,total,order_date,status,channel`: `id` is **absent**, and the date column is `order_date`.
  - The claim sounds plausible but isn't based on the actual input. As in cases 2 and 3, the chatbot didn't read the file.
- **Proposed change:** lowercase all headers, added to the pipeline prompt.
- **Applied:** **automatically**. TODO: confirm whether a confirmation step was shown.
- **Cost:** TODO (credits).
- **Config diff:** TODO. Use Version Control snapshots before and after; the diff should show the header-lowercasing instruction.
- **Retest:** identical error.
- **Fix grade: didn't work.** Lowercasing headers can't help: `id` doesn't exist and `order_date` doesn't lowercase to `transaction_date`.
- **Effect on the baseline:** not observed. The change may be harmless there, since the baseline headers are already lowercase, but it still changed the pipeline.

## 8. Schedule afterwards

Not testable. Per D2, the scheduler never fired for workflow 5257, so this case used manual runs. Schedule state after the case: TODO.

## 9. Validation results

**Not run:** neither run produced output, so there is nothing to validate.

For reference, the validator's input checks on this file would report `input_contract` = fail (required columns `id` and `transaction_date` missing). Every downstream check would be `blocked_by_schema`, because without `id` no deduplication or row matching can be derived. The validator would also not name the `price` type change, because its contract checks column names, not types (see `schema-type-change.md` §9).

## 10. Three verdicts

Not a semantic case; this section doesn't apply.

## 11. Severity

**Proposed: Medium.** The platform **stopped and wrote nothing**, the correct outcome when the dedup key is missing. But the **diagnostics are incomplete** (2 of 4 changes surfaced), and the chatbot's **diagnosis was made up** and its fix didn't work, so recovery is hard. That matches the rubric's Medium ("stops or warns, but diagnostics incomplete/misleading or recovery hard").

Not High:
- No incorrect or partial data reached the destination.
- The failed fix left the pipeline still failing closed, rather than producing silent bad output as in cases 1–3.

The made-up diagnosis is the most serious part of this case. Report it as a chatbot-quality finding alongside cases 2 and 3: in all three, the chatbot didn't read the input file.

## 12. Reproduction steps

From a clean baseline:
1. In `rhombus-takehome-v2`, confirm the pipeline is the baseline version, and that a manual ▶ run on `datasets/baseline.csv` matches baseline run 4 (SHA-256 `ebedc745…cdda`).
2. Save a Version Control snapshot, and clear the AI Builder chat history.
3. Replace the input via Data Input → "From Device" with `datasets/schema_combined.csv`. Check that the preview header is `name,email,country,price,qty,total,order_date,status,channel`. Don't click Apply on any node.
4. Trigger a manual ▶ run. Expected observation: it fails at `clean_transactions` with `['id', 'transaction_date'] not in index`, and no new object appears in `output`.
5. Ask the chatbot for a diagnosis. Compare every column name it cites with the real header from step 3. Record any change it applies.
6. Trigger a manual ▶ run (`retest`). Expected observation: the identical error, and no new object.
7. Restore: upload `datasets/baseline.csv`, restore the snapshot from step 2 (removing the header-lowercasing change), then trigger a manual ▶ run and confirm it matches run 4.

## 13. Evidence

- `datasets/schema_combined.csv` and `.manifest.json`: the input.
- Raw, gitignored (**not yet in `evidence-raw/`**): `case5-log.txt`, `case5-chatbot.txt`, `case5-retest-log.txt`.
- TODO (sanitised copies in `observations/evidence/`):
  - the first-run error excerpt
  - the chatbot's made-up diagnosis (verbatim) next to the real input header
  - the applied prompt change
  - the retest error excerpt
- No validator report: there was no output.

## Limitations

- **Restore check not run.** Whether the header-lowercasing change affects the baseline pipeline wasn't observed. It applies only if the baseline wasn't run through the post-chatbot pipeline before it was restored.
- **AI Builder history cleared.** As for case 4, the history was cleared before the case, so the made-up diagnosis didn't come from earlier conversation context.
