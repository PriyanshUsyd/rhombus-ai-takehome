"""Generate the synthetic baseline dataset, the drifted datasets, and their manifests.

Deterministic: the same seed always produces byte-identical files. No wall-clock
time, locale, or environment is read.

Every injected defect is applied to its own row (one defect per row) so each
count in the manifest is unambiguous. Exact and near duplicates are copies of
clean rows. See datasets/cleaning-policy.md for how each defect should be handled.

Each drifted file (phases 3 and 4) is derived from the baseline bytes; only the
intended change differs. Row-wise changes are applied to duplicate copies too, so
exact duplicates stay exact.

Usage:
    python scripts/generate_datasets.py [--out-dir datasets] [--seed 20261003]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

SEED = 20261003
BASE_ROWS = 234  # unique transaction ids; + 16 duplicate rows = 250 rows
FIRST_ID = 1001
CUSTOMER_COUNT = 60

COLUMNS = [
    "id", "name", "email", "country", "price", "qty", "total", "transaction_date", "status",
]

FIRST_NAMES = [
    "Alice", "Ben", "Chloe", "Daniel", "Emma", "Farah", "George", "Hana", "Isaac", "Jade",
    "Kai", "Lena", "Marco", "Nina", "Oscar", "Priya", "Quinn", "Ravi", "Sofia", "Tom",
]
LAST_NAMES = [
    "Nguyen", "Smith", "Patel", "Chen", "Brown", "Kumar", "Wilson", "Lee", "Taylor", "Singh",
    "Walker", "Khan", "Martin", "Rossi", "Silva",
]
EMAIL_DOMAINS = ["example.com", "example.org", "example.net"]  # reserved, never real
COUNTRIES = [
    "Australia", "New Zealand", "United States", "United Kingdom",
    "Canada", "India", "Singapore", "Germany",
]
STATUSES = ["completed", "pending", "refunded", "cancelled"]
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
DATE_START = date(2025, 1, 1)
DATE_DAYS = 181  # 2025-01-01 .. 2025-06-30

# (defect name, category, rows affected, description). Order is the injection order.
SINGLE_ROW_DEFECTS = [
    ("missing_name", "missing", 3, "name is empty"),
    ("missing_email", "missing", 3, "email is empty"),
    ("missing_country", "missing", 3, "country is empty"),
    ("missing_price", "missing", 2, "price is empty"),
    ("missing_qty", "missing", 2, "qty is empty"),
    ("missing_total", "missing", 3, "total is empty (price and qty present)"),
    ("missing_transaction_date", "missing", 2, "transaction_date is empty"),
    ("missing_status", "missing", 3, "status is empty"),
    ("name_casing_whitespace", "formatting", 5,
     "name has wrong casing and/or leading/trailing/double spaces"),
    ("country_casing_whitespace", "formatting", 5,
     "country is a valid country with wrong casing and/or surrounding spaces"),
    ("status_casing_whitespace", "formatting", 5,
     "status is a valid status with wrong casing and/or surrounding spaces"),
    ("price_currency_symbol", "formatting", 3, "price has a leading '$'"),
    ("date_format_d_mon_yyyy", "formatting", 2, "date written as e.g. '07 Mar 2025'"),
    ("date_format_month_d_yyyy", "formatting", 2, "date written as e.g. 'March 07, 2025'"),
    ("date_format_yyyy_slash", "formatting", 2, "date written as e.g. '2025/03/07'"),
    ("date_format_dd_mm_yyyy", "formatting", 2,
     "date written as DD/MM/YYYY with day > 12 (unambiguous), e.g. '25/03/2025'"),
    ("email_case_whitespace_variant", "formatting", 6,
     ("distinct transaction whose email differs from the same customer's email elsewhere "
      "only by case/whitespace; NOT a duplicate")),
    ("email_malformed", "invalid", 3, "email is not a valid address (missing local part, @ or domain)"),
    ("price_non_numeric", "invalid", 2, "price is non-numeric text"),
    ("qty_non_positive", "invalid", 3, "qty is zero or negative"),
    ("date_impossible", "invalid", 2, "ISO-shaped date that does not exist"),
    ("status_unknown", "invalid", 2, "status not in the allowed set"),
    ("country_unknown", "invalid", 2, "country not in the allowed set"),
    ("total_mismatch", "invalid", 3, "total != price * qty"),
]
EXACT_DUPLICATES = 10
NEAR_DUPLICATES = 6


def money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def email_variant(email: str, k: int) -> str:
    """Return a case/whitespace variant of a lowercase email that is never equal to it."""
    local, domain = email.split("@")
    variants = [
        email.upper(),
        f" {email}",
        f"{email} ",
        f"{local.title()}@{domain}",
        f" {local.title()}@{domain.upper()} ",
        f"{local}@{domain.upper()}",
    ]
    return variants[k % len(variants)]


def build_customers(rng: random.Random) -> list[dict]:
    pairs = [(f, last) for f in FIRST_NAMES for last in LAST_NAMES]
    rng.shuffle(pairs)
    customers = []
    for first, last in pairs[:CUSTOMER_COUNT]:
        customers.append({
            "name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}@{rng.choice(EMAIL_DOMAINS)}",
            "country": rng.choice(COUNTRIES),
        })
    return customers


def build_clean_rows(rng: random.Random, customers: list[dict]) -> list[dict]:
    rows = []
    for i in range(BASE_ROWS):
        cust = rng.choice(customers)
        price = Decimal(rng.randint(500, 50000)) / 100
        qty = rng.randint(1, 10)
        d = DATE_START + timedelta(days=rng.randrange(DATE_DAYS))
        rows.append({
            "id": str(FIRST_ID + i),
            "name": cust["name"],
            "email": cust["email"],
            "country": cust["country"],
            "price": money(price),
            "qty": str(qty),
            "total": money(price * qty),
            "transaction_date": d.isoformat(),
            "status": rng.choice(STATUSES),
            "_date": d,
        })
    return rows


def apply_defect(name: str, row: dict, k: int) -> None:
    d: date = row["_date"]
    if name.startswith("missing_"):
        row[name.removeprefix("missing_")] = ""
    elif name == "name_casing_whitespace":
        first, last = row["name"].split(" ")
        row["name"] = [
            f"  {row['name'].lower()}", f"{row['name'].upper()} ", f"{first}  {last}",
            f" {first.lower()} {last.upper()}", f"{row['name'].lower()}   ",
        ][k % 5]
    elif name == "country_casing_whitespace":
        c = row["country"]
        row["country"] = [c.lower(), c.upper(), f" {c} ", f"{c.lower()} ", f"  {c.upper()}"][k % 5]
    elif name == "status_casing_whitespace":
        s = row["status"]
        row["status"] = [s.upper(), s.title(), f" {s}", f"{s.upper()} ", f" {s.title()} "][k % 5]
    elif name == "price_currency_symbol":
        row["price"] = "$" + row["price"]
    elif name == "date_format_d_mon_yyyy":
        row["transaction_date"] = f"{d.day:02d} {MONTHS[d.month - 1][:3]} {d.year}"
    elif name == "date_format_month_d_yyyy":
        row["transaction_date"] = f"{MONTHS[d.month - 1]} {d.day:02d}, {d.year}"
    elif name == "date_format_yyyy_slash":
        row["transaction_date"] = f"{d.year}/{d.month:02d}/{d.day:02d}"
    elif name == "date_format_dd_mm_yyyy":
        row["transaction_date"] = f"{d.day:02d}/{d.month:02d}/{d.year}"
    elif name == "email_case_whitespace_variant":
        row["email"] = email_variant(row["email"], k)
    elif name == "email_malformed":
        local, domain = row["email"].split("@")
        row["email"] = [f"{local}.{domain}", f"{local}@", f"@{domain}"][k % 3]
    elif name == "price_non_numeric":
        row["price"] = ["abc", "ten"][k % 2]
    elif name == "qty_non_positive":
        row["qty"] = ["0", "-1", "-3"][k % 3]
    elif name == "date_impossible":
        row["transaction_date"] = ["2025-02-30", "2025-13-05"][k % 2]
    elif name == "status_unknown":
        row["status"] = ["unknown", "lost"][k % 2]
    elif name == "country_unknown":
        row["country"] = ["Atlantis", "Narnia"][k % 2]
    elif name == "total_mismatch":
        row["total"] = money(Decimal(row["total"]) + Decimal("10.00"))
    else:  # pragma: no cover - guarded by SINGLE_ROW_DEFECTS
        raise ValueError(name)


def eligible(name: str, row: dict, email_counts: dict[str, int]) -> bool:
    if name == "date_format_dd_mm_yyyy":
        return row["_date"].day > 12
    if name == "email_case_whitespace_variant":
        # The same customer must also appear elsewhere with the canonical email.
        return email_counts[row["email"]] >= 2
    return True


def generate(seed: int = SEED) -> tuple[bytes, dict]:
    """Return (csv_bytes, manifest_without_file_fields)."""
    rng = random.Random(seed)
    customers = build_customers(rng)
    rows = build_clean_rows(rng, customers)
    email_counts: dict[str, int] = {}
    for r in rows:
        email_counts[r["email"]] = email_counts.get(r["email"], 0) + 1

    available = list(range(len(rows)))
    rng.shuffle(available)
    defects: dict[str, dict] = {}

    for name, category, count, description in SINGLE_ROW_DEFECTS:
        picked = []
        for idx in list(available):
            if len(picked) == count:
                break
            if eligible(name, rows[idx], email_counts):
                picked.append(idx)
                available.remove(idx)
        if len(picked) != count:
            raise RuntimeError(f"not enough eligible rows for {name}")
        for k, idx in enumerate(picked):
            apply_defect(name, rows[idx], k)
        defects[name] = {
            "category": category,
            "count": count,
            "ids": sorted(int(rows[i]["id"]) for i in picked),
            "description": description,
        }

    # Duplicates are copies of rows that carry no defect.
    exact_src = available[:EXACT_DUPLICATES]
    near_src = available[EXACT_DUPLICATES:EXACT_DUPLICATES + NEAR_DUPLICATES]
    extra = [dict(rows[i]) for i in exact_src]
    for k, i in enumerate(near_src):
        dup = dict(rows[i])
        dup["email"] = email_variant(dup["email"], k)
        extra.append(dup)
    defects["exact_duplicate"] = {
        "category": "duplicate",
        "count": EXACT_DUPLICATES,
        "ids": sorted(int(rows[i]["id"]) for i in exact_src),
        "description": "row repeated byte-for-byte (same id); the copy appears after the original",
    }
    defects["near_duplicate_email_variant"] = {
        "category": "duplicate",
        "count": NEAR_DUPLICATES,
        "ids": sorted(int(rows[i]["id"]) for i in near_src),
        "description": "row repeated with the same id and values except email differs only by "
                       "case/whitespace; the copy appears after the original",
    }

    # Insert each copy at a random position after its original.
    out = list(rows)
    for dup in extra:
        pos = next(j for j, r in enumerate(out) if r["id"] == dup["id"])
        out.insert(rng.randint(pos + 1, len(out)), dup)

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(out)
    data = buf.getvalue().encode("utf-8")

    defective = sum(d["count"] for d in defects.values() if d["category"] != "duplicate")
    manifest = {
        "dataset": "baseline.csv",
        "generator": "scripts/generate_datasets.py",
        "seed": seed,
        "columns": COLUMNS,
        "row_count": len(out),
        "unique_ids": len(rows),
        "rows_with_single_cell_defect": defective,
        "clean_unique_rows": len(rows) - defective,
        "defects": defects,
        "notes": [
            "Each defect affects its own row; no row carries two defects.",
            "Duplicate sources are clean rows.",
            "CSV: UTF-8, LF line endings, header row, empty field = missing value.",
        ],
    }
    return data, manifest


# ---------------------------------------------------------------- drifted datasets

DROPPED_COLUMN = "country"  # rule-dependent (normalise, unknown -> null); arithmetic untouched
RENAMED_COLUMN = ("transaction_date", "order_date")  # rule-dependent (reformat, reject)
TEXT_PRICE_PREFIX = "USD "  # price numeric -> text, e.g. "222.97" -> "USD 222.97"
ADDED_COLUMN = "channel"  # appended last; values derived from id, so duplicates agree
CHANNELS = ["web", "store", "app"]
COMBINED_DROPPED_COLUMN = "id"  # the dedup key
CENTS_FACTOR = Decimal(100)
ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def read_rows(data: bytes) -> tuple[list[str], list[dict]]:
    reader = csv.DictReader(io.StringIO(data.decode("utf-8"), newline=""))
    return list(reader.fieldnames or []), list(reader)


def to_csv(columns: list[str], rows: list[dict]) -> bytes:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


def numeric_price(value: str) -> Decimal | None:
    """The number in a price cell (optional leading '$'), or None if empty/non-numeric."""
    try:
        return Decimal(value.removeprefix("$")) if value else None
    except InvalidOperation:
        return None


def iso_date(value: str) -> date | None:
    if not ISO_DATE_RE.fullmatch(value):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def drop_column(columns, rows, col):
    return ([c for c in columns if c != col],
            [{k: v for k, v in r.items() if k != col} for r in rows],
            {"dropped_column": col})


def rename_column(columns, rows, old, new):
    return ([new if c == old else c for c in columns],
            [{(new if k == old else k): v for k, v in r.items()} for r in rows],
            {"renamed_column": {"from": old, "to": new}})


def price_to_text(columns, rows):
    out, changed, unchanged = [], set(), set()
    for r in rows:
        r = dict(r)
        if numeric_price(r["price"]) is None:
            unchanged.add(int(r["id"]))
        else:
            r["price"] = TEXT_PRICE_PREFIX + r["price"].removeprefix("$")
            changed.add(int(r["id"]))
        out.append(r)
    return columns, out, {
        "type_changed_column": {
            "column": "price", "from": "numeric", "to": "text",
            "rule": (f"every numeric price (with or without a leading '$') is written as "
                     f"'{TEXT_PRICE_PREFIX}<number>'; empty and already non-numeric cells "
                     "are unchanged"),
            "changed_ids": sorted(changed),
            "unchanged_ids": sorted(unchanged),
        }
    }


def add_column(columns, rows):
    out = [{**r, ADDED_COLUMN: CHANNELS[int(r["id"]) % len(CHANNELS)]} for r in rows]
    return columns + [ADDED_COLUMN], out, {
        "added_column": {"column": ADDED_COLUMN, "position": "last", "values": CHANNELS,
                         "rule": "CHANNELS[id % 3]; never empty"}
    }


def dollars_to_cents(columns, rows):
    out, price_ids, total_ids = [], set(), set()
    for r in rows:
        r = dict(r)
        p = numeric_price(r["price"])
        if p is not None:
            prefix = "$" if r["price"].startswith("$") else ""
            r["price"] = prefix + money(p * CENTS_FACTOR)
            price_ids.add(int(r["id"]))
        if r["total"]:
            r["total"] = money(Decimal(r["total"]) * CENTS_FACTOR)
            total_ids.add(int(r["id"]))
        out.append(r)
    return columns, out, {
        "factor": str(CENTS_FACTOR),
        "rule": ("numeric price and non-empty total multiplied by 100, same text format "
                 "(2 decimals, '$' kept); empty and non-numeric cells unchanged"),
        "price_changed_ids": sorted(price_ids),
        "total_changed_ids": sorted(total_ids),
    }


def swap_day_month(columns, rows):
    out, swapped, same = [], set(), set()
    for r in rows:
        r = dict(r)
        d = iso_date(r["transaction_date"])
        if d is not None and d.day <= 12:
            if d.day == d.month:
                same.add(int(r["id"]))
            else:
                r["transaction_date"] = date(d.year, d.day, d.month).isoformat()
                swapped.add(int(r["id"]))
        out.append(r)
    return columns, out, {
        "rule": ("valid ISO dates with day <= 12 become YYYY-DD-MM (day and month swapped); "
                 "dates with day > 12, non-ISO formats, impossible and empty dates unchanged"),
        "swapped_ids": sorted(swapped),
        "day_equals_month_unchanged_ids": sorted(same),
    }


def combined(columns, rows):
    details = {}
    for step in (add_column, price_to_text,
                 lambda c, r: rename_column(c, r, *RENAMED_COLUMN),
                 lambda c, r: drop_column(c, r, COMBINED_DROPPED_COLUMN)):
        columns, rows, d = step(columns, rows)
        details.update(d)
    return columns, rows, details


# file stem -> (scenario id, category, change, derive(columns, rows) -> (columns, rows, details))
DRIFT_CASES = {
    "schema_drop_column": (
        "schema-drop-column", "schema", f"column '{DROPPED_COLUMN}' removed",
        lambda c, r: drop_column(c, r, DROPPED_COLUMN)),
    "schema_rename_column": (
        "schema-rename-column", "schema",
        f"column '{RENAMED_COLUMN[0]}' renamed to '{RENAMED_COLUMN[1]}', values unchanged",
        lambda c, r: rename_column(c, r, *RENAMED_COLUMN)),
    "schema_type_change": (
        "schema-type-change", "schema", "column 'price' changed from numeric to text",
        price_to_text),
    "schema_add_column": (
        "schema-add-column", "schema", f"column '{ADDED_COLUMN}' added as the last column",
        add_column),
    "schema_combined": (
        "schema-combined", "schema",
        (f"aggressive: '{ADDED_COLUMN}' added, 'price' numeric -> text, "
         f"'{RENAMED_COLUMN[0]}' renamed to '{RENAMED_COLUMN[1]}', "
         f"dedup key '{COMBINED_DROPPED_COLUMN}' removed"),
        combined),
    "semantic_dollars_to_cents": (
        "semantic-dollars-to-cents", "semantic",
        "price and total multiplied by 100 (dollars -> cents); total = price x qty still holds",
        dollars_to_cents),
    "semantic_date_swap": (
        "semantic-date-swap", "semantic",
        "day and month swapped in valid ISO transaction_date values with day <= 12",
        swap_day_month),
}


def generate_drift(name: str, baseline: bytes, seed: int = SEED) -> tuple[bytes, dict]:
    """Return (csv_bytes, manifest_without_file_fields) for one drift case."""
    scenario, category, change, derive = DRIFT_CASES[name]
    columns, rows = read_rows(baseline)
    columns, rows, details = derive(columns, rows)
    data = to_csv(columns, rows)
    manifest = {
        "dataset": f"{name}.csv",
        "scenario": scenario,
        "category": category,
        "generator": "scripts/generate_datasets.py",
        "seed": seed,
        "derived_from": {"dataset": "baseline.csv",
                         "sha256": hashlib.sha256(baseline).hexdigest()},
        "change": change,
        "columns": columns,
        "row_count": len(rows),
        "details": details,
        "notes": [
            "Derived from baseline.csv; only the change above differs.",
            "Row-wise changes also apply to duplicate copies, so exact duplicates stay exact.",
            "CSV: UTF-8, LF line endings, header row, empty field = missing value.",
        ],
    }
    return data, manifest


def write_file(out_dir: Path, stem: str, data: bytes, manifest: dict) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"{stem}.csv"
    csv_path.write_bytes(data)
    manifest = {**manifest, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    man_path = out_dir / f"{stem}.manifest.json"
    man_path.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return csv_path, man_path


def write_drift(out_dir: Path, seed: int = SEED) -> dict[str, tuple[Path, Path]]:
    baseline, _ = generate(seed)
    return {name: write_file(out_dir, name, *generate_drift(name, baseline, seed))
            for name in DRIFT_CASES}


def write(out_dir: Path, seed: int = SEED) -> tuple[Path, Path]:
    return write_file(out_dir, "baseline", *generate(seed))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent.parent / "datasets")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    for csv_path, man_path in [write(args.out_dir, args.seed),
                               *write_drift(args.out_dir, args.seed).values()]:
        print(f"wrote {csv_path} and {man_path}")


if __name__ == "__main__":
    main()
