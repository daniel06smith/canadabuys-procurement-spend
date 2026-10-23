"""Command line entry point.

    python -m spendpipe build  --csv <contractHistoryComplete.csv>
    python -m spendpipe report --month 2026-03
    python -m spendpipe all    --csv <contractHistoryComplete.csv>
"""
from __future__ import annotations

import argparse
import json

DEFAULT_DB = "data/procurement.db"
DEFAULT_EXPORT = "output/powerbi"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="spendpipe", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="clean the CSV and build the SQLite database + Power BI CSVs")
    b.add_argument("--csv", required=True, help="path to the CanadaBuys contract history CSV")
    b.add_argument("--db", default=DEFAULT_DB)
    b.add_argument("--export-dir", default=DEFAULT_EXPORT)

    r = sub.add_parser("report", help="generate the monthly operating report workbook")
    r.add_argument("--db", default=DEFAULT_DB)
    r.add_argument("--month", help="YYYY-MM (default: latest settled month)")
    r.add_argument("--out", help="output .xlsx path (default: output/monthly_report_<month>.xlsx)")

    a = sub.add_parser("all", help="build, then generate the default monthly report")
    a.add_argument("--csv", required=True)
    a.add_argument("--db", default=DEFAULT_DB)
    a.add_argument("--export-dir", default=DEFAULT_EXPORT)
    a.add_argument("--month")

    args = ap.parse_args(argv)

    if args.cmd in ("build", "all"):
        from .build_db import build_database

        stats = build_database(args.csv, args.db, args.export_dir)
        print(json.dumps({k: stats[k] for k in ("raw_rows", "contracts", "suppliers_resolved", "total_value_cad")}, indent=2))
    if args.cmd in ("report", "all"):
        from .report import generate_report

        path = generate_report(args.db, getattr(args, "month", None), getattr(args, "out", None))
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
