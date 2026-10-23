"""Supplier entity resolution.

The file has ~7,000 distinct legal names but only some rows carry the
publisher's own "standardized name". Strategy (rule-based, conservative):

1. normalise every name (accents, punctuation, '&', legal suffixes),
2. use rows that have BOTH a legal and a standardized name to learn
   legal-name -> standardized-name aliases,
3. apply those aliases to rows that only have the legal name.

No fuzzy matching: a false merge of two different companies is worse for a
concentration analysis than leaving a duplicate unmerged.
"""
from __future__ import annotations

import re
from collections import Counter

import pandas as pd

from . import config as C
from .clean import strip_accents


def normalize_name(value) -> str:
    if value is None or pd.isna(value):
        return ""
    text = strip_accents(str(value)).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    tokens = [t for t in text.split() if t not in C.LEGAL_SUFFIX_TOKENS]
    return " ".join(tokens)


def resolve_suppliers(contracts: pd.DataFrame) -> pd.DataFrame:
    """Add supplier_key (canonical id string) to the contracts frame."""
    out = contracts.copy()
    legal_key = out["supplier_legal_name"].map(normalize_name)
    std_key = out["supplier_standardized_name"].map(normalize_name)

    # legal -> standardized aliases learned from rows that have both
    pairs = Counter(
        (lk, sk) for lk, sk in zip(legal_key, std_key) if lk and sk
    )
    best: dict[str, tuple[str, int]] = {}
    for (lk, sk), n in pairs.items():
        if lk not in best or n > best[lk][1]:
            best[lk] = (sk, n)
    alias = {lk: sk for lk, (sk, _) in best.items()}

    canonical = []
    for lk, sk in zip(legal_key, std_key):
        canonical.append(sk or alias.get(lk) or lk or "UNKNOWN SUPPLIER")
    out["supplier_key"] = canonical
    out["legal_key"] = legal_key
    return out


def build_supplier_dim(contracts: pd.DataFrame) -> pd.DataFrame:
    """One row per canonical supplier with a stable integer id."""
    c = contracts

    def top(series: pd.Series):
        s = series.dropna()
        return s.mode().iloc[0] if not s.empty else None

    rows = []
    for key, grp in c.groupby("supplier_key", sort=True):
        std = grp["supplier_standardized_name"].dropna()
        display = std.mode().iloc[0] if not std.empty else grp["supplier_legal_name"].mode().iloc[0]
        rows.append(
            {
                "supplier_key": key,
                "supplier_name": display,
                "n_legal_name_variants": grp["legal_key"].nunique(),
                "country": top(grp["supplier_country"]),
                "province": top(grp["supplier_province"]),
                "region": top(grp["supplier_region"]),
                "city": top(grp["supplier_city"]),
                "size_band": top(grp["supplier_size_band"]),
            }
        )
    dim = pd.DataFrame(rows)
    dim.insert(0, "supplier_id", range(1, len(dim) + 1))
    return dim
