# Phase 7 — Bonus: observability dashboard (optional)

**Start only when Phases 1–6 are done.** A finished README beats an unfinished dashboard.

## Checklist
- [ ] **[CLAUDE]** `scripts/build_dashboard.py`: reads validation JSON + run identity records → writes `docs/index.html` (single static page, data embedded, no backend).
- [ ] Panels (from the brief):
  - Pipeline health by scenario: success/failure for baseline, each drift type, combined.
  - Output consistency: 3 runs of the same input per configuration; match or vary; side-by-side diffs if variance.
  - Capability heat map: drift type × handled / warned / broke / missed.
  - Execution time: baseline vs each drift scenario.
- [ ] Every cell links to its observation file. Run types (scheduled/manual/retest) labelled.
- [ ] Built only from real run data — no placeholder or invented numbers.
- [ ] No credentials, bucket names, or private URLs on the page.
- [ ] **[YOU]** Enable GitHub Pages (from `docs/`); open the public link and check it renders.
- [ ] **[CLAUDE]** Add the link to README.

## Done when
Public link works and is in README.
