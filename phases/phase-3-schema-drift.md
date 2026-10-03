# Phase 3 — Schema drift (5 cases)

Goal: for each case, answer the brief's four questions with evidence:
1. Does Rhombus stop, warn, or carry on? If it carries on, what reaches GCS?
2. Do the logs explain the problem clearly?
3. Does the chatbot diagnose the error correctly, and does its fix actually work?
4. What happens to the schedule afterwards?

All 5 cases run on the **schedule** (brief: "before the next scheduled run, change the source file"). Chatbot-fix retests may be manual runs if available — label them `retest`.

## Datasets
- [ ] **[CLAUDE]** Extend `scripts/generate_datasets.py` to derive each file from the baseline (only the intended change differs); record SHA-256 in each manifest.

| Scenario ID | Change |
|---|---|
| `schema-drop-column` | Remove one existing column |
| `schema-rename-column` | Rename one existing column, values unchanged |
| `schema-type-change` | Same name, different type (e.g. `price` numeric → text) |
| `schema-add-column` | Add one new column |
| `schema-combined` | All four at once, aggressive: drop the dedup key, rename a column a cleaning rule depends on, change `price` type, add a column |

- [ ] **[CLAUDE]** Unit test: each drifted file differs from baseline only by its intended change.

## Protocol — repeat for each case
- [ ] 1. **[YOU]** Pre-state: source key + checksum, pipeline config (export/screenshot), schedule status, destination objects with generation + checksum, last successful run, scenario ID. (**[CLAUDE]** provides `scripts/capture_state.py` for the cloud parts.)
- [ ] 2. **[YOU]** Upload the drifted file to S3; note time.
- [ ] 3. **[YOU]** Wait for the next scheduled run.
- [ ] 4. **[YOU]** Record outcome: stopped / warned / carried on.
- [ ] 5. **[YOU]** Run `fetch_output.py`; compare run identity with pre-state (rule out stale output).
- [ ] 6. **[YOU]** Copy log **text** (not just screenshots) + screenshots into `evidence-raw/`.
- [ ] 7. **[YOU]** Chatbot:
  - save original config;
  - give it the exact error/log excerpt; ask for diagnosis and smallest fix;
  - record diagnosis + proposed change verbatim;
  - apply the change; save new config;
  - **[CLAUDE]** diffs old vs new config; confirms only the relevant part changed;
  - retest; grade fix: worked / partial / didn't / not testable.
- [ ] 8. **[YOU]** Post-state: same fields as pre-state, incl. schedule state.
- [ ] 9. **[YOU/CLAUDE]** Run validator; save JSON report to `observations/evidence/`.
- [ ] 10. **[YOU]** Restore baseline file (and baseline pipeline config if the chatbot fix changed it). Confirm the next run is clean before the next case.
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
