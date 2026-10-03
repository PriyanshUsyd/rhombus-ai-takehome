# Phase 2 — Baseline pipeline

Goal: one successful **scheduled** run of an AI-built cleaning pipeline (S3 → GCS), with output saved, run identity recorded and determinism measured.

## Checklist

### Dataset & policy (before touching Rhombus)
- [x] **[CLAUDE]** Write `scripts/generate_datasets.py` (fixed seed). Baseline ~200–300 synthetic rows, unless Phase 1 found limits that make a smaller file more reliable.
  - Columns: `id, name, email, country, price, qty, total, transaction_date, status`.
  - Known, documented count of each defect: exact duplicates, missing values, inconsistent formatting (casing, whitespace, mixed formats), invalid entries.
  - Edge case: emails differing only by case/whitespace.
  - Writes a `datasets/baseline.manifest.json` with every defect count and the SHA-256 of the file.
  - Dataset filenames use underscores, not hyphens (D1 quirk: Rhombus showed `connection-test.csv` as `connection_test`).
- [x] **[CLAUDE]** Write `datasets/cleaning-policy.md` **before the first run**:
  - Dedup key; whether email match ignores case and trims whitespace; which duplicate survives (first/last/normalised).
  - For each invalid value type: reject row / repair / keep with null.
  - Target output formats (date format, casing, numeric format).
- [x] **[BOTH]** Review the policy together; you approve it. (Approved 2026-10-03.)
- [ ] **[CLAUDE]** Turn the policy into plain-English AI builder prompts (`datasets/ai-builder-prompts.md`). Credits are limited (~6 per message): one consolidated prompt + at most one short correction follow-up.
- [x] **[CLAUDE]** Unit tests for the generator (`pytest -m "not live"`): defect counts match manifest; same seed → same bytes.

### Build in Rhombus
- [ ] **[YOU]** Upload `datasets/baseline.csv` to S3 at the key in `.env`.
- [ ] **[YOU]** Connect S3 as source in Rhombus.
- [ ] **[YOU]** Build the pipeline using the **AI builder only**, using the prompts. Copy every prompt and every builder reply into `evidence-raw/`. If it gets something wrong, re-prompt — never add manual steps.
- [ ] **[YOU]** Ask the builder to state what rules it applied; save the answer (it's a claim to verify, not ground truth).
- [ ] **[YOU]** Set GCS as destination. Note the output object key/pattern.
- [ ] **[YOU]** Schedule at the **shortest safe interval** (one run must finish before the next starts). Record interval chosen.
- [ ] **[YOU]** Export or screenshot the pipeline config (needed later for chatbot diffs).

### Baseline run
- [ ] **[YOU]** Wait for one successful **scheduled** run. Screenshot run status, logs, schedule.
- [ ] **[CLAUDE]** Write `scripts/fetch_output.py`: downloads the GCS object, saves as `outputs/<scenario>-<run#>.csv`, records the run identity record.
- [ ] **[YOU]** Run it immediately after the run completes.
- [ ] Run identity record captured (`observations/evidence/run-identity/<scenario>-<run#>.json`):
  scenario ID, input SHA-256, upload time, GCS object generation, last-modified, download time, platform run ID (if shown), run type (scheduled/manual/retest), run duration, overlap yes/no.

### Determinism
- [ ] **[YOU]** Produce 3 runs of the same baseline input (manual runs if the app offers them, else scheduled). Fetch each.
- [ ] **[CLAUDE]** Compute `raw_output_sha256` (exact bytes) and `canonical_data_sha256` (sorted by key, normalised whitespace/line endings, approved volatile fields removed). Document exactly what is canonicalised.
- [ ] **[CLAUDE]** Report: byte-level determinism / data-level determinism / expected metadata variation; diffs if any.

## Baseline acceptance (all must be evidenced)
1. Scheduled run executed. 2. Reached success state. 3. Output object present and readable. 4. Output parses. 5. Validator results recorded (Phase 5 validator). 6. Schedule still present after run. 7. Determinism measured and any variance documented.

## Done when
`outputs/baseline-1.csv` + run identity + determinism report exist; `PLAN.md` baseline row ticked.
