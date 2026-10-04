# Phase 3 — Schema drift (5 cases)

Goal: for each case, answer the brief's four questions with evidence:
1. Does Rhombus stop, warn, or carry on? If it carries on, what reaches GCS?
2. Do the logs explain the problem clearly?
3. Does the chatbot diagnose the error correctly, and does its fix actually work?
4. What happens to the schedule afterwards? (Per D2 the scheduler never fired for workflow 5257. Record the schedule state before and after each case; if it fires, record that run separately as `scheduled`. Otherwise answer "not testable — scheduler never fired".)

All 5 cases run as a **manual ▶ run (labelled `manual`)** per D2. The scheduler never fired for workflow 5257 (see `PLAN.md` → "Findings log"). The brief asks to change the source file "before the next scheduled run"; this is a documented deviation. Chatbot-fix retests are also manual runs; label them `retest`.

## Datasets
- [x] **[CLAUDE]** Extend `scripts/generate_datasets.py` to derive each file from the baseline (only the intended change differs); record SHA-256 in each manifest.

| Scenario ID | Change |
|---|---|
| `schema-drop-column` | Remove one existing column |
| `schema-rename-column` | Rename one existing column, values unchanged |
| `schema-type-change` | Same name, different type (e.g. `price` numeric → text) |
| `schema-add-column` | Add one new column |
| `schema-combined` | All four at once, aggressive: drop the dedup key, rename a column a cleaning rule depends on, change `price` type, add a column |

- [x] **[CLAUDE]** Unit test: each drifted file differs from baseline only by its intended change.

## Protocol — repeat for each case
> **Do NOT edit or Apply any node between a file swap and the manual ▶ run.** Clicking Apply (observed on the Data Output node) triggers an extra pipeline run, which would be an unlabelled run mixed in with the one being tested.
>
> Input is a From Device upload (D1); the Azure `source` container and its sync are no longer used.

- [ ] 1. **[YOU]** Pre-state: uploaded file name + SHA-256 (from its manifest), pipeline config (export/screenshot), schedule status, destination objects with generation + checksum, last successful run, scenario ID. (**[CLAUDE]** provides `scripts/capture_state.py` for the cloud parts.)
- [ ] 2. **[YOU]** Upload the drifted file via Data Input → "From Device" (replacing the baseline input); note time. Do not touch Apply.
- [ ] 3. **[YOU]** Trigger a manual ▶ run (labelled `manual`); note time.
- [ ] 4. **[YOU]** Record outcome: stopped / warned / carried on.
- [ ] 5. **[YOU]** Run `fetch_output.py`; compare run identity with pre-state (rule out stale output).
- [ ] 6. **[YOU]** Copy log **text** (not just screenshots) + screenshots into `evidence-raw/`.
- [ ] 7. **[YOU]** Chatbot:
  - save original config (wrench → Version Control snapshot + screenshot; no config export seen);
  - give it the exact error/log excerpt; ask for diagnosis and smallest fix;
  - record diagnosis + proposed change verbatim;
  - apply the change; save new config;
  - **[CLAUDE]** diffs old vs new config; confirms only the relevant part changed;
  - retest; grade fix: worked / partial / didn't / not testable.
- [ ] 8. **[YOU]** Post-state: same fields as pre-state, incl. schedule state.
- [ ] 9. **[YOU/CLAUDE]** Run validator; save JSON report to `observations/evidence/`.
- [ ] 10. **[YOU]** Restore baseline file (and baseline pipeline config if the chatbot fix changed it). Trigger a manual ▶ run (labelled `manual`) and confirm it matches the baseline (run 4) before the next case.
- [ ] 11. **[CLAUDE]** Draft `observations/<scenario-id>.md` from the evidence (Phase 6 template).

## Case tracker
| Case | Pre-state | Run | Outcome | Logs | Chatbot | Fix graded | Post-state | Validator | Restored | Observation |
|---|---|---|---|---|---|---|---|---|---|---|
| drop | ⬜ | ⬜ | | ⬜ | ⬜ | | ⬜ | ⬜ | ⬜ | ⬜ |
| rename | ⬜ | ⬜ | | ⬜ | ⬜ | | ⬜ | ⬜ | ⬜ | ⬜ |
| type-change | ⬜ | ⬜ | | ⬜ | ⬜ | | ⬜ | ⬜ | ⬜ | ⬜ |
| add | ⬜ | ⬜ | | ⬜ | ⬜ | | ⬜ | ⬜ | ⬜ | ⬜ |
| combined | ⬜ | ⬜ | | ⬜ | ⬜ | | ⬜ | ⬜ | ⬜ | ⬜ |

## Done when
All 5 rows complete with evidence and an observation draft each.
