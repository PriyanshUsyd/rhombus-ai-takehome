# Phase 6 — Documentation

Goal: observations and README that a reviewer can reproduce from.

## Observation files — [CLAUDE] drafts from evidence, [YOU] reviews
- [ ] One file per case: `observations/schema-drop-column.md`, `schema-rename-column.md`, `schema-type-change.md`, `schema-add-column.md`, `schema-combined.md`, `semantic-dollars-to-cents.md`, `semantic-date-swap.md` (+ `baseline.md`).
- [ ] Template (every file):
  1. Change (exact, dataset SHA-256, timestamp)
  2. Expected behaviour
  3. Actual behaviour (stopped / warned / carried on; what reached GCS)
  4. Pre-state / post-state
  5. Run identity
  6. Logs (verbatim, sanitised excerpt) — clear or not?
  7. Chatbot: prompt, diagnosis, proposed change, config diff, retest, fix grade
  8. Schedule afterwards
  9. Validation results with check statuses
  10. Semantic cases: three verdicts (platform / validator / data risk)
  11. Severity + one-line justification
  12. Reproduction steps (numbered, from clean baseline)
  13. Evidence links (`observations/evidence/...`)
- [ ] Deviation D1 (see `PLAN.md`): `observations/setup-s3-connection-blocked.md` — what was tried, exact error, chatbot reply, evidence. (Setup issue, not a drift case; the 13-point template above does not apply.)
- [ ] Unknown items written as "not observed" — never guessed.

## Evidence sanitisation — [YOU] with [CLAUDE] checklist
- [ ] Remove/blur emails, bucket names, tokens, internal URLs, account IDs from screenshots and logs.
- [ ] Only sanitised copies go into `observations/evidence/`; raw stays in gitignored `evidence-raw/`.

## Severity rubric (copy into README)
- **Critical:** confirmed material corruption or data exposure that is silent or inadequately contained and lacks a reliable recovery path.
- **High:** silent incorrect output, schedule failure, data loss, or failed recovery path.
- **Medium:** stops or warns, but diagnostics incomplete/misleading or recovery hard.
- **Low:** minor issue with safe recovery.
- **Info:** handled well, or non-blocking improvement.
- Principle: silent semantic corruption ranks above a visible failure.

## README.md — [CLAUDE] drafts, [YOU] writes feedback + records video
- [ ] 1. **Setup and how to run** each suite: venv, install, `playwright install chromium`, `.env` from `.env.example`, `pytest -m "not live"`, `pytest ui-tests -m live`, `pytest api-tests -m live`, validator CLI. Note on bounded polling vs fixed sleeps. Cloud cleanup steps.
- [ ] 2. **Observations summary**: table, one row per drift case — change | pipeline stopped? | chatbot fix worked? | severity | link. Then top three findings in a few lines (highest-severity, evidence-based).
- [ ] 3. **Usability feedback** — **[YOU]** write 1–2 paragraphs: most helpful/enjoyable, frustrating/difficult, how to make it more useful and efficient. Only real experiences.
- [ ] 4. **Demo video link** — **[YOU]** record a short walkthrough of UI tests, API tests, data validation (no secrets on screen); upload unlisted; paste link. **[CLAUDE]** can write a script for the video.
- [ ] 5. **Limitations**: include verbatim — "Required scheduled scenarios: 1 baseline + 7 drift scenarios = 8 scheduled runs. Additional determinism and chatbot-fix runs are labelled separately as manual or retest runs." Plus runs per case and platform features that couldn't be verified.
- [ ] 6. **Deviations** — note explaining why the route is Azure Blob `source` → Azure Blob `output` instead of S3 → GCS: S3 connection blocked; GCS not used because GCP billing needs a card (Deviation D1 in `PLAN.md`). Link `observations/setup-s3-connection-blocked.md`.

## Done when
7 drift observation files + baseline + `setup-s3-connection-blocked.md` exist, all link to sanitised evidence; README has all 4 required sections + limitations + deviations.
