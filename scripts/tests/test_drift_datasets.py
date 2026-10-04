"""Offline tests for the drifted datasets in scripts/generate_datasets.py.

Each drifted file is compared with the baseline cell by cell: the intended change must
be present and nothing else may differ. Expectations are re-derived here, not taken
from the generator's helpers.
"""

import csv
import hashlib
import io
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import generate_datasets as gen
import pytest

REPO = Path(__file__).resolve().parents[2]
BASE_COLUMNS = ["id", "name", "email", "country", "price", "qty", "total",
                "transaction_date", "status"]
DRIFT_NAMES = [
    "schema_drop_column", "schema_rename_column", "schema_type_change", "schema_add_column",
    "schema_combined", "semantic_dollars_to_cents", "semantic_date_swap",
]


def rows_of(data: bytes) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
    return list(reader.fieldnames), list(reader)


def number(value: str):
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def valid_iso(value: str):
    try:
        return date.fromisoformat(value) if len(value) == 10 and value[4] == "-" else None
    except ValueError:
        return None


@pytest.fixture(scope="module")
def baseline():
    data, _ = gen.generate()
    return rows_of(data)[1]


@pytest.fixture(scope="module")
def drift():
    data, _ = gen.generate()
    out = {}
    for name in DRIFT_NAMES:
        csv_bytes, manifest = gen.generate_drift(name, data)
        cols, rows = rows_of(csv_bytes)
        out[name] = {"bytes": csv_bytes, "manifest": manifest, "columns": cols, "rows": rows}
    return out


def assert_unchanged_except(base_rows, rows, changed_cols, rename=None):
    """Every cell outside changed_cols equals the baseline cell (by position)."""
    rename = rename or {}
    assert len(rows) == len(base_rows) == 250
    for b, r in zip(base_rows, rows, strict=True):
        for col, value in b.items():
            if col in changed_cols:
                continue
            assert r[rename.get(col, col)] == value, (b["id"], col)


def test_all_seven_cases_exist():
    assert sorted(gen.DRIFT_CASES) == sorted(DRIFT_NAMES)


def test_same_seed_same_bytes(tmp_path):
    a = gen.write_drift(tmp_path / "a")
    b = gen.write_drift(tmp_path / "b")
    for name in DRIFT_NAMES:
        for pa, pb in zip(a[name], b[name], strict=True):
            assert pa.read_bytes() == pb.read_bytes(), name


def test_manifests_match_files(tmp_path):
    base_csv, _ = gen.write(tmp_path)
    base_sha = hashlib.sha256(base_csv.read_bytes()).hexdigest()
    for name, (csv_path, man_path) in gen.write_drift(tmp_path).items():
        data = csv_path.read_bytes()
        manifest = json.loads(man_path.read_text(encoding="utf-8"))
        cols, rows = rows_of(data)
        assert manifest["dataset"] == f"{name}.csv"
        assert manifest["scenario"] == name.replace("_", "-", 1).replace("_", "-")
        assert manifest["category"] == name.split("_")[0]
        assert manifest["sha256"] == hashlib.sha256(data).hexdigest()
        assert manifest["bytes"] == len(data)
        assert manifest["derived_from"] == {"dataset": "baseline.csv", "sha256": base_sha}
        assert manifest["columns"] == cols
        assert manifest["row_count"] == len(rows) == 250
        assert b"\r" not in data and data.endswith(b"\n")


@pytest.mark.parametrize("name", DRIFT_NAMES)
def test_committed_drift_files_are_reproducible(name):
    """datasets/<name>.* must be exactly what the generator produces (no hand edits)."""
    data, _ = gen.generate_drift(name, gen.generate()[0])
    assert (REPO / "datasets" / f"{name}.csv").read_bytes() == data
    manifest = json.loads((REPO / "datasets" / f"{name}.manifest.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- schema drift


def test_drop_column(baseline, drift):
    d = drift["schema_drop_column"]
    assert d["columns"] == [c for c in BASE_COLUMNS if c != "country"]
    assert_unchanged_except(baseline, d["rows"], {"country"})
    assert d["manifest"]["details"] == {"dropped_column": "country"}


def test_rename_column(baseline, drift):
    d = drift["schema_rename_column"]
    assert d["columns"] == [("order_date" if c == "transaction_date" else c) for c in BASE_COLUMNS]
    assert_unchanged_except(baseline, d["rows"], set(), rename={"transaction_date": "order_date"})


def expected_text_price(value: str) -> str:
    stripped = value.removeprefix("$")
    return f"USD {stripped}" if value and number(stripped) is not None else value


def test_type_change(baseline, drift):
    d = drift["schema_type_change"]
    assert d["columns"] == BASE_COLUMNS
    assert_unchanged_except(baseline, d["rows"], {"price"})
    changed = set()
    for b, r in zip(baseline, d["rows"], strict=True):
        assert r["price"] == expected_text_price(b["price"]), b["id"]
        assert r["price"] == "" or number(r["price"]) is None, f"{b['id']} price still numeric"
        if r["price"] != b["price"]:
            changed.add(int(b["id"]))
    info = d["manifest"]["details"]["type_changed_column"]
    assert info["changed_ids"] == sorted(changed)
    assert not set(info["changed_ids"]) & set(info["unchanged_ids"])


def test_add_column(baseline, drift):
    d = drift["schema_add_column"]
    assert d["columns"] == BASE_COLUMNS + ["channel"]
    assert_unchanged_except(baseline, d["rows"], set())
    by_id: dict[str, str] = {}
    for r in d["rows"]:
        assert r["channel"] in {"web", "store", "app"}
        assert by_id.setdefault(r["id"], r["channel"]) == r["channel"], "duplicates disagree"


def test_combined(baseline, drift):
    d = drift["schema_combined"]
    assert "id" not in d["columns"]
    assert "transaction_date" not in d["columns"] and "order_date" in d["columns"]
    assert d["columns"][-1] == "channel"
    assert d["columns"] == ["name", "email", "country", "price", "qty", "total",
                            "order_date", "status", "channel"]
    assert_unchanged_except(baseline, d["rows"], {"id", "price"},
                            rename={"transaction_date": "order_date"})
    for b, r in zip(baseline, d["rows"], strict=True):
        assert r["price"] == expected_text_price(b["price"]), b["id"]
    details = d["manifest"]["details"]
    assert set(details) == {"added_column", "type_changed_column", "renamed_column",
                            "dropped_column"}
    assert details["dropped_column"] == "id"


# ---------------------------------------------------------------- semantic drift


def test_dollars_to_cents(baseline, drift):
    d = drift["semantic_dollars_to_cents"]
    assert d["columns"] == BASE_COLUMNS
    assert_unchanged_except(baseline, d["rows"], {"price", "total"})
    for b, r in zip(baseline, d["rows"], strict=True):
        for col in ("price", "total"):
            prefix = "$" if b[col].startswith("$") else ""
            old = number(b[col].removeprefix(prefix)) if b[col] else None
            if old is None:
                assert r[col] == b[col], (b["id"], col)
            else:
                assert r[col].startswith(prefix)
                new = r[col].removeprefix(prefix)
                assert Decimal(new) == old * 100, (b["id"], col)
                assert len(new.split(".")[1]) == 2, "format changed"


def cross_field_holds(row) -> bool | None:
    p, q, t = number(row["price"].removeprefix("$")), number(row["qty"]), number(row["total"])
    if row["price"] == "" or row["qty"] == "" or row["total"] == "" or None in (p, q, t):
        return None
    return t == p * q


def test_dollars_to_cents_keeps_cross_field_rule(baseline, drift):
    d = drift["semantic_dollars_to_cents"]
    holds = 0
    for b, r in zip(baseline, d["rows"], strict=True):
        assert cross_field_holds(r) == cross_field_holds(b), b["id"]
        holds += cross_field_holds(r) is True
    assert holds > 200


def test_date_swap(baseline, drift):
    d = drift["semantic_date_swap"]
    assert d["columns"] == BASE_COLUMNS
    assert_unchanged_except(baseline, d["rows"], {"transaction_date"})
    swapped = set()
    for b, r in zip(baseline, d["rows"], strict=True):
        old = valid_iso(b["transaction_date"])
        if old is not None and old.day <= 12:
            new = valid_iso(r["transaction_date"])
            assert new == date(old.year, old.day, old.month), b["id"]
            if new != old:
                swapped.add(int(b["id"]))
        else:
            assert r["transaction_date"] == b["transaction_date"], b["id"]
        # Every baseline-valid date is still a valid ISO date: no new rejections.
        if old is not None:
            assert valid_iso(r["transaction_date"]) is not None, b["id"]
        assert "/" not in r["transaction_date"] or r["transaction_date"] == b["transaction_date"]
    details = d["manifest"]["details"]
    assert details["swapped_ids"] == sorted(swapped)
    assert swapped
    for i in details["day_equals_month_unchanged_ids"]:
        assert i not in swapped
