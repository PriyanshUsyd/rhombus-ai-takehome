"""Build docs/data.json for the observability dashboard (docs/index.html).

Only tracked repo files are read: observations/*.md, observations/evidence/validation-*.json,
PLAN.md and datasets/*.manifest.json. outputs/ is gitignored, so it is never read; output
hashes come from the validator reports or from hashes already written in the observations.

The run list below is hand-written from the observations, but nothing in it is trusted
blindly. For every run the build checks that its output blob timestamp, its logged times and
each quoted phrase appear verbatim in the cited source file, and it fails otherwise. Validator
results, row counts and hashes are read from the reports, never typed in. A value that isn't
recorded anywhere is written as "not recorded".

All times are 2026-10-04 AEDT (UTC+11), as in the observations.

Usage:
    python scripts/build_dashboard.py [--out docs/data.json]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GITHUB_BLOB = "https://github.com/PriyanshUsyd/rhombus-ai-takehome/blob/main/"
DATE = "2026-10-04"
TZ = "+11:00"
NOT_RECORDED = "not recorded"
REPORTS = "observations/evidence/validation-{}.json"
KNOWN_BASELINE_FAILURES = ["rule_name_missing_kept_null", "values_match_policy", "output_format"]

RUN_TYPES = ("manual", "retest", "ui-test")
OUTCOMES = ("stopped", "warned", "carried_on", "contradictory", NOT_RECORDED)
HEALTH = ("success", "failed", "success_wrong_or_empty")
CELL_CLASSES = ("handled", "warned", "broke", "silent", "missed", "caught", "n/a")

# Scenario order is the chart order. `cells` feed the capability heat map; each quote must
# appear in the scenario's observation file. Severity is parsed from that file's header.
SCENARIOS = [
    {"id": "baseline", "label": "Baseline", "category": "baseline",
     "observation": "observations/baseline.md", "cells": None},
    {"id": "schema-drop-column", "label": "Drop column", "category": "schema",
     "observation": "observations/schema-drop-column.md", "cells": {
         "behaviour": ("broke", "Stopped: raw Python KeyError, no output",
                       "the first run **failed closed**"),
         "chatbot": ("silent", ("Auto-applied guard → silent wrong output "
                                "(country empty, 3 prices wiped, 4 bad rows kept)"),
                     "**didn't work, harmful.**"),
         "validator": ("caught", "Caught empty country; missed 4 extra rows and 3 wiped prices",
                       "The semantic detector caught the empty `country`"),
     }},
    {"id": "schema-rename-column", "label": "Rename column", "category": "schema",
     "observation": "observations/schema-rename-column.md", "cells": {
         "behaviour": ("broke", "Stopped: raw Python KeyError, no output",
                       "the first run **failed closed**"),
         "chatbot": ("broke", ("Guessed alias map → header-only file under "
                               "\"Pipeline completed successfully\""),
                     "**didn't work, harmful.**"),
         "validator": ("caught", "Caught: row_count 218 → 0",
                       "The validator catches this clearly"),
     }},
    {"id": "schema-type-change", "label": "Type change", "category": "schema",
     "observation": "observations/schema-type-change.md", "cells": {
         "behaviour": ("warned", "Carried on: header-only file, warning only",
                       "The only signal was the warning"),
         "chatbot": ("broke", "Still 0 rows; re-applied reverted fixes",
                     "**Fix grade: didn't work, harmful.**"),
         "validator": ("caught", "Caught by semantic check only (row_count 218 → 0)",
                       "Only the semantic detector flags the data loss."),
     }},
    {"id": "schema-add-column", "label": "Add column", "category": "schema",
     "observation": "observations/schema-add-column.md", "cells": {
         "behaviour": ("handled", "Handled: extra column dropped, output identical to baseline",
                       "The pipeline handled an additive schema change correctly."),
         "chatbot": ("n/a", "Not used (no error)", "Not used: the run had no error or warning."),
         "validator": ("handled", "No anomaly; only known baseline defects",
                       "fail, from the known baseline defects only."),
     }},
    {"id": "schema-combined", "label": "Combined", "category": "schema",
     "observation": "observations/schema-combined.md", "cells": {
         "behaviour": ("broke", "Stopped: error names 2 of 4 changes",
                       "the error named only 2 of the 4 changes"),
         "chatbot": ("broke", "Made-up diagnosis; identical error after fix",
                     "**Fix grade: didn't work.**"),
         "validator": ("n/a", "Not run: no output", "**Not run:** neither run produced output"),
     }},
    {"id": "semantic-dollars-to-cents", "label": "Dollars → cents", "category": "semantic",
     "observation": "observations/semantic-dollars-to-cents.md", "cells": {
         "behaviour": ("missed", "Missed: \"completed successfully\", every money value ×100",
                       "Platform: **missed**"),
         "chatbot": ("n/a", "Not used (no error)", "Not used: the run had no error or warning."),
         "validator": ("caught", "Caught: 4 money metrics, each ×100", "Validator: **caught**"),
     }},
    {"id": "semantic-date-swap", "label": "Date swap", "category": "semantic",
     "observation": "observations/semantic-date-swap.md", "cells": {
         "behaviour": ("missed", "Missed: \"completed successfully\", 81 of 218 dates wrong",
                       "Platform: **missed**"),
         "chatbot": ("n/a", "Not used (no error)", "Not used: the run had no error or warning."),
         "validator": ("caught", "Caught weakly: date range only; 40 of 81 wrong dates invisible",
                       "Validator: **caught, weakly**"),
     }},
    {"id": "ui-test-session", "label": "UI test session", "category": "ui-test",
     "observation": "PLAN.md", "cells": None},
]

# One entry per run. `source` is the file every literal below is checked against.
# report: validator report id; same_bytes_as: run id whose hashes this output shares
# (only where the source states the outputs are byte-identical).
RUNS = [
    # Baseline: object times only; start/finish not recorded (baseline.md §5).
    {"id": "baseline-run-1", "scenario": "baseline", "label": "Run 1", "run_type": "manual",
     "source": "observations/baseline.md", "output_time": "14:10:30",
     "blob": "RhombusAI_output_1791083430615.csv", "report": "manual-dryrun-1",
     "outcome": "carried_on", "health": "success",
     "note": "Known baseline defects only (3 `None` names, 70 money cells missing a trailing "
             "zero).", "quotes": ["byte-identical to run 1"]},
    {"id": "baseline-run-2", "scenario": "baseline", "label": "Run 2", "run_type": "manual",
     "source": "observations/baseline.md", "output_time": "15:00:20",
     "blob": "RhombusAI_output_1791086420064.csv", "report": "manual-dryrun-2",
     "outcome": "carried_on", "health": "success", "note": "Byte-identical to run 1."},
    {"id": "baseline-run-3", "scenario": "baseline", "label": "Run 3", "run_type": "manual",
     "source": "observations/baseline.md", "output_time": "15:04:43",
     "blob": "RhombusAI_output_1791086683413.csv", "report": "manual-dryrun-3",
     "outcome": "carried_on", "health": "success_wrong_or_empty",
     "note": "Modified pipeline (how is not recorded): every id and qty written as a decimal. "
             "Reverted before run 4.", "quotes": ["**every `id` and `qty` was written as a decimal**"]},
    {"id": "baseline-run-4", "scenario": "baseline", "label": "Run 4 (reference)",
     "run_type": "manual", "source": "observations/baseline.md", "output_time": "15:11:16",
     "blob": "RhombusAI_output_1791087076533.csv", "report": "manual-dryrun-4",
     "outcome": "carried_on", "health": "success",
     "note": "The baseline every drift case is compared with.",
     "quotes": ["byte-identical to runs 1 and 2: the baseline"]},

    {"id": "drop-column-manual", "scenario": "schema-drop-column", "label": "First run",
     "run_type": "manual", "source": "observations/schema-drop-column.md",
     "trigger_time": "15:46:21", "completion_time": "15:46:26",
     "outcome": "stopped", "health": "failed",
     "note": "Failed at clean_transactions: ['country'] not in index. No output.",
     "quotes": ["15:46:21–15:46:26 (log)"]},
    {"id": "drop-column-retest", "scenario": "schema-drop-column", "label": "Retest",
     "run_type": "retest", "source": "observations/schema-drop-column.md",
     "output_time": "15:49:21", "blob": "RhombusAI_output_1791089361234.csv",
     "report": "schema-drop-column-retest", "outcome": "carried_on",
     "health": "success_wrong_or_empty", "chatbot_fix": "didn't work, harmful",
     "note": "country empty on all 222 rows; 4 rows kept that should be rejected; "
             "3 valid prices wiped.", "quotes": ["**didn't work, harmful.**"]},

    {"id": "rename-column-manual", "scenario": "schema-rename-column", "label": "First run",
     "run_type": "manual", "source": "observations/schema-rename-column.md",
     "trigger_time": "15:53:35", "completion_time": "15:53:39",
     "outcome": "stopped", "health": "failed",
     "note": "Failed at clean_transactions: ['transaction_date'] not in index. No output.",
     "quotes": ["15:53:35–15:53:39 (log)"]},
    {"id": "rename-column-retest", "scenario": "schema-rename-column", "label": "Retest",
     "run_type": "retest", "source": "observations/schema-rename-column.md",
     "trigger_time": "15:54:52", "completion_time": "15:55:07", "output_time": "15:55:09",
     "blob": "RhombusAI_output_1791089709537.csv", "report": "schema-rename-column-retest",
     "outcome": "warned", "health": "success_wrong_or_empty",
     "chatbot_fix": "didn't work, harmful",
     "note": "Warning \"No results found…\" next to \"Pipeline completed successfully\"; "
             "header-only file (0 of 218 rows).",
     "quotes": ["15:54:52–15:55:07 (log)", "**didn't work, harmful.**"]},

    {"id": "type-change-manual", "scenario": "schema-type-change", "label": "First run",
     "run_type": "manual", "source": "observations/schema-type-change.md",
     "output_time": "15:57:20", "blob": "RhombusAI_output_1791089840449.csv",
     "report": "schema-type-change", "outcome": "warned", "health": "success_wrong_or_empty",
     "note": "No error; warning \"No results found…\"; header-only file (0 of 218 rows).",
     "quotes": ["**Carried on, no error.** Warning"]},
    {"id": "type-change-retest", "scenario": "schema-type-change", "label": "Retest",
     "run_type": "retest", "source": "observations/schema-type-change.md",
     "output_time": "16:02:39", "blob": "RhombusAI_output_1791090159425.csv",
     "report": "schema-type-change-retest", "outcome": NOT_RECORDED,
     "health": "success_wrong_or_empty", "chatbot_fix": "didn't work, harmful",
     "note": "Still header-only (0 rows), byte-identical to the first run.",
     "quotes": ["Run status and warnings: not recorded.", "**Fix grade: didn't work, harmful.**"]},

    {"id": "add-column-manual", "scenario": "schema-add-column", "label": "Run",
     "run_type": "manual", "source": "observations/schema-add-column.md",
     "output_time": "16:04:44", "blob": "RhombusAI_output_1791090284446.csv",
     "report": "schema-add-column", "outcome": "carried_on", "health": "success",
     "note": "channel dropped; byte-identical to baseline run 4.",
     "quotes": ["**Byte-identical to baseline run 4:**"]},
    {"id": "add-column-rerun-1", "scenario": "schema-add-column", "label": "Re-run 18:30 (a)",
     "run_type": "manual", "source": "observations/schema-add-column.md",
     "trigger_time": "18:30:12", "completion_time": "18:30:15", "output_time": "18:30:18",
     "blob": "RhombusAI_output_1791099018130.csv", "same_bytes_as": "baseline-run-4",
     "outcome": "carried_on", "health": "success",
     "note": "Confirmation re-run with schema_add_column.csv visibly selected.",
     "quotes": ["logged 18:30:12–18:30:15", "Both are **byte-identical to baseline run 4**"]},
    {"id": "add-column-rerun-2", "scenario": "schema-add-column", "label": "Re-run 18:30 (b)",
     "run_type": "manual", "source": "observations/schema-add-column.md",
     "trigger_time": "18:30:25", "completion_time": "18:30:29", "output_time": "18:30:31",
     "blob": "RhombusAI_output_1791099031596.csv", "same_bytes_as": "baseline-run-4",
     "outcome": "carried_on", "health": "success",
     "note": "Confirmation re-run with schema_add_column.csv visibly selected.",
     "quotes": ["18:30:25–18:30:29", "Both are **byte-identical to baseline run 4**"]},

    {"id": "combined-manual", "scenario": "schema-combined", "label": "First run",
     "run_type": "manual", "source": "observations/schema-combined.md",
     "outcome": "stopped", "health": "failed",
     "note": "Failed: ['id', 'transaction_date'] not in index. No output.",
     "quotes": ["failed (`['id', 'transaction_date'] not in index`)"]},
    {"id": "combined-retest", "scenario": "schema-combined", "label": "Retest",
     "run_type": "retest", "source": "observations/schema-combined.md",
     "outcome": "stopped", "health": "failed", "chatbot_fix": "didn't work",
     "note": "Identical error after the chatbot's header-lowercasing fix. No output.",
     "quotes": ["failed (identical error)", "**Fix grade: didn't work.**"]},

    {"id": "dollars-to-cents-manual", "scenario": "semantic-dollars-to-cents", "label": "Run",
     "run_type": "manual", "source": "observations/semantic-dollars-to-cents.md",
     "trigger_time": "16:14:31", "completion_time": "16:14:34",
     "blob": "RhombusAI_output_1791090876827.csv", "report": "semantic-dollars-to-cents",
     "outcome": "carried_on", "health": "success_wrong_or_empty",
     "note": "\"Pipeline completed successfully\", no warning; every money value ×100.",
     "quotes": ["| `manual` | 16:14:31–16:14:34 | completed successfully |"]},

    {"id": "date-swap-manual", "scenario": "semantic-date-swap", "label": "Run",
     "run_type": "manual", "source": "observations/semantic-date-swap.md",
     "completion_time": "16:16:54", "blob": "RhombusAI_output_1791091017015.csv",
     "report": "semantic-date-swap", "outcome": "carried_on",
     "health": "success_wrong_or_empty",
     "note": "Start ambiguous: two \"started\" entries (16:16:47, 16:16:52), so duration "
             "not computed. 81 of 218 dates wrong.",
     "quotes": ["16:16:47 or 16:16:52 (two start entries) – 16:16:54"]},

    # ▶ runs on baseline.csv during the UI test work (PLAN.md → Findings log).
    {"id": "ui-1707-a", "scenario": "ui-test-session", "label": "~17:07 test 6 (1st)",
     "run_type": "ui-test", "source": "PLAN.md", "outcome": "stopped",
     "health": "failed",
     "note": "src_output failure logged (card at 05:07:32 PM); no export; 300 s Azure poll "
             "timed out.", "quotes": ["**~17:07, test 6, twice: failure logged, no export.**",
                                       "the 300 s Azure poll timed out"]},
    {"id": "ui-1707-b", "scenario": "ui-test-session", "label": "~17:07 test 6 (2nd)",
     "run_type": "ui-test", "source": "PLAN.md", "outcome": NOT_RECORDED, "health": "failed",
     "note": "No export. Whether a src_output failure was logged isn't established.",
     "quotes": ["so only \"no export\" is established for it"]},
    {"id": "ui-1723-manual", "scenario": "ui-test-session", "label": "17:23 ▶ normal browser",
     "run_type": "manual", "source": "PLAN.md", "output_time": "17:23:06",
     "blob": "RhombusAI_output_1791094986135.csv", "outcome": "carried_on",
     "health": "success", "note": "No failure logged; exported. Output not validated.",
     "quotes": ["**17:23, manual ▶ in a normal browser: no failure, exported**"]},
    {"id": "ui-1724", "scenario": "ui-test-session", "label": "17:24 test 6",
     "run_type": "ui-test", "source": "PLAN.md", "output_time": "17:24:30",
     "blob": "RhombusAI_output_1791095070309.csv", "same_bytes_as": "baseline-run-4",
     "outcome": "carried_on", "health": "success",
     "note": "No failure logged; byte-identical to baseline run 4.",
     "quotes": ["**17:24, test 6: no failure, exported**",
                "(17:24:30), byte-identical to baseline run 4"]},
    {"id": "ui-1803", "scenario": "ui-test-session", "label": "~18:03 test 6",
     "run_type": "ui-test", "source": "PLAN.md", "outcome": NOT_RECORDED, "health": "failed",
     "note": "No export. Whether a src_output failure was logged isn't established.",
     "quotes": ["**~18:03, test 6 (user run): no export.**"]},
    {"id": "ui-1806", "scenario": "ui-test-session", "label": "18:06 test 6",
     "run_type": "ui-test", "source": "PLAN.md", "output_time": "18:07:03",
     "blob": "RhombusAI_output_1791097623381.csv", "report": "ui-run-1806",
     "outcome": "contradictory", "health": "success",
     "note": "src_output failure logged at 18:06:43, yet a correct export 20 s later.",
     "quotes": ["**18:06, test 6 with timestamp-scoped log checks: failure logged AND exported.**",
                "06:06:43 PM"]},
    {"id": "ui-1852", "scenario": "ui-test-session", "label": "18:52 test 6",
     "run_type": "ui-test", "source": "PLAN.md", "output_time": "18:56:23",
     "blob": "RhombusAI_output_1791100583085.csv", "same_bytes_as": "baseline-run-4",
     "validator_from_text": "fail",
     "outcome": "contradictory", "health": "success",
     "note": "src_output failure reported by the user; correct export about 4 min later. "
             "Output files named by ui-tests/test_journey.py (ui-run-20261004-1852z).",
     "quotes": ["**18:52, ▶ Run (user report): failure logged AND exported.**",
                ("It is byte-identical to baseline run 4 (SHA-256 `ebedc745…`; validator: only "
                 "the 3 known baseline failures; determinism pass)"),
                "`outputs/ui-run-20261004-1852z.*`"]},
]

RECORD_KEYS = (
    "id", "scenario", "scenario_label", "category", "label", "run_type", "trigger_time",
    "completion_time", "output_time", "duration_s", "outcome", "health", "output_blob",
    "rows_out", "validator_overall", "failed_checks", "semantic_anomaly",
    "semantic_metrics", "raw_sha256", "canonical_sha256", "hash_basis", "chatbot_fix",
    "severity", "note", "observation", "observation_url", "sources",
)


class SourceMismatch(ValueError):
    """A value in the run list isn't found in the file it cites."""


def read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def require(text: str, needle: str, where: str) -> None:
    if flat(needle) not in flat(text):
        raise SourceMismatch(f"{where}: {needle!r} not found")


def severity_of(observation: str) -> str:
    """Rubric levels in bold on the header's Severity row, e.g. 'High' or 'High / Low'."""
    m = re.search(r"^\| \*\*Severity[^|]*\|(.*)\|\s*$", read(observation), re.MULTILINE)
    if not m:
        return NOT_RECORDED
    levels = re.findall(r"\*\*(Critical|High|Medium|Low|Info)\*\*", m.group(1))
    return " / ".join(dict.fromkeys(levels)) or NOT_RECORDED


def iso(hms: str | None) -> str:
    return f"{DATE}T{hms}{TZ}" if hms else NOT_RECORDED


def seconds(start: str, end: str) -> int:
    def secs(hms: str) -> int:
        h, m, s = (int(part) for part in hms.split(":"))
        return h * 3600 + m * 60 + s

    return secs(end) - secs(start)


def load_report(report_id: str) -> dict:
    return json.loads(read(REPORTS.format(report_id)))


def validator_fields(report: dict) -> dict:
    checks = report["checks"]
    semantic = checks["semantic_anomaly"]
    anomaly = {"fail": "yes", "pass": "no"}.get(semantic["status"], "n/a")
    return {
        "rows_out": report["semantic_fingerprint"]["output"]["row_count"],
        "validator_overall": report["overall"],
        "failed_checks": [name for name, c in checks.items() if c["status"] == "fail"],
        "semantic_anomaly": anomaly,
        "semantic_metrics": [a["metric"] for a in semantic.get("anomalies", [])],
        "raw_sha256": report["files"]["output"]["raw_output_sha256"],
        "canonical_sha256": report["files"]["output"]["canonical_data_sha256"],
    }


def build_record(run: dict, scenario: dict, severity: str, by_id: dict) -> dict:
    src = run["source"]
    text = read(src)
    where = f"{run['id']} ({src})"
    for key in ("trigger_time", "completion_time", "output_time"):
        if run.get(key):
            require(text, run[key], where)
    if run.get("blob"):
        # Sources sometimes abbreviate the name (`…1791095070309.csv`); the ms stamp is unique.
        require(text, run["blob"].removeprefix("RhombusAI_output_"), where)
    for quote in run.get("quotes", []):
        require(text, quote, where)

    rec = {
        "id": run["id"], "scenario": run["scenario"], "scenario_label": scenario["label"],
        "category": scenario["category"], "label": run["label"], "run_type": run["run_type"],
        "trigger_time": iso(run.get("trigger_time")),
        "completion_time": iso(run.get("completion_time")),
        "output_time": iso(run.get("output_time")),
        "duration_s": (seconds(run["trigger_time"], run["completion_time"])
                       if run.get("trigger_time") and run.get("completion_time") else None),
        "outcome": run["outcome"], "health": run["health"],
        "output_blob": run.get("blob") or "none",
        "rows_out": 0 if not run.get("blob") else NOT_RECORDED,
        "validator_overall": "not run (no output)" if not run.get("blob") else NOT_RECORDED,
        "failed_checks": [], "semantic_anomaly": NOT_RECORDED if run.get("blob") else "n/a",
        "semantic_metrics": [],
        "raw_sha256": NOT_RECORDED if run.get("blob") else "none",
        "canonical_sha256": NOT_RECORDED if run.get("blob") else "none", "hash_basis": None,
        "chatbot_fix": run.get("chatbot_fix") or ("not used" if run["run_type"] != "retest"
                                                  else NOT_RECORDED),
        "severity": severity, "note": run["note"],
        "observation": scenario["observation"],
        "observation_url": GITHUB_BLOB + scenario["observation"],
        "sources": [src],
    }
    if run.get("report"):
        rec.update(validator_fields(load_report(run["report"])))
        rec["hash_basis"] = "validator report"
        rec["sources"].append(REPORTS.format(run["report"]))
    elif run.get("same_bytes_as"):
        ref = by_id[run["same_bytes_as"]]
        rec["raw_sha256"], rec["canonical_sha256"] = ref["raw_sha256"], ref["canonical_sha256"]
        rec["rows_out"] = ref["rows_out"]
        rec["hash_basis"] = f"stated byte-identical to {ref['id']}"
    if run.get("validator_from_text"):
        rec["validator_overall"] = run["validator_from_text"]
        rec["failed_checks"] = list(KNOWN_BASELINE_FAILURES)
    return rec


def run3_differences() -> list[dict]:
    """Side-by-side cells that differ between run 3 and run 2, from the run 3 report samples."""
    det = load_report("manual-dryrun-3")["checks"]["determinism"]
    header = ["id", "name", "email", "country", "price", "qty", "total", "transaction_date",
              "status"]

    def by_id(rows):
        return {int(float(r.split(",")[0])): r.split(",") for r in rows}

    ours = by_id(det["rows_only_in_output"]["sample"])
    ref = by_id(det["rows_only_in_baseline_output"]["sample"])
    diffs = []
    for row_id in sorted(ours.keys() & ref.keys()):
        for col, new, old in zip(header, ours[row_id], ref[row_id], strict=True):
            if new != old:
                diffs.append({"id": row_id, "column": col, "reference": old, "run_3": new})
    return diffs


def build() -> dict:
    scenarios = {s["id"]: s for s in SCENARIOS}
    severities = {s["id"]: ("not assessed" if s["category"] == "ui-test"
                            else severity_of(s["observation"])) for s in SCENARIOS}
    records: dict[str, dict] = {}
    for run in RUNS:
        sc = scenarios[run["scenario"]]
        records[run["id"]] = build_record(run, sc, severities[sc["id"]], records)

    heatmap = []
    for s in SCENARIOS:
        if not s["cells"]:
            continue
        text = read(s["observation"])
        row = {"scenario": s["id"], "label": s["label"], "observation_url":
               GITHUB_BLOB + s["observation"], "severity": severities[s["id"]]}
        for key, (cls, label, quote) in s["cells"].items():
            require(text, quote, f"heat map {s['id']}.{key}")
            row[key] = {"class": cls, "text": label}
        heatmap.append(row)

    manifests = {}
    for path in sorted((REPO / "datasets").glob("*.manifest.json")):
        m = json.loads(path.read_text(encoding="utf-8"))
        manifests[m.get("scenario", "baseline")] = {"dataset": m["dataset"], "change": m.get("change", "")}

    return {
        "generated_from": "tracked repo files only (observations/, PLAN.md, datasets/)",
        "timezone": "AEDT (UTC+11)",
        "github_base": GITHUB_BLOB,
        "scenarios": [{"id": s["id"], "label": s["label"], "category": s["category"],
                       "observation_url": GITHUB_BLOB + s["observation"],
                       "severity": severities[s["id"]],
                       "change": manifests.get(s["id"], {}).get("change", "")}
                      for s in SCENARIOS],
        "runs": list(records.values()),
        "heatmap": heatmap,
        "run3_differences": run3_differences(),
        "excluded": [
            "Log anomaly at 16:14:23–16:14:26 before the dollars-to-cents run (not a test run).",
            "Mistaken rename-case run on baseline.csv (RhombusAI_output_1791089499109.csv).",
            "Runs logged at 17:00:02 and 18:05:27 with no ▶ or Apply click (no output).",
            "Unattributed output blobs listed in the observations.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=REPO / "docs" / "data.json")
    args = ap.parse_args()
    data = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {args.out} ({len(data['runs'])} runs)")


if __name__ == "__main__":
    main()
