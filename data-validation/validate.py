"""Validate a Rhombus pipeline output against its input and the approved cleaning policy.

Usage:
    python data-validation/validate.py --scenario baseline \
        --input datasets/baseline.csv --output outputs/baseline-1.csv \
        [--baseline-output outputs/baseline-1.csv] [--manifest datasets/baseline.manifest.json] \
        --report observations/evidence/validation-baseline.json

Exit codes: 0 pass · 1 validation fail · 2 bad invocation/config · 3 input/output file missing.

Every check returns status pass | fail | not_applicable (+reason) | blocked_by_schema (+reason).
Expectations are derived from the input + datasets/cleaning-policy.md (see cleaning_policy.py),
never from the output. The semantic section is an anomaly detector, not proof of correctness.

Canonical form used for canonical_data_sha256 (documented in the report too): UTF-8 BOM removed,
parsed as CSV, every cell stripped of surrounding whitespace, header kept, data rows sorted by
integer id (rows without a valid id last, then by full row), re-serialised with LF line endings
and minimal quoting. No values are reformatted and no columns are dropped (no volatile fields
are known yet).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import cleaning_policy as cp

EXIT_PASS, EXIT_FAIL, EXIT_USAGE, EXIT_MISSING = 0, 1, 2, 3
REPO = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO / "datasets" / "baseline.manifest.json"
SAMPLE_LIMIT = 20
MONEY_COLUMNS = ("price", "total")
INT_COLUMNS = ("id", "qty")

# Semantic anomaly thresholds (output vs baseline output).
ROW_COUNT_REL_CHANGE = Decimal("0.10")
MONEY_RATIO_BOUNDS = (Decimal("0.5"), Decimal("2.0"))
NULL_RATE_ABS_INCREASE = 0.05
DATE_PARSE_RATE_DROP = 0.01
DISTRIBUTION_TVD = 0.25


# ---------------------------------------------------------------- file reading

@dataclass
class CsvFile:
    path: Path
    raw: bytes
    header: list[str] | None = None
    rows: list[list[str]] = field(default_factory=list)
    error: str | None = None

    @property
    def readable(self) -> bool:
        return self.error is None and self.header is not None

    def dicts(self) -> list[dict[str, str]]:
        assert self.header is not None
        return [dict(zip(self.header, r + [""] * (len(self.header) - len(r)), strict=False))
                for r in self.rows]


def read_csv(path: Path) -> CsvFile:
    raw = path.read_bytes()
    f = CsvFile(path=path, raw=raw)
    if raw.startswith(b"PK\x03\x04"):
        f.error = "file is a ZIP container (looks like XLSX), not CSV"
        return f
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        f.error = f"not valid UTF-8: {exc}"
        return f
    try:
        rows = [r for r in csv.reader(io.StringIO(text, newline="")) if r != []]
    except csv.Error as exc:
        f.error = f"CSV parse error: {exc}"
        return f
    if not rows:
        f.error = "file is empty"
        return f
    f.header, f.rows = rows[0], rows[1:]
    return f


def canonical_id(value: str | None) -> str | None:
    """Output id used for matching: '1001' and '1001.0' both match id 1001.

    Only zero fractions are accepted ('1001.5' is still invalid). The text form is
    still flagged separately by output_format (whole_number).
    """
    m = re.fullmatch(r"(\d+)(?:\.0+)?", (value or "").strip())
    return str(int(m.group(1))) if m else None


def canonical_bytes(f: CsvFile) -> bytes:
    assert f.header is not None
    rows = [[c.strip() for c in r] for r in f.rows]
    id_pos = f.header.index("id") if "id" in f.header else None

    def key(r):
        cid = canonical_id(r[id_pos]) if id_pos is not None and id_pos < len(r) else None
        return (cid is None, int(cid) if cid else 0, r)

    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow([c.strip() for c in f.header])
    w.writerows(sorted(rows, key=key))
    return buf.getvalue().encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- helpers

def result(status: str, **details) -> dict:
    return {"status": status, **details}


def blocked(reason: str) -> dict:
    return result("blocked_by_schema", reason=reason)


def not_applicable(reason: str) -> dict:
    return result("not_applicable", reason=reason)


def sample(items: list) -> dict:
    return {"count": len(items), "sample": items[:SAMPLE_LIMIT]}


def cell_equal(col: str, expected: str, actual: str) -> bool:
    if col in MONEY_COLUMNS or col in INT_COLUMNS:
        if expected == "" or actual == "":
            return expected == actual
        a = cp.parse_decimal(actual)
        return a is not None and a == Decimal(expected)
    return expected == actual


def output_index(out_rows: list[dict[str, str]]) -> tuple[Counter, dict[str, dict], int]:
    counts: Counter = Counter()
    first: dict[str, dict] = {}
    invalid = 0
    for r in out_rows:
        cid = canonical_id(r.get("id"))
        if cid is None:
            invalid += 1
            continue
        counts[cid] += 1
        first.setdefault(cid, r)
    return counts, first, invalid


# ---------------------------------------------------------------- checks

def check_input_contract(inp: CsvFile) -> dict:
    if not inp.readable:
        return result("fail", violations=[f"input unreadable: {inp.error}"])
    header = inp.header or []
    violations = [f"required column {c} is missing" for c in cp.COLUMNS if c not in header]
    dupes = [c for c, n in Counter(header).items() if n > 1]
    violations += [f"duplicate column {c}" for c in dupes]
    warnings = [f"extra column {c} (policy: output keeps only the 9 contract columns)"
                for c in header if c not in cp.COLUMNS]
    if not violations and [c for c in header if c in cp.COLUMNS] != cp.COLUMNS:
        warnings.append("contract columns are in a different order")
    return result("fail" if violations else "pass", violations=violations, warnings=warnings)


def check_schema(out: CsvFile) -> dict:
    if not out.readable:
        return result("fail", violations=[f"output unreadable: {out.error}"])
    header = out.header or []
    violations = [f"required column {c} is missing" for c in cp.COLUMNS if c not in header]
    violations += [f"unexpected column {c}" for c in header if c not in cp.COLUMNS]
    violations += [f"duplicate column {c}" for c, n in Counter(header).items() if n > 1]
    if not violations and header != cp.COLUMNS:
        violations.append(f"column order {header} != {cp.COLUMNS}")
    ragged = [i for i, r in enumerate(out.rows, start=1) if len(r) != len(header)]
    if ragged:
        violations.append(f"{len(ragged)} data rows have a field count different from the header "
                          f"(first: row {ragged[0]})")
    return result("fail" if violations else "pass", violations=violations)


def check_deduplication(outcomes, out_rows) -> dict:
    counts, _, _ = output_index(out_rows)
    dup_in_output = {k: v for k, v in counts.items() if v > 1}
    by_email: dict[str, list[str]] = {}
    for o in outcomes:
        if o.outcome == "kept" and o.expected["email"]:
            by_email.setdefault(o.expected["email"], []).append(o.id)
    shared = sorted({i for ids in by_email.values() if len(ids) > 1 for i in ids}, key=int)
    collapsed = [i for i in shared if counts[i] == 0]
    kinds = Counter(o.duplicate_kind for o in outcomes if o.outcome == "duplicate")
    status = "fail" if dup_in_output or collapsed else "pass"
    return result(
        status,
        key="id",
        survivor="first occurrence in file order",
        input_duplicate_rows={"exact": kinds["exact"], "near": kinds["near"],
                              "conflicting": kinds["conflicting"]},
        duplicate_ids_in_output=sample(sorted(dup_in_output, key=int)),
        distinct_ids_sharing_email={"expected_kept": len(shared),
                                    "missing_from_output": sample(collapsed)},
    )


def check_reconciliation(outcomes, out_rows) -> dict:
    counts, _, invalid_ids = output_index(out_rows)
    input_ids = {o.id for o in outcomes if o.id}
    kept_ids = [o.id for o in outcomes if o.outcome == "kept"]
    rules = []

    for kind in ("exact", "near", "conflicting"):
        rows = [o for o in outcomes if o.duplicate_kind == kind]
        if not rows:
            continue
        per_id = Counter(o.id for o in rows)
        not_removed = [i for i in sorted(per_id, key=int) if counts[i] > 1]
        missed = sum(min(counts[i] - 1, per_id[i]) for i in not_removed)
        rules.append({"rule": f"dedup_{kind}", "expected_removed": len(rows),
                      "actual_removed": len(rows) - missed, "ids_not_removed": not_removed})

    for reason in cp.REJECT_REASONS:
        rows = [o for o in outcomes if o.outcome == "rejected" and o.primary_reason == reason]
        if not rows:
            continue
        if reason in ("id_missing", "id_invalid"):
            actual = max(0, len(rows) - invalid_ids)
            not_removed = [f"input row {o.line}" for o in rows][: len(rows) - actual]
        else:
            not_removed = [o.id for o in rows if counts[o.id] > 0]
            actual = len(rows) - len(not_removed)
        rules.append({"rule": f"reject_{reason}", "expected_removed": len(rows),
                      "actual_removed": actual, "ids_not_removed": not_removed})

    missing = [i for i in kept_ids if counts[i] == 0]
    unknown = sorted((i for i in counts if i not in input_ids), key=int)
    unaccounted = {
        "missing_from_output": sample(missing),
        "unexpected_in_output": sample(unknown + ([f"{invalid_ids} rows with missing/invalid id"]
                                                  if invalid_ids else [])),
    }
    unaccounted["count"] = len(missing) + len(unknown) + invalid_ids
    ok = (all(r["actual_removed"] == r["expected_removed"] for r in rules)
          and unaccounted["count"] == 0 and len(out_rows) == len(kept_ids))
    return result(
        "pass" if ok else "fail",
        input_count=len(outcomes),
        expected_output_count=len(kept_ids),
        actual_output_count=len(out_rows),
        rules=rules,
        unaccounted_rows=unaccounted,
    )


MANIFEST_EXPECTATION = {
    "exact_duplicate": "dup:exact",
    "near_duplicate_email_variant": "dup:near",
    "email_case_whitespace_variant": "email_normalised",
    "name_casing_whitespace": "name_normalised",
    "country_casing_whitespace": "country_normalised",
    "status_casing_whitespace": "status_normalised",
    "price_currency_symbol": "price_symbol_stripped",
    "date_format_d_mon_yyyy": "date_reformatted",
    "date_format_month_d_yyyy": "date_reformatted",
    "date_format_yyyy_slash": "date_reformatted",
    "date_format_dd_mm_yyyy": "date_reformatted",
    "missing_total": "total_filled",
    "missing_name": "name_missing_kept_null",
    "missing_email": "email_missing_kept_null",
    "missing_country": "country_missing_kept_null",
    "missing_status": "status_missing_kept_null",
    "email_malformed": "email_invalid_to_null",
    "country_unknown": "country_unknown_to_null",
    "status_unknown": "status_unknown_to_null",
    "missing_price": "reject:price_missing",
    "missing_qty": "reject:qty_missing",
    "missing_transaction_date": "reject:date_missing",
    "price_non_numeric": "reject:price_non_numeric",
    "qty_non_positive": "reject:qty_non_positive",
    "date_impossible": "reject:date_impossible",
    "total_mismatch": "reject:total_mismatch",
}


def check_manifest(outcomes, manifest: dict | None, input_sha: str) -> dict:
    """Self-check: the policy engine's per-row classification vs the generator's manifest."""
    if manifest is None:
        return not_applicable("no manifest available")
    if manifest.get("sha256") != input_sha:
        return not_applicable("manifest describes a different file (sha256 differs from input)")
    tags: dict[str, set[str]] = {}
    for o in outcomes:
        if not o.id:
            continue
        found = tags.setdefault(o.id, set())
        if o.outcome == "duplicate":
            found.add(f"dup:{o.duplicate_kind}")
        elif o.outcome == "rejected":
            found.add(f"reject:{o.primary_reason}")
        else:
            found.update(o.actions)
    mismatches = []
    for defect, info in manifest.get("defects", {}).items():
        tag = MANIFEST_EXPECTATION.get(defect)
        if tag is None:
            mismatches.append({"defect": defect, "problem": "defect unknown to the validator"})
            continue
        engine = sorted(int(i) for i, t in tags.items() if tag in t)
        manifest_ids = sorted(info.get("ids", []))
        if tag == "date_reformatted":  # several manifest defects share one action
            group = [d for d, t in MANIFEST_EXPECTATION.items() if t == tag]
            manifest_ids = sorted(i for d in group for i in manifest["defects"].get(d, {}).get("ids", []))
        if engine != manifest_ids:
            mismatches.append({"defect": defect, "expected_tag": tag,
                               "manifest_ids": manifest_ids, "engine_ids": engine})
    return result("fail" if mismatches else "pass", mismatches=mismatches,
                  manifest_row_count=manifest.get("row_count"), input_row_count=len(outcomes))


def check_rule(action: str, outcomes, out: CsvFile, out_first: dict[str, dict]) -> dict:
    col = cp.ACTIONS[action]
    if col not in (out.header or []):
        return blocked(f"output column {col} is missing")
    affected = [o for o in outcomes if o.outcome == "kept" and action in o.actions]
    if not affected:
        return not_applicable("no input rows need this rule")
    evaluated = [o for o in affected if o.id in out_first]
    if not evaluated:
        return not_applicable("all affected rows are absent from the output "
                              "(see row_count_reconciliation)")
    mismatches = [{"id": o.id, "column": col, "expected": o.expected[col],
                   "actual": out_first[o.id][col]}
                  for o in evaluated if not cell_equal(col, o.expected[col], out_first[o.id][col])]
    return result("fail" if mismatches else "pass", column=col, affected_rows=len(affected),
                  evaluated_rows=len(evaluated), mismatches=sample(mismatches))


def check_values(outcomes, out: CsvFile, out_first: dict[str, dict]) -> dict:
    missing_cols = [c for c in cp.COLUMNS if c not in (out.header or [])]
    if missing_cols:
        return blocked(f"output columns missing: {missing_cols}")
    per_col: Counter = Counter()
    mismatches = []
    evaluated = 0
    for o in outcomes:
        if o.outcome != "kept" or o.id not in out_first:
            continue
        evaluated += 1
        for col in cp.COLUMNS:
            actual = out_first[o.id][col]
            if not cell_equal(col, o.expected[col], actual):
                per_col[col] += 1
                mismatches.append({"id": o.id, "column": col,
                                   "expected": o.expected[col], "actual": actual})
    return result("fail" if mismatches else "pass", evaluated_rows=evaluated,
                  mismatches_by_column=dict(per_col), mismatches=sample(mismatches))


def check_format(out: CsvFile, out_rows: list[dict[str, str]]) -> dict:
    header = out.header or []
    violations: dict[str, list] = {}

    def flag(rule: str, row: int, col: str, value: str):
        violations.setdefault(rule, []).append({"row": row, "column": col, "value": value})

    for n, r in enumerate(out_rows, start=1):
        for col in header:
            v = r.get(col, "")
            if v != v.strip():
                flag("no_surrounding_whitespace", n, col, v)
        for col in MONEY_COLUMNS:
            if col in header and r[col] and not re.fullmatch(r"-?\d+\.\d{2}", r[col]):
                flag("money_two_decimals", n, col, r[col])
        for col in INT_COLUMNS:
            if col in header and r[col] and not re.fullmatch(r"\d+", r[col]):
                flag("whole_number", n, col, r[col])
        if "transaction_date" in header and r["transaction_date"]:
            d, _ = cp.parse_date(r["transaction_date"])
            if d is None or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["transaction_date"]):
                flag("iso_date", n, "transaction_date", r["transaction_date"])
        if "country" in header and r["country"] and r["country"] not in cp.COUNTRIES:
            flag("country_in_allowed_list", n, "country", r["country"])
        if "status" in header and r["status"] and r["status"] not in cp.STATUSES:
            flag("status_in_allowed_set", n, "status", r["status"])
        if "email" in header and r["email"] and r["email"] != r["email"].lower():
            flag("email_lowercase", n, "email", r["email"])
    return result("fail" if violations else "pass",
                  violations={k: sample(v) for k, v in violations.items()})


# ---------------------------------------------------------------- semantic fingerprint

def quantile(sorted_vals: list[Decimal], q: Decimal) -> str | None:
    """Nearest-rank quantile on already sorted Decimals."""
    if not sorted_vals:
        return None
    rank = max(1, int((q * len(sorted_vals)).to_integral_value(rounding=ROUND_HALF_UP)))
    return str(sorted_vals[min(rank, len(sorted_vals)) - 1])


def fingerprint(out: CsvFile) -> dict:
    rows = out.dicts()
    header = out.header or []
    fp: dict = {"row_count": len(rows), "columns": {}}
    for col in header:
        values = [r[col].strip() for r in rows]
        info: dict = {
            "null_rate": round(sum(v == "" for v in values) / len(rows), 6) if rows else 0.0,
            "distinct_count": len({v for v in values if v}),
        }
        if col in MONEY_COLUMNS or col == "qty":
            nums = sorted(d for d in (cp.parse_decimal(v) for v in values if v) if d is not None)
            info.update({
                "numeric_count": len(nums),
                "sum": str(sum(nums, Decimal(0))),
                "min": str(nums[0]) if nums else None,
                "max": str(nums[-1]) if nums else None,
                **{f"p{p}": quantile(nums, Decimal(p) / 100) for p in (10, 25, 50, 75, 90)},
            })
        if col in ("country", "status"):
            info["distribution"] = dict(sorted(Counter(v for v in values if v).items()))
        if col == "transaction_date":
            parsed = []
            for v in values:
                if v and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                    try:
                        parsed.append(date.fromisoformat(v))
                    except ValueError:
                        pass
            non_empty = sum(1 for v in values if v)
            info.update({
                "parse_success_rate": round(len(parsed) / non_empty, 6) if non_empty else None,
                "min": min(parsed).isoformat() if parsed else None,
                "max": max(parsed).isoformat() if parsed else None,
                "month_histogram": dict(sorted(Counter(d.strftime("%Y-%m") for d in parsed).items())),
                "day_le_12_share": round(sum(d.day <= 12 for d in parsed) / len(parsed), 6)
                if parsed else None,
            })
        fp["columns"][col] = info
    if "id" in header:
        ids = [canonical_id(r["id"]) for r in rows]
        fp["duplicate_key_count"] = len(rows) - len({i for i in ids if i})
    if {"price", "qty", "total"} <= set(header):
        failures = 0
        for r in rows:
            p, q, t = (cp.parse_decimal(r[c].strip()) for c in ("price", "qty", "total"))
            if None not in (p, q, t) and t != (p * q).quantize(cp.CENT, rounding=ROUND_HALF_UP):
                failures += 1
        fp["cross_field_failures"] = failures
    return fp


def tvd(a: dict, b: dict) -> float:
    ta, tb = sum(a.values()), sum(b.values())
    if not ta or not tb:
        return 0.0 if ta == tb else 1.0
    return 0.5 * sum(abs(a.get(k, 0) / ta - b.get(k, 0) / tb) for k in set(a) | set(b))


def check_semantic(fp: dict, base: dict | None) -> dict:
    if base is None:
        return not_applicable("no --baseline-output given")
    anomalies = []

    def add(metric, baseline, current, rule):
        anomalies.append({"metric": metric, "baseline": baseline, "current": current, "rule": rule})

    if base["row_count"]:
        change = abs(Decimal(fp["row_count"] - base["row_count"])) / base["row_count"]
        if change > ROW_COUNT_REL_CHANGE:
            add("row_count", base["row_count"], fp["row_count"],
                f"relative change > {ROW_COUNT_REL_CHANGE}")
    lo, hi = MONEY_RATIO_BOUNDS
    for col, cur in fp["columns"].items():
        ref = base["columns"].get(col)
        if ref is None:
            add(f"{col}", "absent", "present", "column not in baseline output")
            continue
        if cur["null_rate"] - ref["null_rate"] > NULL_RATE_ABS_INCREASE:
            add(f"{col}.null_rate", ref["null_rate"], cur["null_rate"],
                f"absolute increase > {NULL_RATE_ABS_INCREASE}")
        if col in MONEY_COLUMNS:
            for stat in ("p50", "sum"):
                if ref.get(stat) and cur.get(stat) and Decimal(ref[stat]) != 0:
                    ratio = Decimal(cur[stat]) / Decimal(ref[stat])
                    if not lo <= ratio <= hi:
                        add(f"{col}.{stat}", ref[stat], cur[stat], f"ratio outside [{lo}, {hi}]")
        if "distribution" in cur:
            new = sorted(set(cur["distribution"]) - set(ref.get("distribution", {})))
            if new:
                add(f"{col}.values", sorted(ref.get("distribution", {})), new, "values not seen in baseline")
            elif tvd(cur["distribution"], ref.get("distribution", {})) > DISTRIBUTION_TVD:
                add(f"{col}.distribution", ref["distribution"], cur["distribution"],
                    f"total variation distance > {DISTRIBUTION_TVD}")
        if col == "transaction_date":
            if (ref.get("parse_success_rate") is not None and cur.get("parse_success_rate") is not None
                    and ref["parse_success_rate"] - cur["parse_success_rate"] > DATE_PARSE_RATE_DROP):
                add("transaction_date.parse_success_rate", ref["parse_success_rate"],
                    cur["parse_success_rate"], f"drop > {DATE_PARSE_RATE_DROP}")
            if ref.get("min") and cur.get("min") and (cur["min"] < ref["min"] or cur["max"] > ref["max"]):
                add("transaction_date.range", [ref["min"], ref["max"]], [cur["min"], cur["max"]],
                    "outside baseline date range")
            if tvd(cur.get("month_histogram", {}), ref.get("month_histogram", {})) > DISTRIBUTION_TVD:
                add("transaction_date.month_histogram", ref.get("month_histogram"),
                    cur.get("month_histogram"), f"total variation distance > {DISTRIBUTION_TVD}")
    for col in base["columns"]:
        if col not in fp["columns"]:
            add(col, "present", "absent", "column missing compared with baseline output")
    for metric in ("duplicate_key_count", "cross_field_failures"):
        if fp.get(metric, 0) > base.get(metric, 0):
            add(metric, base.get(metric), fp.get(metric), "increase vs baseline")
    return result("fail" if anomalies else "pass", anomalies=anomalies,
                  note="anomaly detector vs baseline output, not proof of correctness")


def check_determinism(out: CsvFile, base: CsvFile | None, same_input: bool) -> dict:
    if base is None:
        return not_applicable("no --baseline-output given")
    if not same_input:
        return not_applicable("input is not the baseline dataset; determinism compares runs of "
                              "the same input only")
    if not (out.readable and base.readable):
        return blocked("output or baseline output unreadable")
    raw_equal = out.raw == base.raw
    a, b = canonical_bytes(out), canonical_bytes(base)
    if a == b:
        return result("pass", byte_identical=raw_equal, data_identical=True)
    ra, rb = set(a.decode().split("\n")[1:]), set(b.decode().split("\n")[1:])
    return result("fail", byte_identical=raw_equal, data_identical=False,
                  rows_only_in_output=sample(sorted(ra - rb)),
                  rows_only_in_baseline_output=sample(sorted(rb - ra)))


# ---------------------------------------------------------------- orchestration

def validate(scenario: str, inp: CsvFile, out: CsvFile, base: CsvFile | None,
             manifest: dict | None) -> dict:
    input_sha = sha256(inp.raw)
    checks: dict[str, dict] = {}
    checks["input_contract"] = check_input_contract(inp)
    checks["schema"] = check_schema(out)

    contract_ok = checks["input_contract"]["status"] == "pass"
    out_cols = set(out.header or []) if out.readable else set()
    outcomes = cp.apply_policy(inp.dicts()) if contract_ok else None
    out_rows = out.dicts() if out.readable else []
    _, out_first, _ = output_index(out_rows) if "id" in out_cols else (None, {}, 0)
    contract_reason = ("source contract broken: "
                       + "; ".join(checks["input_contract"]["violations"])
                       + " — expectations cannot be derived safely")

    if not contract_ok:
        if inp.readable and "id" not in (inp.header or []):
            checks["deduplication"] = not_applicable("deduplication key is absent")
        else:
            checks["deduplication"] = blocked(contract_reason)
        checks["row_count_reconciliation"] = blocked(contract_reason)
    elif "id" not in out_cols:
        reason = "output unreadable" if not out.readable else "output column id is missing"
        checks["deduplication"] = blocked(reason)
        checks["row_count_reconciliation"] = blocked(reason)
    else:
        checks["deduplication"] = check_deduplication(outcomes, out_rows)
        checks["row_count_reconciliation"] = check_reconciliation(outcomes, out_rows)

    checks["manifest_consistency"] = (check_manifest(outcomes, manifest, input_sha) if contract_ok
                                      else blocked(contract_reason))

    for action in cp.ACTIONS:
        name = f"rule_{action}"
        if not contract_ok:
            checks[name] = blocked(contract_reason)
        elif "id" not in out_cols:
            checks[name] = blocked("output unreadable or output column id is missing")
        else:
            checks[name] = check_rule(action, outcomes, out, out_first)

    if not contract_ok:
        checks["values_match_policy"] = blocked(contract_reason)
    elif "id" not in out_cols:
        checks["values_match_policy"] = blocked("output unreadable or output column id is missing")
    else:
        checks["values_match_policy"] = check_values(outcomes, out, out_first)

    checks["output_format"] = (check_format(out, out_rows) if out.readable
                               else blocked("output unreadable"))

    same_input = manifest is not None and manifest.get("sha256") == input_sha
    checks["determinism"] = check_determinism(out, base, same_input)

    fp = fingerprint(out) if out.readable else None
    base_fp = fingerprint(base) if base is not None and base.readable else None
    if fp is None:
        checks["semantic_anomaly"] = blocked("output unreadable")
    elif base is not None and base_fp is None:
        checks["semantic_anomaly"] = blocked("baseline output unreadable")
    else:
        checks["semantic_anomaly"] = check_semantic(fp, base_fp)

    overall = "fail" if any(c["status"] == "fail" for c in checks.values()) else "pass"
    return {
        "scenario": scenario,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "policy": "datasets/cleaning-policy.md (approved 2026-10-03)",
        "files": {
            "input": {"path": str(inp.path), "sha256": input_sha},
            "output": {
                "path": str(out.path),
                "raw_output_sha256": sha256(out.raw),
                "canonical_data_sha256": sha256(canonical_bytes(out)) if out.readable else None,
            },
            "baseline_output": None if base is None else {
                "path": str(base.path),
                "raw_output_sha256": sha256(base.raw),
                "canonical_data_sha256": sha256(canonical_bytes(base)) if base.readable else None,
            },
            "canonicalisation": "BOM removed; cells stripped; rows sorted by integer id; "
                                "LF line endings; minimal quoting; no value reformatting",
        },
        "expected": cp.summarise(outcomes) if outcomes is not None else None,
        "checks": checks,
        "semantic_fingerprint": {"output": fp, "baseline_output": base_fp},
        "overall": overall,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a pipeline output against input + policy.")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--baseline-output", type=Path)
    parser.add_argument("--manifest", type=Path,
                        help="defaults to datasets/baseline.manifest.json (used only if its sha256 "
                             "matches the input)")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args(argv)  # argparse exits with 2 on bad invocation

    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", args.scenario):
        parser.error("--scenario must be lowercase letters, digits, '-' or '_'")

    for label, path in (("input", args.input), ("output", args.output),
                        ("baseline output", args.baseline_output), ("manifest", args.manifest)):
        if path is not None and not path.is_file():
            print(f"error: {label} file not found: {path}", file=sys.stderr)
            return EXIT_MISSING

    manifest_path = args.manifest or (DEFAULT_MANIFEST if DEFAULT_MANIFEST.is_file() else None)
    manifest = None
    if manifest_path is not None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"error: manifest is not valid JSON: {manifest_path}: {exc}", file=sys.stderr)
            return EXIT_USAGE

    report = validate(
        args.scenario,
        read_csv(args.input),
        read_csv(args.output),
        read_csv(args.baseline_output) if args.baseline_output else None,
        manifest,
    )
    try:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write report {args.report}: {exc}", file=sys.stderr)
        return EXIT_USAGE

    failed = [k for k, v in report["checks"].items() if v["status"] == "fail"]
    print(f"{args.scenario}: overall={report['overall']}"
          + (f" failed={failed}" if failed else "") + f" report={args.report}")
    return EXIT_PASS if report["overall"] == "pass" else EXIT_FAIL


if __name__ == "__main__":
    sys.exit(main())
