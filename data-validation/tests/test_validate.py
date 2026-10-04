"""Offline tests for data-validation/validate.py and cleaning_policy.py.

Fixture outputs are written by hand from datasets/cleaning-policy.md, not produced by the
policy engine, so the engine is checked against an independent expectation.
"""

import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path

import cleaning_policy as cp
import pytest
import validate as v

REPO = Path(__file__).resolve().parents[2]
HEADER = "id,name,email,country,price,qty,total,transaction_date,status"

INPUT = f"""{HEADER}
1,alice nguyen,Alice.Nguyen@Example.com ,australia,$10.00,2,20.00,07 Mar 2025,COMPLETED
2,Ben Smith,ben.smith@example.org,Canada,5.50,3,,2025/03/08,pending
2,Ben Smith,BEN.SMITH@example.org,Canada,5.50,3,,2025/03/08,pending
3,Chloe Patel,chloe.patel@example.net,Atlantis,1.00,1,1.000,25/03/2025,lost
4,Daniel Chen,not-an-email,India,abc,1,1.00,2025-03-01,pending
5,Emma Brown,emma@example.com,India,2.00,0,0.00,2025-03-01,pending
6,Farah Kumar,farah@example.com,India,2.00,1,2.00,05/03/2025,pending
7,George Lee,george@example.com,Germany,3.00,2,6.01,2025-03-02,refunded
8,Alice Nguyen,alice.nguyen@example.com,Australia,4.00,1,4.00,2025-03-03,completed
9,Hana Singh,hana@example.com,India,1.10,3,3.30,2025-02-30,pending
1,alice nguyen,Alice.Nguyen@Example.com ,australia,$10.00,2,20.00,07 Mar 2025,COMPLETED
10,Isaac  wilson,isaac@example,Singapore,1.10,3,3.30,"March 01, 2025",Pending
11,,,,2.00,1,,2025-04-02,
"""
# Hand-written policy-correct output for INPUT.
EXPECTED = f"""{HEADER}
1,Alice Nguyen,alice.nguyen@example.com,Australia,10.00,2,20.00,2025-03-07,completed
2,Ben Smith,ben.smith@example.org,Canada,5.50,3,16.50,2025-03-08,pending
3,Chloe Patel,chloe.patel@example.net,,1.00,1,1.00,2025-03-25,
8,Alice Nguyen,alice.nguyen@example.com,Australia,4.00,1,4.00,2025-03-03,completed
10,Isaac Wilson,,Singapore,1.10,3,3.30,2025-03-01,pending
11,,,,2.00,1,2.00,2025-04-02,
"""


def write(tmp_path: Path, name: str, text: str | bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
    return p


def run(tmp_path, output_text, input_text=None, baseline_text=None, manifest=None):
    inp = write(tmp_path, "input.csv", input_text or INPUT)
    out = write(tmp_path, "output.csv", output_text)
    argv = ["--scenario", "test", "--input", str(inp), "--output", str(out),
            "--report", str(tmp_path / "report.json")]
    if baseline_text is not None:
        argv += ["--baseline-output", str(write(tmp_path, "baseline.csv", baseline_text))]
    if manifest is not None:
        mp = tmp_path / "manifest.json"
        mp.write_text(json.dumps(manifest), encoding="utf-8")
        argv += ["--manifest", str(mp)]
    else:  # never pick up the real baseline manifest for fixtures
        mp = tmp_path / "no-manifest.json"
        mp.write_text(json.dumps({"sha256": "none"}), encoding="utf-8")
        argv += ["--manifest", str(mp)]
    code = v.main(argv)
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    return code, report


def status(report, check):
    return report["checks"][check]["status"]


def edit_output(replacements: list[tuple[str, str]]) -> str:
    text = EXPECTED
    for a, b in replacements:
        assert a in text, a
        text = text.replace(a, b)
    return text


def scale_money(text: str, factor: int) -> str:
    rows = list(csv.reader(io.StringIO(text)))
    for r in rows[1:]:
        for i in (4, 6):
            if r[i] and r[i].lstrip("$").replace(".", "", 1).isdigit():
                prefix = "$" if r[i].startswith("$") else ""
                r[i] = prefix + str((Decimal(r[i].lstrip("$")) * factor).quantize(Decimal("0.01")))
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


# ---------------------------------------------------------------- policy engine

def test_engine_classifies_fixture_rows():
    rows = list(csv.DictReader(io.StringIO(INPUT)))
    outcomes = cp.apply_policy(rows)
    rejected = {o.id: o.primary_reason for o in outcomes if o.outcome == "rejected"}
    assert rejected == {"4": "price_non_numeric", "5": "qty_non_positive", "6": "date_ambiguous",
                        "7": "total_mismatch", "9": "date_impossible"}
    dups = sorted((o.id, o.duplicate_kind) for o in outcomes if o.outcome == "duplicate")
    assert dups == [("1", "exact"), ("2", "near")]
    kept = {o.id: o.expected for o in outcomes if o.outcome == "kept"}
    expected = {r["id"]: r for r in csv.DictReader(io.StringIO(EXPECTED))}
    assert kept == expected


@pytest.mark.parametrize("text,expected", [
    ("2025-03-07", ("2025-03-07", None)),
    ("07 Mar 2025", ("2025-03-07", None)),
    ("March 07, 2025", ("2025-03-07", None)),
    ("2025/03/07", ("2025-03-07", None)),
    ("25/03/2025", ("2025-03-25", None)),
    ("05/03/2025", (None, "date_ambiguous")),
    ("03/25/2025", (None, "date_unrecognised")),
    ("2025-02-30", (None, "date_impossible")),
    ("2025-13-05", (None, "date_impossible")),
    ("7th March", (None, "date_unrecognised")),
])
def test_explicit_date_formats(text, expected):
    d, why = cp.parse_date(text)
    assert ((d.isoformat() if d else None), why) == expected


def test_total_rule_uses_decimal_not_float():
    # 1.10 * 3 = 3.3000000000000003 in float; must equal 3.30 under the policy.
    assert 1.10 * 3 != 3.30
    _, reasons, _ = cp._normalise({"id": "1", "name": "A B", "email": "a@b.co", "country": "India",
                                   "price": "1.10", "qty": "3", "total": "3.30",
                                   "transaction_date": "2025-01-01", "status": "pending"})
    assert reasons == []


def test_engine_on_real_baseline_matches_policy_section_6():
    rows = list(csv.DictReader(io.StringIO((REPO / "datasets/baseline.csv").read_text("utf-8"))))
    s = cp.summarise(cp.apply_policy(rows))
    assert s == {"input_rows": 250, "duplicates_removed": 16, "rejected": 16,
                 "expected_output_rows": 218, "kept_unchanged": 164, "kept_with_null": 19,
                 "kept_repaired_only": 35}


# ---------------------------------------------------------------- validator: pass path

def test_policy_correct_output_passes(tmp_path):
    code, report = run(tmp_path, EXPECTED)
    assert code == 0, json.dumps({k: c for k, c in report["checks"].items()
                                  if c["status"] == "fail"}, indent=1)
    assert report["overall"] == "pass"
    for check in ("input_contract", "schema", "deduplication", "row_count_reconciliation",
                  "values_match_policy", "output_format", "rule_name_normalised",
                  "rule_email_invalid_to_null", "rule_country_unknown_to_null",
                  "rule_total_filled", "rule_date_reformatted"):
        assert status(report, check) == "pass", check
    assert status(report, "determinism") == "not_applicable"
    assert status(report, "semantic_anomaly") == "not_applicable"
    assert status(report, "manifest_consistency") == "not_applicable"
    rec = report["checks"]["row_count_reconciliation"]
    assert (rec["input_count"], rec["expected_output_count"], rec["actual_output_count"]) == (13, 6, 6)
    assert report["semantic_fingerprint"]["output"]["row_count"] == 6


def test_real_baseline_manifest_consistency_and_perfect_output(tmp_path):
    """Plumbing on the real baseline: engine vs manifest, and an engine-built output passes."""
    rows = list(csv.DictReader(io.StringIO((REPO / "datasets/baseline.csv").read_text("utf-8"))))
    kept = [o.expected for o in cp.apply_policy(rows) if o.outcome == "kept"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cp.COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(kept)
    out = write(tmp_path, "out.csv", buf.getvalue())
    code = v.main(["--scenario", "baseline", "--input", str(REPO / "datasets/baseline.csv"),
                   "--output", str(out), "--report", str(tmp_path / "r.json")])
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert status(report, "manifest_consistency") == "pass"
    assert code == 0 and report["overall"] == "pass"


# ---------------------------------------------------------------- validator: failures

def test_rejected_row_left_in_output_fails(tmp_path):
    out = EXPECTED + "7,George Lee,george@example.com,Germany,3.00,2,6.01,2025-03-02,refunded\n"
    code, report = run(tmp_path, out)
    assert code == 1 and report["overall"] == "fail"
    rules = {r["rule"]: r for r in report["checks"]["row_count_reconciliation"]["rules"]}
    assert rules["reject_total_mismatch"]["ids_not_removed"] == ["7"]
    assert rules["reject_total_mismatch"]["actual_removed"] == 0


def test_dedup_by_email_is_caught(tmp_path):
    out = edit_output([("8,Alice Nguyen,alice.nguyen@example.com,Australia,4.00,1,4.00,2025-03-03,completed\n", "")])
    code, report = run(tmp_path, out)
    assert code == 1
    dedup = report["checks"]["deduplication"]
    assert dedup["status"] == "fail"
    assert dedup["distinct_ids_sharing_email"]["missing_from_output"]["sample"] == ["8"]
    assert report["checks"]["row_count_reconciliation"]["unaccounted_rows"]["missing_from_output"]["sample"] == ["8"]


def test_duplicate_left_in_output_fails(tmp_path):
    out = EXPECTED + "2,Ben Smith,ben.smith@example.org,Canada,5.50,3,16.50,2025-03-08,pending\n"
    _, report = run(tmp_path, out)
    assert status(report, "deduplication") == "fail"
    rules = {r["rule"]: r for r in report["checks"]["row_count_reconciliation"]["rules"]}
    assert rules["dedup_near"]["ids_not_removed"] == ["2"]


def test_unnormalised_value_fails_its_rule(tmp_path):
    out = edit_output([("1,Alice Nguyen,alice.nguyen@example.com,Australia",
                        "1,Alice Nguyen,alice.nguyen@example.com,australia")])
    _, report = run(tmp_path, out)
    assert status(report, "rule_country_normalised") == "fail"
    assert status(report, "output_format") == "fail"
    assert status(report, "rule_name_normalised") == "pass"


def test_money_value_equal_but_format_wrong(tmp_path):
    out = edit_output([("5.50,3,16.50", "5.50,3,16.5")])
    _, report = run(tmp_path, out)
    assert status(report, "values_match_policy") == "pass"
    assert status(report, "rule_total_filled") == "pass"
    fmt = report["checks"]["output_format"]
    assert fmt["status"] == "fail" and "money_two_decimals" in fmt["violations"]


def test_float_formatted_ids_still_match_but_fail_format(tmp_path):
    """'1.0' matches id 1 for dedup/reconciliation; output_format still flags the text."""
    rows = list(csv.reader(io.StringIO(EXPECTED)))
    for r in rows[1:]:
        r[0], r[5] = f"{r[0]}.0", f"{r[5]}.0"
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    _, report = run(tmp_path, buf.getvalue(), baseline_text=EXPECTED)
    for check in ("deduplication", "row_count_reconciliation", "values_match_policy",
                  "rule_name_normalised", "rule_total_filled", "semantic_anomaly"):
        assert status(report, check) == "pass", check
    rec = report["checks"]["row_count_reconciliation"]
    assert rec["unaccounted_rows"]["count"] == 0
    assert report["semantic_fingerprint"]["output"]["duplicate_key_count"] == 0
    fmt = report["checks"]["output_format"]
    assert fmt["status"] == "fail"
    assert fmt["violations"]["whole_number"]["count"] == 2 * (len(rows) - 1)
    assert report["overall"] == "fail"


def test_non_zero_fraction_id_is_not_matched(tmp_path):
    out = edit_output([("\n1,Alice", "\n1.5,Alice")])
    _, report = run(tmp_path, out)
    rec = report["checks"]["row_count_reconciliation"]
    assert rec["status"] == "fail"
    assert "1" in rec["unaccounted_rows"]["missing_from_output"]["sample"]


def test_output_missing_column_blocks_dependent_checks(tmp_path):
    rows = [r.rsplit(",", 1)[0] for r in EXPECTED.strip().split("\n")]
    _, report = run(tmp_path, "\n".join(rows) + "\n")
    assert status(report, "schema") == "fail"
    assert "required column status is missing" in report["checks"]["schema"]["violations"]
    for check in ("rule_status_normalised", "rule_status_unknown_to_null", "values_match_policy"):
        assert status(report, check) == "blocked_by_schema", check
    assert report["overall"] == "fail"


def test_input_without_dedup_key_blocks_downstream(tmp_path):
    no_id = "\n".join(line.split(",", 1)[1] for line in INPUT.strip().split("\n")) + "\n"
    out_no_id = "\n".join(line.split(",", 1)[1] for line in EXPECTED.strip().split("\n")) + "\n"
    code, report = run(tmp_path, out_no_id, input_text=no_id)
    assert code == 1
    assert status(report, "input_contract") == "fail"
    assert report["checks"]["deduplication"] == {"status": "not_applicable",
                                                 "reason": "deduplication key is absent"}
    assert status(report, "row_count_reconciliation") == "blocked_by_schema"
    downstream = [k for k in report["checks"] if k.startswith("rule_")] + ["values_match_policy"]
    assert all(status(report, k) == "blocked_by_schema" for k in downstream)


def test_xlsx_output_is_a_schema_failure(tmp_path):
    code, report = run(tmp_path, b"PK\x03\x04rest-of-zip")
    assert code == 1
    assert "XLSX" in report["checks"]["schema"]["violations"][0]
    assert status(report, "row_count_reconciliation") == "blocked_by_schema"


# ---------------------------------------------------------------- determinism + semantic

def test_determinism_ignores_bom_crlf_and_row_order(tmp_path):
    inp_sha = hashlib.sha256(INPUT.encode("utf-8")).hexdigest()
    lines = EXPECTED.strip().split("\n")
    shuffled = "﻿" + "\r\n".join([lines[0]] + lines[1:][::-1]) + "\r\n"
    _, report = run(tmp_path, shuffled.encode("utf-8"), baseline_text=EXPECTED,
                    manifest={"sha256": inp_sha, "defects": {}})
    det = report["checks"]["determinism"]
    assert det == {"status": "pass", "byte_identical": False, "data_identical": True}
    files = report["files"]
    assert files["output"]["raw_output_sha256"] != files["baseline_output"]["raw_output_sha256"]
    assert files["output"]["canonical_data_sha256"] == files["baseline_output"]["canonical_data_sha256"]


def test_determinism_detects_changed_value(tmp_path):
    inp_sha = hashlib.sha256(INPUT.encode("utf-8")).hexdigest()
    _, report = run(tmp_path, edit_output([("4.00,1,4.00", "4.00,1,4.00 ")]), baseline_text=EXPECTED,
                    manifest={"sha256": inp_sha, "defects": {}})
    # Trailing space is canonicalised away, so this is data-identical...
    assert status(report, "determinism") == "pass"
    _, report = run(tmp_path, edit_output([("Ben Smith", "Ben Smyth")]), baseline_text=EXPECTED,
                    manifest={"sha256": inp_sha, "defects": {}})
    assert status(report, "determinism") == "fail"


def test_dollars_to_cents_passes_policy_but_trips_semantic_detector(tmp_path):
    code, report = run(tmp_path, scale_money(EXPECTED, 100), input_text=scale_money(INPUT, 100),
                       baseline_text=EXPECTED)
    assert status(report, "values_match_policy") == "pass"   # structurally a valid clean
    sem = report["checks"]["semantic_anomaly"]
    assert sem["status"] == "fail"
    assert {"price.p50", "total.sum"} <= {a["metric"] for a in sem["anomalies"]}
    assert status(report, "determinism") == "not_applicable"
    assert code == 1


def test_date_swap_trips_semantic_detector(tmp_path):
    # Phase-4 construction: swap day/month only inside ISO dates with day <= 12.
    swapped_in = INPUT.replace("2025-04-02", "2025-02-04")
    swapped_out = EXPECTED.replace("2025-04-02", "2025-02-04")
    _, report = run(tmp_path, swapped_out, input_text=swapped_in, baseline_text=EXPECTED)
    assert status(report, "values_match_policy") == "pass"  # every date still valid
    metrics = {a["metric"] for a in report["checks"]["semantic_anomaly"]["anomalies"]}
    assert "transaction_date.range" in metrics


def test_same_output_as_baseline_has_no_anomalies(tmp_path):
    _, report = run(tmp_path, EXPECTED, baseline_text=EXPECTED)
    assert report["checks"]["semantic_anomaly"]["status"] == "pass"


# ---------------------------------------------------------------- exit codes

def test_exit_3_when_files_missing(tmp_path):
    inp = write(tmp_path, "in.csv", INPUT)
    assert v.main(["--scenario", "x", "--input", str(tmp_path / "nope.csv"), "--output", str(inp),
                   "--report", str(tmp_path / "r.json")]) == 3
    assert v.main(["--scenario", "x", "--input", str(inp), "--output", str(tmp_path / "nope.csv"),
                   "--report", str(tmp_path / "r.json")]) == 3
    assert not (tmp_path / "r.json").exists()


def test_exit_2_on_bad_invocation(tmp_path):
    inp = write(tmp_path, "in.csv", INPUT)
    with pytest.raises(SystemExit) as exc:
        v.main(["--scenario", "Bad Name!", "--input", str(inp), "--output", str(inp),
                "--report", str(tmp_path / "r.json")])
    assert exc.value.code == 2
    with pytest.raises(SystemExit) as exc:
        v.main(["--input", str(inp)])
    assert exc.value.code == 2
    bad = write(tmp_path, "m.json", "{not json")
    assert v.main(["--scenario", "x", "--input", str(inp), "--output", str(inp),
                   "--manifest", str(bad), "--report", str(tmp_path / "r.json")]) == 2
