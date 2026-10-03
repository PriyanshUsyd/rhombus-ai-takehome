"""Reference implementation of datasets/cleaning-policy.md (approved 2026-10-03).

Given the *input* rows, compute what a policy-correct output must contain and why
each input row was kept, removed as a duplicate, or rejected. Expectations come
from the input + policy only; the platform's output is never consulted here.

Money uses Decimal; dates are parsed with explicit formats only (no inference,
no locale-dependent month names).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

COLUMNS = [
    "id", "name", "email", "country", "price", "qty", "total", "transaction_date", "status",
]
COUNTRIES = [
    "Australia", "New Zealand", "United States", "United Kingdom",
    "Canada", "India", "Singapore", "Germany",
]
STATUSES = ["completed", "pending", "refunded", "cancelled"]
CENT = Decimal("0.01")

MONTHS_FULL = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
MONTHS_ABBR = [m[:3] for m in MONTHS_FULL]

# Policy: exactly one @, text before it, a domain containing a dot after it.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Rejection reasons, in the order they are evaluated (first match is the primary reason).
REJECT_REASONS = [
    "id_missing", "id_invalid",
    "price_missing", "price_non_numeric",
    "qty_missing", "qty_not_whole", "qty_non_positive",
    "date_missing", "date_impossible", "date_ambiguous", "date_unrecognised",
    "total_non_numeric", "total_mismatch",
]
# Repair / null actions, keyed by the column they change.
ACTIONS = {
    "name_normalised": "name",
    "name_missing_kept_null": "name",
    "email_normalised": "email",
    "email_invalid_to_null": "email",
    "email_missing_kept_null": "email",
    "country_normalised": "country",
    "country_unknown_to_null": "country",
    "country_missing_kept_null": "country",
    "status_normalised": "status",
    "status_unknown_to_null": "status",
    "status_missing_kept_null": "status",
    "price_symbol_stripped": "price",
    "date_reformatted": "transaction_date",
    "total_filled": "total",
}


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def parse_decimal(text: str) -> Decimal | None:
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def parse_date(text: str) -> tuple[date | None, str | None]:
    """Parse with the policy's explicit formats. Returns (date, None) or (None, reason)."""

    def build(y: str, m: int, d: str) -> tuple[date | None, str | None]:
        try:
            return date(int(y), m, int(d)), None
        except ValueError:
            return None, "date_impossible"

    if m := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text):        # 2025-03-07
        return build(m[1], int(m[2]), m[3])
    if m := re.fullmatch(r"(\d{4})/(\d{2})/(\d{2})", text):        # 2025/03/07
        return build(m[1], int(m[2]), m[3])
    if m := re.fullmatch(r"(\d{1,2}) ([A-Za-z]{3}) (\d{4})", text):  # 07 Mar 2025
        mon = m[2].lower()
        if mon not in MONTHS_ABBR:
            return None, "date_unrecognised"
        return build(m[3], MONTHS_ABBR.index(mon) + 1, m[1])
    if m := re.fullmatch(r"([A-Za-z]+) (\d{1,2}), (\d{4})", text):  # March 07, 2025
        mon = m[1].lower()
        if mon not in MONTHS_FULL:
            return None, "date_unrecognised"
        return build(m[3], MONTHS_FULL.index(mon) + 1, m[2])
    if m := re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", text):    # 25/03/2025 (DD/MM only)
        first, second = int(m[1]), int(m[2])
        if first <= 12 and second <= 12:
            return None, "date_ambiguous"
        if first <= 12:  # looks like MM/DD/YYYY, which the policy does not accept
            return None, "date_unrecognised"
        return build(m[3], second, m[1])
    return None, "date_unrecognised"


@dataclass
class RowOutcome:
    line: int                      # 1-based data row number in the input file
    raw: dict[str, str]
    id: str | None = None          # canonical id (str of int) when valid
    outcome: str = "kept"          # kept | duplicate | rejected
    duplicate_kind: str | None = None   # exact | near | conflicting
    reject_reasons: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    expected: dict[str, str] | None = None   # expected output record when kept
    values: dict[str, str] = field(default_factory=dict, repr=False)  # normalised values

    @property
    def primary_reason(self) -> str | None:
        return self.reject_reasons[0] if self.reject_reasons else None


def _normalise(raw: dict[str, str]) -> tuple[dict, list[str], list[str]]:
    """Steps 1-2 (+ the per-row parts of 4-5). Returns (values, reject_reasons, actions)."""
    v = {c: raw.get(c, "").strip() for c in COLUMNS}
    reasons: list[str] = []
    actions: list[str] = []
    out: dict = {}

    # id (dedup key) — policy gap: a missing/non-integer id cannot be deduplicated, so it is rejected.
    if v["id"] == "":
        reasons.append("id_missing")
    elif not re.fullmatch(r"\d+", v["id"]):
        reasons.append("id_invalid")
    else:
        out["id"] = str(int(v["id"]))

    name = " ".join(v["name"].split()).title()
    if name == "":
        actions.append("name_missing_kept_null")
    elif name != raw.get("name", ""):
        actions.append("name_normalised")
    out["name"] = name

    email = v["email"].lower()
    if email == "":
        actions.append("email_missing_kept_null")
    elif not EMAIL_RE.match(email):
        actions.append("email_invalid_to_null")
        email = ""
    elif email != raw.get("email", ""):
        actions.append("email_normalised")
    out["email"] = email

    country = next((c for c in COUNTRIES if c.casefold() == v["country"].casefold()), "")
    if v["country"] == "":
        actions.append("country_missing_kept_null")
    elif country == "":
        actions.append("country_unknown_to_null")
    elif country != raw.get("country", ""):
        actions.append("country_normalised")
    out["country"] = country

    status = v["status"].lower()
    if v["status"] == "":
        actions.append("status_missing_kept_null")
    elif status not in STATUSES:
        actions.append("status_unknown_to_null")
        status = ""
    elif status != raw.get("status", ""):
        actions.append("status_normalised")
    out["status"] = status

    price_text = v["price"]
    if price_text.startswith("$"):
        price_text = price_text[1:]
        actions.append("price_symbol_stripped")
    price = parse_decimal(price_text) if price_text else None
    if v["price"] == "":
        reasons.append("price_missing")
    elif price is None:
        reasons.append("price_non_numeric")

    qty = None
    if v["qty"] == "":
        reasons.append("qty_missing")
    else:
        q = parse_decimal(v["qty"])
        if q is None or q != q.to_integral_value():
            reasons.append("qty_not_whole")
        elif q <= 0:
            reasons.append("qty_non_positive")
        else:
            qty = int(q)

    if v["transaction_date"] == "":
        reasons.append("date_missing")
    else:
        d, why = parse_date(v["transaction_date"])
        if d is None:
            reasons.append(why)
        else:
            out["transaction_date"] = d.isoformat()
            if out["transaction_date"] != raw.get("transaction_date", ""):
                actions.append("date_reformatted")

    if price is not None and qty is not None:
        expected_total = (price * qty).quantize(CENT, rounding=ROUND_HALF_UP)
        out["price"], out["qty"] = money(price), str(qty)
        if v["total"] == "":
            actions.append("total_filled")
            out["total"] = money(expected_total)
        else:
            total = parse_decimal(v["total"])
            if total is None:
                reasons.append("total_non_numeric")
            elif total != expected_total:
                reasons.append("total_mismatch")
            else:
                out["total"] = money(total)
    elif v["total"] != "" and parse_decimal(v["total"]) is None:
        reasons.append("total_non_numeric")

    reasons.sort(key=REJECT_REASONS.index)
    return out, reasons, actions


def apply_policy(rows: list[dict[str, str]]) -> list[RowOutcome]:
    """Apply the policy to input rows (dicts keyed by the 9 contract columns)."""
    outcomes: list[RowOutcome] = []
    first_by_id: dict[str, RowOutcome] = {}
    for line, raw in enumerate(rows, start=1):
        values, reasons, actions = _normalise(raw)
        o = RowOutcome(line=line, raw=raw, id=values.get("id"), actions=actions, values=values)
        if o.id is None:  # cannot take part in dedup
            o.outcome, o.reject_reasons = "rejected", reasons
            outcomes.append(o)
            continue
        first = first_by_id.get(o.id)
        if first is not None:  # step 3: first occurrence in file order survives
            o.outcome = "duplicate"
            if raw == first.raw:
                o.duplicate_kind = "exact"
            elif values == first.values:
                o.duplicate_kind = "near"
            else:
                o.duplicate_kind = "conflicting"
            o.actions = []
            outcomes.append(o)
            continue
        first_by_id[o.id] = o
        if reasons:  # step 4
            o.outcome, o.reject_reasons = "rejected", reasons
            o.actions = []
        else:
            o.expected = {c: values.get(c, "") for c in COLUMNS}
        outcomes.append(o)
    return outcomes


def summarise(outcomes: list[RowOutcome]) -> dict:
    kept = [o for o in outcomes if o.outcome == "kept"]
    summary = {
        "input_rows": len(outcomes),
        "duplicates_removed": sum(o.outcome == "duplicate" for o in outcomes),
        "rejected": sum(o.outcome == "rejected" for o in outcomes),
        "expected_output_rows": len(kept),
        "kept_unchanged": sum(not o.actions for o in kept),
        "kept_with_null": sum(any(a.endswith("_null") for a in o.actions) for o in kept),
        "kept_repaired_only": sum(bool(o.actions) and not any(a.endswith("_null") for a in o.actions)
                                  for o in kept),
    }
    return summary
