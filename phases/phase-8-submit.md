# Phase 8 — Final check & submit

## Final check
- [ ] **[YOU]** Fresh clone into a new folder → new venv → follow README exactly. Every command works.
- [ ] **[YOU]** `pytest -m "not live"` passes with no `.env` present.
- [ ] **[BOTH]** Secrets scan of full git history (e.g. `git log -p | grep -iE "secret|password|token|AKIA|private_key"`); nothing found. If found: rotate the key, then rewrite history.
- [ ] **[CLAUDE]** Deliverables check against the brief:
  - [ ] `/ui-tests/` — S3 connection, AI pipeline, GCS destination, schedule; CLI-runnable; no fixed sleeps; real assertions
  - [ ] `/api-tests/` — ≥2 tests, ≥1 negative, status + content asserted
  - [ ] `/data-validation/` — schema, row counts, cleaning rules, determinism, semantic cases; run on baseline + every drift
  - [ ] `/datasets/` — baseline + every drifted version
  - [ ] `/observations/` — one .md per drift case, evidence in `/observations/evidence/` and linked
  - [ ] README — setup/run, summary table + top 3, usability feedback, demo video link
  - [ ] (Bonus) dashboard link
- [ ] **[YOU]** Demo video link opens while logged out.
- [ ] **[YOU]** Pause or delete the Rhombus schedule; delete/disable cloud resources and keys per README cleanup.
- [ ] **[YOU]** Repo is public (or accessible to reviewers).

## Submit — [YOU]
- [ ] Start a **new email** (not a reply) to **careers@rhombusai.com**
- [ ] Subject exactly: **Rhombus AI – Take-Home Exercise**
- [ ] Body includes the GitHub repository link.
- [ ] Send within one week of receiving the exercise.

## Done when
Email sent.
