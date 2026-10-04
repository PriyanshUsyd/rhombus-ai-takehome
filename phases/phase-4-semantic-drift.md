# Phase 4 — Semantic drift (2 cases)

Goal: structure stays identical, meaning changes. Answer: does Rhombus notice? Does our validation catch it?

Both cases run as a **manual ▶ run (labelled `manual`)** per D2. The scheduler never fired for workflow 5257 (see `PLAN.md` → "Findings log").

## Datasets
- [x] **[CLAUDE]** Add to `scripts/generate_datasets.py`:

| Scenario ID | Change | Why it's purely semantic |
|---|---|---|
| `semantic-dollars-to-cents` | Multiply both `price` and `total` by 100 | `total = price × qty` still holds; only the unit changes |
| `semantic-date-swap` | Only ambiguous, valid dates (day ≤ 12), day and month swapped | Every date still parses; the meaning changes |

- [x] **[CLAUDE]** `semantic-date-swap` construction: swap day and month **inside the canonical ISO `transaction_date` values** (`YYYY-MM-DD` → `YYYY-DD-MM`), only on rows whose day ≤ 12, so every result is still a valid ISO date. Never use slash formats: the baseline policy rejects ambiguous slash dates, which would turn this semantic case into a rejection case. Rows with day > 12 and the non-ISO formatted dates stay unchanged.
- [x] **[CLAUDE]** Unit test: schema identical to baseline; cross-field rule still holds (cents case); every date valid (date case).
- [ ] Optional, separate cases only if time allows: `robustness-invalid-dates`, `crossfield-broken-total`. Never mixed into the two required cases.

## Protocol
Same as Phase 3 (pre-state → From Device upload → manual ▶ run (labelled `manual`) → outcome → fetch → logs → chatbot if there's an error/warning → post-state → validator → restore → observation draft).

## Verdicts — three independent results per case
| Detector | Result |
|---|---|
| Platform behaviour | caught / missed / unclear |
| Validator behaviour | caught / missed / blocked / not applicable |
| Final data risk | Critical / High / Medium / Low / Info |

## Case tracker
| Case | Run | Platform | Validator | Data risk | Restored | Observation |
|---|---|---|---|---|---|---|
| dollars-to-cents | ⬜ | | | | ⬜ | ⬜ |
| date-swap | ⬜ | | | | ⬜ | ⬜ |

## Done when
Both cases have run evidence, three verdicts each, and an observation draft.
