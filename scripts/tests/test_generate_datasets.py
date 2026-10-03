"""Offline tests for scripts/generate_datasets.py.

Defects are re-detected from the CSV text with rules written independently of the
generator, then compared with the manifest.
"""

import csv
import hashlib
import io
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import generate_datasets as gen

REPO = Path(__file__).resolve().parents[2]
COUNTRIES = {"Australia", "New Zealand", "United States", "United Kingdom",
             "Canada", "India", "Singapore", "Germany"}
STATUSES = {"completed", "pending", "refunded", "cancelled"}
EMAIL_RE = re.compile(r"^[a-z0-9._-]+@[a-z0-9.-]+\.[a-z]{2,}$")
ALT_DATE_FORMATS = {
    "date_format_d_mon_yyyy": "%d %b %Y",
    "date_format_month_d_yyyy": "%B %d, %Y",
    "date_format_yyyy_slash": "%Y/%m/%d",
    "date_format_dd_mm_yyyy": "%d/%m/%Y",
}


def norm(s: str) -> str:
    return " ".join(s.split())


def parses(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt).replace(tzinfo=UTC)
        return True
    except ValueError:
        return False


def decimal_or_none(value: str):
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def detect(row: dict, all_emails: list[str]) -> list[str]:
    """Return every defect name that applies to a single (non-duplicate) row."""
    found = []
    for col in gen.COLUMNS[1:]:
        if row[col] == "":
            found.append(f"missing_{col}")

    name = row["name"]
    if name and name != norm(name).title():
        found.append("name_casing_whitespace")

    country = row["country"]
    if country and country not in COUNTRIES:
        found.append("country_casing_whitespace" if norm(country).title() in COUNTRIES
                     else "country_unknown")

    status = row["status"]
    if status and status not in STATUSES:
        found.append("status_casing_whitespace" if norm(status).lower() in STATUSES
                     else "status_unknown")

    email = row["email"]
    if email:
        canon = email.strip().lower()
        if not EMAIL_RE.match(canon):
            found.append("email_malformed")
        elif email != canon:
            assert all_emails.count(canon) >= 1, f"variant {email!r} has no canonical twin"
            found.append("email_case_whitespace_variant")

    price, qty, total = row["price"], row["qty"], row["total"]
    if price.startswith("$"):
        found.append("price_currency_symbol")
        price = price[1:]
    p = decimal_or_none(price) if price else None
    if price and p is None:
        found.append("price_non_numeric")
    q = int(qty) if qty else None
    if q is not None and q <= 0:
        found.append("qty_non_positive")
    if p is not None and q is not None and q > 0 and total and Decimal(total) != p * q:
        found.append("total_mismatch")

    d = row["transaction_date"]
    if d and not parses(d, "%Y-%m-%d"):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            found.append("date_impossible")
        else:
            matches = [n for n, f in ALT_DATE_FORMATS.items() if parses(d, f)]
            assert len(matches) == 1, f"date {d!r} matches {matches}"
            if matches[0] == "date_format_dd_mm_yyyy":
                assert int(d[:2]) > 12, f"ambiguous DD/MM date {d!r}"
            found.append(matches[0])
    return found


def classify(data: bytes) -> dict[str, list[int]]:
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"), newline="")))
    seen: dict[str, dict] = {}
    canonical_emails = [r["email"] for r in rows]
    result: dict[str, list[int]] = {}

    def add(name, row_id):
        result.setdefault(name, []).append(int(row_id))

    for row in rows:
        first = seen.get(row["id"])
        if first is not None:
            if row == first:
                add("exact_duplicate", row["id"])
            else:
                assert {k: v for k, v in row.items() if k != "email"} == \
                       {k: v for k, v in first.items() if k != "email"}
                assert row["email"].strip().lower() == first["email"]
                add("near_duplicate_email_variant", row["id"])
            continue
        seen[row["id"]] = row
        found = detect(row, canonical_emails)
        assert len(found) <= 1, f"id {row['id']} has several defects: {found}"
        for name in found:
            add(name, row["id"])
    return {k: sorted(v) for k, v in result.items()}


def test_same_seed_same_bytes(tmp_path):
    a_csv, a_man = gen.write(tmp_path / "a")
    b_csv, b_man = gen.write(tmp_path / "b")
    assert a_csv.read_bytes() == b_csv.read_bytes()
    assert a_man.read_bytes() == b_man.read_bytes()


def test_different_seed_different_bytes():
    assert gen.generate(1)[0] != gen.generate(2)[0]


def test_manifest_sha_and_row_count(tmp_path):
    csv_path, man_path = gen.write(tmp_path)
    data = csv_path.read_bytes()
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(data).hexdigest()
    assert manifest["bytes"] == len(data)
    lines = data.decode("utf-8").split("\n")
    assert lines[0] == ",".join(gen.COLUMNS)
    assert lines[-1] == ""  # trailing LF, no CRLF
    assert b"\r" not in data
    assert len(lines) - 2 == manifest["row_count"] == 250


def test_manifest_defects_match_file(tmp_path):
    csv_path, man_path = gen.write(tmp_path)
    manifest = json.loads(man_path.read_text(encoding="utf-8"))
    detected = classify(csv_path.read_bytes())
    expected = {name: d["ids"] for name, d in manifest["defects"].items()}
    assert detected == expected
    for name, d in manifest["defects"].items():
        assert d["count"] == len(d["ids"]), name
    single = sum(len(v) for k, v in detected.items() if "duplicate" not in k)
    assert manifest["rows_with_single_cell_defect"] == single
    assert manifest["clean_unique_rows"] == manifest["unique_ids"] - single


def test_committed_dataset_is_reproducible():
    """datasets/baseline.* must be exactly what the generator produces (no hand edits)."""
    data, _ = gen.generate()
    assert (REPO / "datasets" / "baseline.csv").read_bytes() == data
    manifest = json.loads((REPO / "datasets" / "baseline.manifest.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == hashlib.sha256(data).hexdigest()
