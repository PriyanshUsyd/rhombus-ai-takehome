"""Offline tests for scripts/build_dashboard.py and the published docs/data.json.

The build is checked for a fixed record schema, for values that trace back to the repo's
evidence, and for staleness: docs/data.json must equal a fresh build.
"""

import json
import re
from pathlib import Path

import build_dashboard as bd
import pytest

REPO = Path(__file__).resolve().parents[2]
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TIME = re.compile(r"^2026-10-04T\d{2}:\d{2}:\d{2}\+11:00$")


@pytest.fixture(scope="module")
def data():
    return bd.build()


def test_records_have_exactly_the_documented_fields(data):
    for rec in data["runs"]:
        assert tuple(rec) == bd.RECORD_KEYS, rec["id"]


def test_enums_and_formats(data):
    ids = [r["id"] for r in data["runs"]]
    assert len(ids) == len(set(ids))
    scenario_ids = {s["id"] for s in data["scenarios"]}
    for r in data["runs"]:
        assert r["scenario"] in scenario_ids
        assert r["run_type"] in bd.RUN_TYPES
        assert r["outcome"] in bd.OUTCOMES
        assert r["health"] in bd.HEALTH
        for key in ("trigger_time", "completion_time", "output_time"):
            assert r[key] == bd.NOT_RECORDED or TIME.match(r[key]), (r["id"], key)
        for key in ("raw_sha256", "canonical_sha256"):
            assert r[key] in (bd.NOT_RECORDED, "none") or HEX64.match(r[key]), (r["id"], key)
        assert r["output_blob"] == "none" or re.fullmatch(r"RhombusAI_output_\d{13}\.csv",
                                                          r["output_blob"])
        assert r["semantic_anomaly"] in ("yes", "no", "n/a", bd.NOT_RECORDED)
        assert r["observation_url"] == bd.GITHUB_BLOB + r["observation"]
        assert (REPO / r["observation"]).is_file()
        for src in r["sources"]:
            assert (REPO / src).is_file(), src


def test_no_output_means_no_rows_hash_or_validator(data):
    for r in data["runs"]:
        if r["output_blob"] == "none":
            assert r["rows_out"] == 0
            assert r["raw_sha256"] == "none"
            assert r["validator_overall"] == "not run (no output)"
            assert r["health"] == "failed"


def test_duration_only_when_both_times_logged(data):
    for r in data["runs"]:
        logged = bd.NOT_RECORDED not in (r["trigger_time"], r["completion_time"])
        assert (r["duration_s"] is not None) == logged, r["id"]
        if logged:
            assert r["duration_s"] >= 0


def test_validator_fields_match_the_reports(data):
    by_id = {r["id"]: r for r in data["runs"]}
    for run in bd.RUNS:
        if not run.get("report"):
            continue
        report = json.loads((REPO / bd.REPORTS.format(run["report"])).read_text(encoding="utf-8"))
        rec = by_id[run["id"]]
        assert rec["validator_overall"] == report["overall"]
        assert rec["raw_sha256"] == report["files"]["output"]["raw_output_sha256"]
        assert set(rec["failed_checks"]) == {k for k, c in report["checks"].items()
                                             if c["status"] == "fail"}


def test_known_results(data):
    """Spot checks against figures stated in the observations."""
    by_id = {r["id"]: r for r in data["runs"]}
    baseline = "ebedc745b23296ff1c77ced008d0dd27e051d7c1f091c1cd1efa43147310cdda"
    for rid in ("baseline-run-1", "baseline-run-2", "baseline-run-4", "add-column-manual",
                "ui-1806"):
        assert by_id[rid]["raw_sha256"] == baseline
    assert by_id["baseline-run-3"]["raw_sha256"] != baseline
    assert by_id["rename-column-retest"]["rows_out"] == 0
    assert by_id["drop-column-retest"]["rows_out"] == 222
    assert by_id["drop-column-manual"]["duration_s"] == 5
    assert by_id["dollars-to-cents-manual"]["semantic_anomaly"] == "yes"
    sev = {s["id"]: s["severity"] for s in data["scenarios"]}
    assert sev["schema-add-column"] == "Info" and sev["schema-combined"] == "Medium"


def test_run3_differences_are_decimal_ids_and_the_none_name(data):
    diffs = data["run3_differences"]
    assert {"id": 1001, "column": "id", "reference": "1001", "run_3": "1001.0"} in diffs
    assert {"id": 1017, "column": "name", "reference": "None", "run_3": ""} in diffs
    assert {d["column"] for d in diffs} == {"id", "qty", "name"}


def test_heatmap_classes(data):
    assert len(data["heatmap"]) == 7
    for row in data["heatmap"]:
        for key in ("behaviour", "chatbot", "validator"):
            assert row[key]["class"] in bd.CELL_CLASSES


def test_unverifiable_value_fails_the_build(monkeypatch):
    bad = dict(bd.RUNS[0], output_time="23:59:59")
    monkeypatch.setattr(bd, "RUNS", [bad] + bd.RUNS[1:])
    with pytest.raises(bd.SourceMismatch):
        bd.build()


def test_nothing_private_or_placeholder(data):
    text = json.dumps(data, ensure_ascii=False)
    for banned in ("TODO", "priyanshrhombus", "SharedAccessSignature", "sig=", "auto-sync",
                   "evidence-raw"):
        assert banned not in text, banned


def test_published_data_json_is_current(data):
    published = json.loads((REPO / "docs" / "data.json").read_text(encoding="utf-8"))
    assert published == data, "docs/data.json is stale: run python scripts/build_dashboard.py"
