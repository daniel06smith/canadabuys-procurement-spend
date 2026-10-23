"""Unit tests for the cleaning, categorisation and supplier-matching logic."""
import numpy as np
import pandas as pd
import pytest

from spendpipe import categorize, clean, config as C, suppliers


# ---------------------------------------------------------------- helpers
def raw_frame(rows: list[dict]) -> pd.DataFrame:
    """Build a raw frame with every configured column (default: missing)."""
    df = pd.DataFrame(rows)
    for col in C.COLUMNS:
        if col not in df:
            df[col] = None
    return df


def contract_rows():
    base = dict(supplier_legal_name="ACME Ltd.", supplier_country_raw="CA", supplier_province_raw="ON",
                instrument_type="Contract", procurement_method="Competitive - Open bidding",
                procurement_category="*GD", client_department="Dept A", unspsc="*43211500",
                title="Laptops", currency="CAD")
    return [
        {**base, "contract_number": "C1", "amendment_number": "000", "total_value": "150000", "contract_amount": "100000",
         "award_date": "2025-04-10", "publication_date": "2025-04-20", "start_date": "2025-05-01", "end_date": "2026-05-01"},
        {**base, "contract_number": "C1", "amendment_number": "001", "total_value": "150000", "contract_amount": "50000",
         "award_date": "2025-04-10", "publication_date": "2025-09-01", "amendment_date": "2025-08-20",
         "start_date": "2025-05-01", "end_date": "2099-12-31"},
        # standing offer: value is a ceiling -> excluded from growth analysis
        {**base, "contract_number": "SO1", "amendment_number": "000", "total_value": "900000", "contract_amount": "1000",
         "instrument_type": "Standing Offer", "award_date": "2025-05-01", "publication_date": "2025-05-02"},
        {**base, "contract_number": "SO1", "amendment_number": "001", "total_value": "900000", "contract_amount": "0",
         "instrument_type": "Standing Offer", "award_date": "2025-05-01", "publication_date": "2025-06-02"},
        # only an amendment is visible (original awarded before the file starts)
        {**base, "contract_number": "C2", "amendment_number": "002", "total_value": "70000", "contract_amount": "70000",
         "award_date": "2023-01-15", "publication_date": "2025-02-01"},
    ]


# ---------------------------------------------------------------- helpers
def test_split_multi_strips_markers_and_blanks():
    assert clean.split_multi("*Software\n*Software maintenance and support\n") == ["Software", "Software maintenance and support"]
    assert clean.split_multi(None) == []
    assert clean.split_multi(np.nan) == []


@pytest.mark.parametrize("raw,country,expected", [
    ("ON", "Canada", "Ontario"), ("Québec", "Canada", "Quebec"), ("QC", "Canada", "Quebec"),
    ("Colombie-Britannique", "Canada", "British Columbia"), ("Ontario", "Canada", "Ontario"),
    ("Virginia", "United States", "Virginia"), (None, "Canada", "Unknown"),
])
def test_normalize_province(raw, country, expected):
    assert clean.normalize_province(raw, country) == expected


@pytest.mark.parametrize("raw,expected", [
    ("CA", "Canada"), ("Canada", "Canada"), ("US", "United States"), ("United States", "United States"),
    ("GB", "United Kingdom"), ("Cayman Islands", "Cayman Islands"), (None, "Unknown"),
])
def test_normalize_country(raw, expected):
    assert clean.normalize_country(raw) == expected


def test_supplier_region_uses_province_for_canada_and_country_otherwise():
    assert clean.supplier_region("Ontario", "Canada") == "Ontario"
    assert clean.supplier_region("Unknown", "Canada") == "Canada (province unknown)"
    assert clean.supplier_region("Virginia", "United States") == "United States"


@pytest.mark.parametrize("raw,expected", [
    ("20", "Small (1-99)"), ("1 to 4 employees", "Small (1-99)"), ("Self-employed", "Small (1-99)"),
    ("100 to 199 employees", "Medium (100-499)"), ("250", "Medium (100-499)"),
    ("500", "Large (500+)"), ("5000 employees and over", "Large (500+)"), ("67000", "Large (500+)"),
    ("UNKNOWN", "Unknown"), (None, "Unknown"),
])
def test_size_band(raw, expected):
    assert clean.size_band(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("Competitive - Open bidding", "Competitive"), ("Non-competitive", "Non-competitive"),
    ("Advance contract award notice", "Advance notice (ACAN)"), (None, "Not reported"),
])
def test_sourcing_type(raw, expected):
    assert clean.sourcing_type(raw) == expected


def test_fiscal_year_uses_april_start():
    assert clean.fiscal_year(pd.Timestamp("2025-03-31")) == "FY2024-25"
    assert clean.fiscal_year(pd.Timestamp("2025-04-01")) == "FY2025-26"
    assert clean.fiscal_year(pd.NaT) is None


def test_value_band_boundaries():
    assert clean.value_band(99_999) == "1. Under $100K"
    assert clean.value_band(100_000) == "2. $100K - $1M"
    assert clean.value_band(0) == "0. No value / adjustment"
    assert clean.value_band(-5) == "0. No value / adjustment"


# ---------------------------------------------------------------- loading
def test_load_raw_trims_whitespace_and_merges_duplicate_contract_numbers(tmp_path):
    cols = list(C.COLUMNS.values())
    row = {c: "" for c in cols}
    a = {**row, C.COLUMNS["contract_number"]: "W1-23/001/AB ", C.COLUMNS["total_value"]: "100", C.COLUMNS["supplier_country_raw"]: "N/A"}
    b = {**row, C.COLUMNS["contract_number"]: "W1-23/001/AB", C.COLUMNS["total_value"]: "100"}
    path = tmp_path / "raw.csv"
    pd.DataFrame([a, b], columns=cols).to_csv(path, index=False, encoding="utf-8-sig")
    df = clean.load_raw(str(path))
    assert df["contract_number"].nunique() == 1
    assert df.attrs["contract_number_rows_trimmed"] == 1
    assert df.attrs["contract_number_duplicates_merged"] == 1
    assert df["supplier_country_raw"].isna().all()  # "N/A" is treated as missing


def test_load_raw_reports_missing_columns(tmp_path):
    path = tmp_path / "bad.csv"
    pd.DataFrame({"title-titre-eng": ["x"]}).to_csv(path, index=False)
    with pytest.raises(ValueError, match="missing expected columns"):
        clean.load_raw(str(path))


# ---------------------------------------------------------------- cleaning + collapse
def build_contracts():
    ev = clean.clean_events(raw_frame(contract_rows()))
    return ev, clean.collapse_to_contracts(ev)


def test_collapse_returns_one_row_per_contract():
    ev, ct = build_contracts()
    assert len(ev) == 5 and len(ct) == 3
    assert ct["contract_number"].is_unique


def test_final_value_is_not_double_counted_across_amendments():
    _, ct = build_contracts()
    c1 = ct.set_index("contract_number").loc["C1"]
    assert c1["final_value"] == 150_000
    assert c1["n_records"] == 2 and c1["n_amendments"] == 1


def test_value_growth_uses_original_record_only():
    _, ct = build_contracts()
    c1 = ct.set_index("contract_number").loc["C1"]
    assert c1["growth_eligible"]
    assert c1["original_amount"] == 100_000
    assert c1["value_change"] == 50_000
    assert c1["growth_pct"] == pytest.approx(0.5)


def test_standing_offers_and_missing_originals_are_excluded_from_growth():
    _, ct = build_contracts()
    ct = ct.set_index("contract_number")
    assert not ct.loc["SO1", "growth_eligible"]            # ceiling value, not a firm award
    assert not ct.loc["C2", "has_original_record"]        # first visible record is amendment 002
    assert not ct.loc["C2", "growth_eligible"]
    assert np.isnan(ct.loc["C2", "growth_pct"])


def test_placeholder_end_date_is_flagged_and_blanked():
    ev, ct = build_contracts()
    assert ev["end_date_placeholder"].sum() == 1
    assert pd.isna(ev.loc[ev["end_date_placeholder"], "end_date"]).all()
    assert ct.set_index("contract_number").loc["C1", "end_date_placeholder"]


def test_award_month_and_fiscal_year():
    _, ct = build_contracts()
    c1 = ct.set_index("contract_number").loc["C1"]
    assert c1["award_month"] == pd.Timestamp("2025-04-01")
    assert c1["fiscal_year"] == "FY2025-26"


def test_data_quality_flags_amended_contract_without_original():
    _, ct = build_contracts()
    ct = categorize.add_categories(ct)
    dq = clean.data_quality_issues(ct)
    flagged = dq[dq["issue_type"] == "Amended contract without original record in file"]["contract_number"].tolist()
    assert flagged == ["C2"]


# ---------------------------------------------------------------- categorisation
def test_parse_unspsc_handles_multi_value_cells():
    assert categorize.parse_unspsc("*10120000\n*10121500") == ["10120000", "10121500"]
    assert categorize.parse_unspsc(None) == []


def test_category_from_code_segment_and_family_override():
    assert categorize.category_from_code("43211500") == "IT Hardware, Software & Telecom"
    assert categorize.category_from_code("81111800") == "IT Services & Software Support"   # family 8111
    assert categorize.category_from_code("81101500") == "Engineering, Research & Technical Services"
    assert categorize.category_from_code("25101500") == "Vehicles, Ships & Aircraft"
    assert categorize.category_from_code("99999999") is None


def test_categorize_prefers_unspsc_over_text():
    cat, method, code = categorize.categorize("*43211500", "Language Interpretation Services", "x")
    assert (cat, method, code) == ("IT Hardware, Software & Telecom", "UNSPSC", "43211500")


def test_categorize_falls_back_to_gsin_description_not_supplier_name():
    cat, method, _ = categorize.categorize(None, "*Translation Services", "MARINE CONSULTING INC (W1)")
    assert (cat, method) == ("Professional & Business Services", "Keyword fallback")
    # a GSIN description with no keyword match stays unclassified: the supplier name is ignored
    cat, method, _ = categorize.categorize(None, "*Zzz Widgets", "MARINE CONSULTING INC (W1)")
    assert (cat, method) == (C.UNCLASSIFIED, "Unclassified")


def test_categorize_uses_title_only_when_no_gsin():
    cat, method, _ = categorize.categorize(None, None, "Modular Storage Sheds")
    assert cat == "Facilities, Construction & Environmental" and method == "Keyword fallback"


def test_every_mapped_segment_has_a_name_and_a_known_category():
    for seg in C.SEGMENT_TO_CATEGORY:
        assert seg in C.SEGMENT_NAMES, seg
    assert len(set(C.SEGMENT_TO_CATEGORY.values()) | set(C.FAMILY_TO_CATEGORY.values())) == 14


# ---------------------------------------------------------------- suppliers
@pytest.mark.parametrize("a,b", [
    ("Acme Inc.", "ACME INCORPORATED"), ("Bell Textron Canada limitée", "BELL TEXTRON CANADA LIMITEE"),
    ("R&R International", "R AND R INTERNATIONAL"), ("Café  Soleil Ltd", "CAFE SOLEIL LTEE"),
])
def test_normalize_name_collapses_cosmetic_differences(a, b):
    assert suppliers.normalize_name(a) == suppliers.normalize_name(b)


def test_normalize_name_keeps_distinct_companies_apart():
    assert suppliers.normalize_name("9071-4290 Quebec Inc") != suppliers.normalize_name("9071-4291 Quebec Inc")
    assert suppliers.normalize_name("MDA") != suppliers.normalize_name("MDA Systems")


def test_resolve_suppliers_learns_aliases_from_standardized_names():
    df = pd.DataFrame({
        "supplier_legal_name": ["Bell Textron Canada Limited", "BELL TEXTRON CANADA LTD", "Other Co"],
        "supplier_standardized_name": ["BELL HELICOPTER TEXTRON CANADA", None, None],
    })
    out = suppliers.resolve_suppliers(df)
    # row 1 has no standardized name, but its legal name matches row 0's alias
    assert out["supplier_key"].iloc[0] == out["supplier_key"].iloc[1]
    assert out["supplier_key"].iloc[2] == "OTHER"  # "Co" is a legal-form suffix and is stripped
