"""Build the SQLite star schema, KPI views and Power BI CSV exports."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

from . import categorize, clean, config as C, suppliers

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

POWERBI_TABLES = [
    "dim_category", "dim_unspsc_segment", "dim_department", "dim_supplier",
    "dim_date", "fact_contract", "fact_contract_event", "dq_issue",
]


def _iso(series: pd.Series) -> pd.Series:
    return series.dt.strftime("%Y-%m-%d")


def prepare_tables(csv_path: str) -> tuple[dict[str, pd.DataFrame], dict]:
    """Run the whole transform and return DataFrames keyed by table name."""
    raw = clean.load_raw(csv_path)
    load_stats = dict(raw.attrs)
    n_raw_rows = len(raw)

    events = clean.clean_events(raw)
    contracts = clean.collapse_to_contracts(events)
    contracts = categorize.add_categories(contracts)
    contracts = suppliers.resolve_suppliers(contracts)
    dq = clean.data_quality_issues(contracts)

    # ---- dimensions -----------------------------------------------------
    cats = sorted(contracts["category"].unique(), key=lambda x: (x == C.UNCLASSIFIED, x))
    dim_category = pd.DataFrame({"category_id": range(1, len(cats) + 1), "category_name": cats})

    depts = sorted(contracts["client_department"].unique())
    dim_department = pd.DataFrame({"department_id": range(1, len(depts) + 1), "department_name": depts})

    dim_supplier = suppliers.build_supplier_dim(contracts)

    dim_segment = pd.DataFrame(
        [
            {"segment_code": k, "segment_name": v, "category_name": C.SEGMENT_TO_CATEGORY.get(k)}
            for k, v in sorted(C.SEGMENT_NAMES.items())
        ]
    )

    # ---- contract fact ----------------------------------------------------
    f = contracts.merge(dim_category.rename(columns={"category_name": "category"}), on="category")
    f = f.merge(dim_department.rename(columns={"department_name": "client_department"}), on="client_department")
    f = f.merge(dim_supplier[["supplier_id", "supplier_key"]], on="supplier_key")

    for col in ["award_date", "award_month", "start_date", "end_date", "first_publication_date", "last_amendment_date"]:
        f[col] = _iso(f[col])
    for col in ["multi_category", "has_original_record", "growth_eligible", "end_date_placeholder", "end_before_start"]:
        f[col] = f[col].astype(bool).astype(int)

    fact_cols = [
        "contract_number", "title", "supplier_id", "category_id", "department_id", "category_method",
        "unspsc_primary", "unspsc_segment", "multi_category", "procurement_category", "instrument_type",
        "procurement_method", "sourcing_type", "limited_tendering_reason", "status", "delivery_region",
        "award_date", "award_month", "fiscal_year", "start_date", "end_date", "first_publication_date",
        "last_amendment_date", "publication_lag_days", "n_records", "n_amendments", "has_original_record",
        "original_amount", "final_value", "value_class", "value_band", "growth_eligible", "value_change",
        "growth_pct", "end_date_placeholder", "end_before_start",
    ]
    fact_contract = f[fact_cols].copy()

    # ---- event fact ---------------------------------------------------------
    ev = events[
        ["contract_number", "amendment_number", "amendment_seq", "amendment_type", "publication_date",
         "amendment_date", "contract_amount", "total_value"]
    ].copy()
    ev["publication_date"] = _iso(ev["publication_date"])
    ev["amendment_date"] = _iso(ev["amendment_date"])

    # ---- date dimension -------------------------------------------------------
    start = pd.to_datetime(fact_contract["award_date"]).min().replace(day=1)
    end = max(pd.to_datetime(fact_contract["award_date"]).max(), contracts["last_publication_date"].max())
    days = pd.date_range(start, end, freq="D")
    dim_date = pd.DataFrame(
        {
            "date": days.strftime("%Y-%m-%d"),
            "year": days.year,
            "quarter": days.quarter,
            "month": days.month,
            "month_name": days.strftime("%b"),
            "year_month": days.strftime("%Y-%m"),
            "month_start": days.to_period("M").to_timestamp().strftime("%Y-%m-%d"),
            "fiscal_year": [clean.fiscal_year(d) for d in days],
        }
    )

    tables = {
        "dim_category": dim_category,
        "dim_unspsc_segment": dim_segment,
        "dim_department": dim_department,
        "dim_supplier": dim_supplier.drop(columns=[]),
        "dim_date": dim_date,
        "fact_contract": fact_contract,
        "fact_contract_event": ev,
        "dq_issue": dq,
    }
    stats = {
        "raw_rows": n_raw_rows,
        "contract_number_rows_trimmed": load_stats.get("contract_number_rows_trimmed", 0),
        "contract_number_duplicates_merged": load_stats.get("contract_number_duplicates_merged", 0),
        "contracts": len(fact_contract),
        "legal_names_raw": int(contracts["supplier_legal_name"].nunique()),
        "suppliers_resolved": len(dim_supplier),
        "data_through_publication": str(contracts["last_publication_date"].max().date()),
    }
    return tables, stats


def build_database(csv_path: str, db_path: str, export_dir: str | None = None) -> dict:
    tables, stats = prepare_tables(csv_path)
    db = Path(db_path)
    db.parent.mkdir(parents=True, exist_ok=True)
    if db.exists():
        db.unlink()

    con = sqlite3.connect(db)
    try:
        con.executescript((SQL_DIR / "schema.sql").read_text(encoding="utf-8"))
        # load order respects foreign keys
        for name in ["dim_category", "dim_unspsc_segment", "dim_department", "dim_supplier", "dim_date",
                     "fact_contract", "fact_contract_event", "dq_issue"]:
            tables[name].to_sql(name, con, if_exists="append", index=False)
        con.executescript((SQL_DIR / "views.sql").read_text(encoding="utf-8"))
        con.commit()
        stats.update(_summarize(con))
    finally:
        con.close()

    if export_dir:
        export_powerbi(tables, export_dir)
    Path(db.parent / "build_summary.json").write_text(json.dumps(stats, indent=2, default=str), encoding="utf-8")
    return stats


def export_powerbi(tables: dict[str, pd.DataFrame], export_dir: str) -> None:
    out = Path(export_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name in POWERBI_TABLES:
        tables[name].to_csv(out / f"{name}.csv", index=False, encoding="utf-8")


def _summarize(con: sqlite3.Connection) -> dict:
    q = lambda sql: pd.read_sql_query(sql, con)
    s = {}
    s["valued_contracts"] = int(q("SELECT COUNT(*) n FROM fact_contract WHERE final_value > 0")["n"][0])
    s["zero_value_contracts"] = int(q("SELECT COUNT(*) n FROM fact_contract WHERE final_value = 0")["n"][0])
    s["total_value_cad"] = float(q("SELECT SUM(final_value) v FROM fact_contract WHERE final_value > 0")["v"][0])
    s["award_date_min"] = q("SELECT MIN(award_date) d FROM fact_contract")["d"][0]
    s["award_date_max"] = q("SELECT MAX(award_date) d FROM fact_contract")["d"][0]
    cm = q("SELECT category_method m, COUNT(*) n, SUM(CASE WHEN final_value>0 THEN final_value ELSE 0 END) v "
           "FROM fact_contract GROUP BY 1")
    s["category_method"] = cm.set_index("m").to_dict("index")
    p = q("SELECT * FROM v_supplier_pareto")
    s["top10_supplier_share_pct"] = float(p.loc[p.supplier_rank <= 10, "share_pct"].sum())
    s["top50_supplier_share_pct"] = float(p.loc[p.supplier_rank <= 50, "share_pct"].sum())
    s["amendment_summary"] = q("SELECT * FROM v_amendment_summary").iloc[0].to_dict()
    s["dq_summary"] = q("SELECT * FROM v_dq_summary").set_index("issue_type")["n_contracts"].to_dict()
    return s
