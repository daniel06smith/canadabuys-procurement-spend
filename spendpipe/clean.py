"""Load and clean the CanadaBuys contract-history file.

The raw file has one row per contract *record* (the original award plus each
amendment), so 23K rows describe ~14K contracts. This module:

1. loads only the columns we need (no contact-person PII),
2. normalises dates, numbers, locations and a few categorical fields,
3. flags data-quality problems instead of silently dropping rows,
4. collapses the amendment history to one row per contract.
"""
from __future__ import annotations

import re
import unicodedata

import numpy as np
import pandas as pd

from . import config as C


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------
def load_raw(path: str) -> pd.DataFrame:
    """Read the CSV, keep only the configured English columns, rename them."""
    header = pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
    missing = [c for c in C.COLUMNS.values() if c not in header]
    if missing:
        raise ValueError(
            "Source file is missing expected columns (CanadaBuys restructured "
            f"this file in 2026; check the data dictionary): {missing}"
        )
    df = pd.read_csv(
        path,
        encoding="utf-8-sig",
        dtype=str,
        usecols=list(C.COLUMNS.values()),
        keep_default_na=False,
        # only blank cells and explicit "N/A"/"NULL" markers are missing;
        # ("NA" is left alone because it is also a valid ISO country code).
        na_values=["", "N/A", "n/a", "NULL", "null"],
    )
    df = df.rename(columns={v: k for k, v in C.COLUMNS.items()})
    # Trim every text cell. This matters: 24 contract numbers appear both with
    # and without a trailing space, which would otherwise count the same
    # contract twice (about $5.1B of double-counted value in this file).
    cn = df["contract_number"]
    trimmed_rows = int((cn.notna() & (cn != cn.str.strip())).sum())
    keys_before = cn.nunique()
    for col in df.columns:
        df[col] = df[col].str.strip()
    df.attrs["contract_number_rows_trimmed"] = trimmed_rows
    df.attrs["contract_number_duplicates_merged"] = int(keys_before - df["contract_number"].nunique())
    return df


# --------------------------------------------------------------------------
# Small helpers (unit-tested)
# --------------------------------------------------------------------------
def split_multi(value) -> list[str]:
    """Split a CanadaBuys multi-value cell ('*a\\n*b') into clean items."""
    if value is None or (isinstance(value, float) and np.isnan(value)) or pd.isna(value):
        return []
    items = []
    for part in str(value).split("\n"):
        part = part.strip().lstrip("*").strip()
        if part:
            items.append(part)
    return items


def normalize_province(raw, country: str) -> str:
    """Canadian provinces -> canonical English name; foreign states unchanged."""
    if raw is None or pd.isna(raw) or not str(raw).strip():
        return "Unknown"
    text = str(raw).strip()
    if country == "Canada":
        return C.PROVINCE_MAP.get(text.upper(), C.PROVINCE_MAP.get(text, text))
    return text


def normalize_country(raw) -> str:
    if raw is None or pd.isna(raw) or not str(raw).strip():
        return "Unknown"
    text = str(raw).strip()
    return C.COUNTRY_MAP.get(text.upper(), text) if len(text) == 2 else text


def supplier_region(province: str, country: str) -> str:
    """Province for Canadian suppliers, otherwise the country."""
    if country == "Canada":
        return province if province in C.CANADIAN_PROVINCES else "Canada (province unknown)"
    return country


def size_band(raw) -> str:
    """Bucket the mixed numeric/text employee-count field into size bands."""
    if raw is None or pd.isna(raw):
        return C.UNKNOWN_SIZE
    text = str(raw).strip().lower()
    if not text or "unknown" in text:
        return C.UNKNOWN_SIZE
    if "self" in text:
        n = 1
    else:
        nums = [int(x) for x in re.findall(r"\d+", text)]
        if not nums:
            return C.UNKNOWN_SIZE
        n = nums[-1] if "over" not in text else nums[0]
        if len(nums) > 1 and "to" in text:
            n = nums[0]  # lower bound of a "X to Y employees" band
    for lo, hi, label in C.SIZE_BANDS:
        if lo <= n <= hi:
            return label
    return C.UNKNOWN_SIZE


def sourcing_type(method) -> str:
    if method is None or pd.isna(method):
        return "Not reported"
    m = str(method).lower()
    if m.startswith("competitive"):
        return "Competitive"
    if m.startswith("non-competitive"):
        return "Non-competitive"
    if "advance" in m:
        return "Advance notice (ACAN)"
    return "Other"


def value_band(v) -> str:
    if v is None or pd.isna(v) or v <= 0:
        return "0. No value / adjustment"
    for lo, hi, label in C.VALUE_BANDS:
        if lo <= v < hi:
            return label
    return "0. No value / adjustment"


def fiscal_year(ts) -> str | None:
    """Government of Canada fiscal year label, e.g. 2025-04-10 -> 'FY2025-26'."""
    if pd.isna(ts):
        return None
    start = ts.year if ts.month >= C.FISCAL_YEAR_START_MONTH else ts.year - 1
    return f"FY{start}-{str(start + 1)[-2:]}"


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


# --------------------------------------------------------------------------
# Record-level cleaning
# --------------------------------------------------------------------------
def clean_events(raw: pd.DataFrame) -> pd.DataFrame:
    """Clean every record (original + amendments). Adds flags; drops nothing."""
    df = raw.copy()

    for col in ["publication_date", "award_date", "amendment_date", "start_date", "end_date"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ["contract_amount", "total_value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Amendment sequence: '000' is the original; 'T01'/'S01' are non-numeric
    # historical codes and sort after the numbered amendments.
    seq = pd.to_numeric(df["amendment_number"], errors="coerce")
    df["amendment_seq"] = seq.fillna(1000).astype(int)

    # Placeholder / impossible end dates
    df["end_date_placeholder"] = (df["end_date"].dt.year >= C.PLACEHOLDER_END_YEAR).fillna(False)
    df.loc[df["end_date_placeholder"], "end_date"] = pd.NaT
    df["end_before_start"] = (df["end_date"] < df["start_date"]).fillna(False)

    # Locations
    df["supplier_country"] = df["supplier_country_raw"].map(normalize_country)
    df["supplier_province"] = [
        normalize_province(p, c) for p, c in zip(df["supplier_province_raw"], df["supplier_country"])
    ]
    df["supplier_region"] = [
        supplier_region(p, c) for p, c in zip(df["supplier_province"], df["supplier_country"])
    ]
    df["supplier_size_band"] = df["supplier_employee_count"].map(size_band)

    # Categorical tidy-up
    df["client_department"] = df["client_department"].replace(C.DEPARTMENT_ALIASES).fillna("Unknown")
    df["sourcing_type"] = df["procurement_method"].map(sourcing_type)
    cat = df["procurement_category"].map(lambda v: split_multi(v)[0] if split_multi(v) else None)
    df["procurement_category"] = cat.map(C.PROCUREMENT_CATEGORY_LABELS).fillna("Unknown")
    df["limited_tendering_reason"] = df["limited_tendering_reason"].map(
        lambda v: (split_multi(v) or [None])[0]
    )
    df.loc[df["limited_tendering_reason"].isin(["None"]), "limited_tendering_reason"] = np.nan
    df["delivery_region"] = df["delivery_regions"].map(lambda v: "; ".join(split_multi(v)) or None)
    df = df.drop(columns=["delivery_regions", "supplier_province_raw", "supplier_country_raw"])
    return df


# --------------------------------------------------------------------------
# Contract-level collapse
# --------------------------------------------------------------------------
def collapse_to_contracts(events: pd.DataFrame) -> pd.DataFrame:
    """One row per contract number.

    Findings from profiling the file (documented in the README):
    * ``total_value`` is identical on every record of a contract, so it is the
      contract's current cumulative value.
    * ``contract_amount`` is NOT consistent across amendments (sometimes the
      cumulative amount, sometimes the change), so it is only used from the
      original record (amendment 000) to measure value growth.
    """
    ev = events.sort_values(["contract_number", "amendment_seq", "publication_date"], kind="stable")
    g = ev.groupby("contract_number", sort=False)

    # Descriptive attributes: last non-null value across the record history
    # (fills gaps where a later record omits a field the earlier one had).
    attr_cols = [
        "title", "solicitation_number", "currency", "status", "instrument_type",
        "gsin_desc", "unspsc", "procurement_category", "procurement_method",
        "sourcing_type", "limited_tendering_reason", "delivery_region",
        "supplier_legal_name", "supplier_standardized_name", "supplier_city",
        "supplier_country", "supplier_province", "supplier_region",
        "supplier_size_band", "client_department", "total_value",
    ]
    contracts = g[attr_cols].last()

    first_row = ev.drop_duplicates("contract_number", keep="first").set_index("contract_number")
    latest_row = ev.drop_duplicates("contract_number", keep="last").set_index("contract_number")
    first_row = first_row.reindex(contracts.index)
    latest_row = latest_row.reindex(contracts.index)

    # Current contract term = the latest record's dates
    for col in ["start_date", "end_date", "end_date_placeholder", "end_before_start"]:
        contracts[col] = latest_row[col]
    contracts["end_date_placeholder"] = g["end_date_placeholder"].any()

    contracts["award_date"] = g["award_date"].min()
    contracts["first_publication_date"] = g["publication_date"].min()
    contracts["last_publication_date"] = g["publication_date"].max()
    contracts["last_amendment_date"] = g["amendment_date"].max()
    contracts["n_records"] = g.size()
    contracts["n_amendments"] = g["amendment_seq"].apply(lambda s: int((s > 0).sum()))
    contracts["latest_amendment_type"] = latest_row["amendment_type"]
    contracts["has_original_record"] = first_row["amendment_seq"].eq(0)
    contracts["original_amount"] = first_row["contract_amount"].where(contracts["has_original_record"])
    contracts["final_value"] = contracts["total_value"]
    contracts = contracts.drop(columns=["total_value"])

    # Value growth after award - only where we can see the original record,
    # it had a positive amount, and the contract has been amended.
    # Standing offers / supply arrangements are excluded: their "value" is a
    # ceiling, so comparing it to a first call-up is not like-for-like.
    eligible = (
        contracts["has_original_record"]
        & (contracts["original_amount"] > 0)
        & contracts["final_value"].notna()
        & (contracts["n_amendments"] > 0)
        & contracts["instrument_type"].isin(C.GROWTH_INSTRUMENTS)
    )
    contracts["growth_eligible"] = eligible
    contracts["value_change"] = (contracts["final_value"] - contracts["original_amount"]).where(eligible)
    contracts["growth_pct"] = (contracts["value_change"] / contracts["original_amount"]).where(eligible)

    contracts["award_month"] = contracts["award_date"].dt.to_period("M").dt.to_timestamp()
    contracts["fiscal_year"] = contracts["award_date"].map(fiscal_year)
    contracts["publication_lag_days"] = (contracts["first_publication_date"] - contracts["award_date"]).dt.days
    contracts["value_class"] = np.select(
        [contracts["final_value"] > 0, contracts["final_value"] < 0],
        ["Valued", "Negative (adjustment)"],
        default="No value ($0)",
    )
    contracts["value_band"] = contracts["final_value"].map(value_band)
    return contracts.reset_index()


# --------------------------------------------------------------------------
# Data-quality exceptions
# --------------------------------------------------------------------------
def data_quality_issues(contracts: pd.DataFrame) -> pd.DataFrame:
    """Long-format list of contract-level exceptions (one row per issue)."""
    rules = {
        "Missing award date": contracts["award_date"].isna(),
        "End date is a system placeholder (>= 2060)": contracts["end_date_placeholder"],
        "End date before start date": contracts["end_before_start"],
        "Negative contract value": contracts["final_value"] < 0,
        "Zero value on a stand-alone contract": (contracts["final_value"] == 0)
        & contracts["instrument_type"].isin(["Contract", "Contract against SA", "Task Authorization Based Contract"]),
        "Award published before award date": contracts["publication_lag_days"] < 0,
        "No UNSPSC or GSIN category": contracts["unspsc"].isna() & contracts["gsin_desc"].isna(),
        "Sourcing method not reported": contracts["sourcing_type"].eq("Not reported"),
        "Supplier province unknown (Canadian supplier)": contracts["supplier_region"].eq("Canada (province unknown)"),
        "Amended contract without original record in file": (contracts["n_amendments"] > 0)
        & ~contracts["has_original_record"],
    }
    frames = []
    for label, mask in rules.items():
        sub = contracts.loc[mask.fillna(False), ["contract_number"]].copy()
        sub["issue_type"] = label
        frames.append(sub)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["contract_number", "issue_type"])
