"""Read-only reconciliation of source job-summary rows against an exported DB snapshot.

Input CSVs have: company, job_no, job_date, lob, income, expense, profit.
No live database connection or writes. Never silently collapse duplicate keys.

Usage:
  python scripts/reconcile_profit_exports.py --source source.csv --database db.csv --output audit/reconciliation.json
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = ("company", "job_no", "job_date", "lob", "income", "expense", "profit")
AMOUNTS = ("income", "expense", "profit")


def load(path: Path) -> tuple[dict, list]:
    records = {}
    errors = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        missing = sorted(set(FIELDS) - set(reader.fieldnames or []))
        if missing:
            return {}, [{"row": 1, "error": "Missing required columns: " + ", ".join(missing)}]
        for line, raw in enumerate(reader, 2):
            try:
                key = tuple((raw[k] or "").strip() for k in FIELDS[:4])
                if any(not x for x in key):
                    raise ValueError("Missing company, job number, date or LOB")
                if key in records:
                    raise ValueError("Duplicate job key; cannot reconcile without a unique source identity")
                amounts = tuple(Decimal((raw[k] or "").strip().replace(",", "")).quantize(Decimal("0.01")) for k in AMOUNTS)
                if any(not x.is_finite() for x in amounts):
                    raise ValueError("Non-finite amount")
                if abs(amounts[0] - amounts[1] - amounts[2]) > Decimal("0.01"):
                    raise ValueError("Income minus expense does not equal profit")
                records[key] = amounts
            except (ValueError, InvalidOperation, TypeError) as exc:
                errors.append({"row": line, "error": str(exc)})
    return records, errors


def reconcile(source: Path, database: Path) -> dict:
    a, a_errors = load(source)
    b, b_errors = load(database)
    # Do not present totals as reconciled when input validation failed.
    if a_errors or b_errors:
        return {"status": "invalid_input", "source_errors": a_errors, "database_errors": b_errors,
                "warning": "No reconciliation conclusions can be drawn from invalid input."}
    missing = sorted(set(a) - set(b))
    extra = sorted(set(b) - set(a))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    def totals(records):
        return {name: str(sum((v[i] for v in records.values()), Decimal("0.00")))
                for i, name in enumerate(AMOUNTS)}
    def rows(keys, left, right=None):
        return [{"key": list(k), "source": list(map(str, left[k])) if k in left else None,
                 "database": list(map(str, right[k])) if right is not None and k in right else None}
                for k in keys]
    return {"status": "matched" if not (missing or extra or changed) else "mismatch",
            "source_count": len(a), "database_count": len(b),
            "source_totals": totals(a), "database_totals": totals(b),
            "missing_in_database": rows(missing, a, b),
            "unexpected_in_database": rows(extra, a, b),
            "amount_mismatches": rows(changed, a, b),
            "warning": "This compares supplied exports only. Verify their extraction scope and source report dates separately."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = reconcile(args.source, args.database)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    if result["status"] != "matched":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
