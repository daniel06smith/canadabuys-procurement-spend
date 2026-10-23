"""Spend categorisation.

Primary method: map the contract's first UNSPSC code (UN standard
product/service taxonomy) to a business category via its 2-digit segment.
Fallback for legacy records with no UNSPSC: keyword rules on the GSIN
description and title. Anything else is "Unclassified" and is reported, not
hidden.
"""
from __future__ import annotations

import re

import pandas as pd

from . import config as C
from .clean import split_multi

_COMPILED_RULES = [(re.compile(p, re.IGNORECASE), cat) for p, cat in C.KEYWORD_RULES]


def parse_unspsc(value) -> list[str]:
    """All 8-digit UNSPSC codes in a cell, in order."""
    return [m for item in split_multi(value) for m in re.findall(r"\d{8}", item)]


def category_from_code(code: str) -> str | None:
    if not code or len(code) < 4:
        return None
    return C.FAMILY_TO_CATEGORY.get(code[:4]) or C.SEGMENT_TO_CATEGORY.get(code[:2])


def category_from_text(*texts) -> str | None:
    blob = " ".join(str(t) for t in texts if t is not None and not pd.isna(t))
    if not blob.strip():
        return None
    for pattern, category in _COMPILED_RULES:
        if pattern.search(blob):
            return category
    return None


def categorize(unspsc, gsin_desc, title) -> tuple[str, str, str | None]:
    """Return (category, method, primary_unspsc_code)."""
    codes = parse_unspsc(unspsc)
    if codes:
        cat = category_from_code(codes[0])
        if cat:
            return cat, "UNSPSC", codes[0]
        return C.UNCLASSIFIED, "UNSPSC (segment not mapped)", codes[0]
    # Legacy records: classify on the GSIN description. Their titles are just
    # "SUPPLIER NAME (contract no.)", so the title is only used when there is
    # no GSIN description at all (otherwise a supplier called "Marine ..."
    # would be classified by its name).
    has_gsin = gsin_desc is not None and not pd.isna(gsin_desc) and str(gsin_desc).strip() != ""
    cat = category_from_text(gsin_desc) if has_gsin else category_from_text(title)
    if cat:
        return cat, "Keyword fallback", None
    return C.UNCLASSIFIED, "Unclassified", None


def add_categories(contracts: pd.DataFrame) -> pd.DataFrame:
    out = contracts.copy()
    results = [
        categorize(u, g, t) for u, g, t in zip(out["unspsc"], out["gsin_desc"], out["title"])
    ]
    out["category"] = [r[0] for r in results]
    out["category_method"] = [r[1] for r in results]
    out["unspsc_primary"] = [r[2] for r in results]
    out["unspsc_segment"] = out["unspsc_primary"].str[:2]
    out["unspsc_code_count"] = out["unspsc"].map(lambda v: len(parse_unspsc(v)))
    # Several UNSPSC codes may span segments; we use the first and flag it.
    out["multi_category"] = out["unspsc"].map(
        lambda v: len({c[:2] for c in parse_unspsc(v)}) > 1
    )
    return out
