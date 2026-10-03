"""Generate the synthetic baseline dataset and its manifest.

Deterministic: the same seed always produces byte-identical files. No wall-clock
time, locale, or environment is read.

Every injected defect is applied to its own row (one defect per row) so each
count in the manifest is unambiguous. Exact and near duplicates are copies of
clean rows. See datasets/cleaning-policy.md for how each defect should be handled.

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
from datetime import date, timedelta
from decimal import Decimal
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


def write(out_dir: Path, seed: int = SEED) -> tuple[Path, Path]:
    data, manifest = generate(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "baseline.csv"
    csv_path.write_bytes(data)
    manifest = {**manifest, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    man_path = out_dir / "baseline.manifest.json"
    man_path.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    return csv_path, man_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent.parent / "datasets")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    csv_path, man_path = write(args.out_dir, args.seed)
    print(f"wrote {csv_path} and {man_path}")


if __name__ == "__main__":
    main()
