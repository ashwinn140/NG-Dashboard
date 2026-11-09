"""Read-only inspection of archived historical Job Profit Analysis workbooks.

Usage:
  python scripts/audit_historical_profit.py /path/to/archives --year 2024

No database writes, promotions or approval actions. Only file names, hashes,
date coverage, counts, validation issues and rounded totals are reported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.profit import is_profit_report, read_profit, validate_profit


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def inspect(root: Path, year: int) -> dict:
    results = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".xlsx", ".xlsm"}:
            continue
        try:
            if not is_profit_report(str(path)):
                continue
            report = read_profit(str(path))
            if not (report.range_from and report.range_to and
                    report.range_from.year <= year <= report.range_to.year):
                # An undated workbook is still relevant for manual investigation.
                if report.range_from is not None and report.range_to is not None:
                    continue
            issues = validate_profit(report)
            # A report spanning calendar years must not be mistaken for
            # a report containing only the requested year's jobs.
            import pandas as pd
            dates = pd.to_datetime(report.df.get("Job Date"), errors="coerce")
            year_mask = dates.dt.year.eq(year)
            year_rows = report.df.loc[year_mask]
            amounts = {}
            year_amounts = {}
            for column in ("Income (INR)", "Expense (INR)", "Profit (INR)"):
                amounts[column] = round(float(report.df[column].sum()), 2) if column in report.df else None
                year_amounts[column] = round(float(year_rows[column].sum()), 2) if column in year_rows else None
            results.append({
                "file": str(path.relative_to(root)),
                "sha256": _hash_file(path),
                "company": report.company,
                "basis": report.basis,
                "range_from": report.range_from.isoformat() if report.range_from else None,
                "range_to": report.range_to.isoformat() if report.range_to else None,
                "jobs": len(report.df),
                "jobs_in_requested_year": len(year_rows),
                "totals": amounts,
                "totals_in_requested_year": year_amounts,
                "requires_period_split": len(year_rows) != len(report.df),
                "validation_issues": issues,
                "eligible_for_manual_review": not issues,
            })
        except Exception as exc:
            results.append({"file": str(path.relative_to(root)), "error": str(exc),
                            "eligible_for_manual_review": False})
    return {"year": year, "archive": str(root), "files_inspected": len(results),
            "eligible": sum(bool(x.get("eligible_for_manual_review")) for x in results),
            "files": results,
            "warning": "Validation alone does not reconcile the imported database or authorize promotion."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.archive.is_dir():
        parser.error("archive must be an existing directory")
    result = inspect(args.archive, args.year)
    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    else:
        print(output)


if __name__ == "__main__":
    main()
