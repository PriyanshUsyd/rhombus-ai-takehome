# PLAN.md — Phase tracker

Owner tags: **[YOU]** = human does it live · **[CLAUDE]** = Claude produces it · **[BOTH]** = Claude prepares, human runs/confirms.
Status: ⬜ not started · 🟨 in progress · ✅ done · ⛔ blocked (write reason)

| # | Phase | File | Status | Notes |
|---|-------|------|--------|-------|
| 1 | Setup & discovery | `phases/phase-1-setup.md` | ⬜ | |
| 2 | Baseline pipeline | `phases/phase-2-baseline.md` | ⬜ | |
| 3 | Schema drift (5 cases) | `phases/phase-3-schema-drift.md` | ⬜ | |
| 4 | Semantic drift (2 cases) | `phases/phase-4-semantic-drift.md` | ⬜ | |
| 5 | Code: validation, UI, API | `phases/phase-5-code.md` | ⬜ | |
| 6 | Documentation | `phases/phase-6-documentation.md` | ⬜ | |
| 7 | Bonus dashboard (optional) | `phases/phase-7-dashboard.md` | ⬜ | Only after 1–6 |
| 8 | Submit | `phases/phase-8-submit.md` | ⬜ | |

Note: Phase 5 code (generator, validator) is started early — the dataset generator in Phase 2 and the validator before Phase 3 runs. UI/API tests are written once Phase 1 discovery evidence exists.

## Scenario run tracker

| Scenario ID | Dataset | Run type | Run done | Output downloaded | Validator run | Observation file | Severity |
|---|---|---|---|---|---|---|---|
| baseline | `datasets/baseline.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/baseline.md` | |
| determinism-1..3 | `datasets/baseline.csv` | manual/scheduled | ⬜ | ⬜ | ⬜ | (in baseline.md) | |
| schema-drop-column | `datasets/schema-drop-column.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-drop-column.md` | |
| schema-rename-column | `datasets/schema-rename-column.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-rename-column.md` | |
| schema-type-change | `datasets/schema-type-change.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-type-change.md` | |
| schema-add-column | `datasets/schema-add-column.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-add-column.md` | |
| schema-combined | `datasets/schema-combined.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/schema-combined.md` | |
| semantic-dollars-to-cents | `datasets/semantic-dollars-to-cents.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/semantic-dollars-to-cents.md` | |
| semantic-date-swap | `datasets/semantic-date-swap.csv` | scheduled | ⬜ | ⬜ | ⬜ | `observations/semantic-date-swap.md` | |

## Open questions (verify in app — fill in during Phase 1)
| Question | Answer | Evidence |
|---|---|---|
| Credentials Rhombus needs for S3 | | |
| Credentials Rhombus needs for GCS | | |
| Schedule intervals offered | | |
| Manual "run now" exists? | | |
| Output object key templatable? | | |
| Upload / row limits | | |
| Pipeline config exportable? | | |
| Where run logs are shown | | |
| Where the chatbot is accessed | | |
| Login method (email/password, SSO, MFA?) | | |
