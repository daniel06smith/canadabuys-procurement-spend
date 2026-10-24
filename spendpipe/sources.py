"""Read the CanadaBuys source files for exploration (EDA notebooks).

Every notebook loads data through this module, so all of them see the same
columns, the same missing-value markers and the same whitespace trimming.

* Files are found in data/raw by a fragment of their name, so a browser's
  "file(1).csv" still resolves.
* Only the columns listed below are read. Contact names, e-mails, phones,
  street addresses and postal codes are never loaded (``assert_no_contact_columns``).
* Values stay as trimmed strings (the raw layer); ``parse_types`` converts
  dates and numbers when a notebook needs them.
* The first read of a CSV is cached as Parquet in data/interim, so later
  loads take about a second instead of up to a minute. The cache is rebuilt
  whenever the CSV is newer or the column list changed.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

RAW_DIR = Path("data/raw")
CACHE_DIR = Path("data/interim")
NA_MARKERS = ["", "N/A", "n/a", "NULL", "null"]   # same as the v1 loader

# label -> fragment of the file name (case-insensitive)
SOURCES = {
    "contracts_current": "contractHistoryComplete",
    "contracts_legacy": "contractHistoryHistorical",
    "tenders_current": "tenderNoticeComplete",
    "tenders_legacy": "tenderNoticeHistorical",
}

CONTRACT_COLUMNS = {
    "title": "title-titre-eng",
    "reference_number": "referenceNumber-numeroReference",
    "amendment_number": "amendmentNumber-numeroModification",
    "procurement_number": "procurementNumber-numeroApprovisionnement",
    "solicitation_number": "solicitationNumber-numeroSollicitation",
    "contract_number": "contractNumber-numeroContrat",
    "number_of_records": "numberOfRecords-nombreEnregistrements",
    "publication_date": "publicationDate-datePublication",
    "award_date": "contractAwardDate-dateAttributionContrat",
    "amendment_date": "amendmentDate-dateModification",
    "start_date": "contractStartDate-contratDateDebut",
    "end_date": "contractEndDate-dateFinContrat",
    "contract_amount": "contractAmount-montantContrat",
    "total_value": "totalContractValue-valeurTotaleContrat",
    "status": "contractStatus-statutContrat-eng",
    "instrument_type": "instrumentType-typeInstrument-eng",
    "amendment_type": "amendmentType-typeModification-eng",
    "gsin": "gsin-nibs",
    "gsin_desc": "gsinDescription-nibsDescription-eng",
    "unspsc": "unspsc",
    "unspsc_desc": "unspscDescription-eng",
    "procurement_category": "procurementCategory-categorieApprovisionnement",
    "notice_type": "noticeType-avisType-eng",
    "procurement_method": "procurementMethod-methodeApprovisionnement-eng",
    "selection_criteria": "selectionCriteria-criteresSelection-eng",
    "limited_tendering_reason": "limitedTenderingReason-raisonAppelOffresLimite-eng",
    "supplier_legal_name": "supplierLegalName-nomLegalFournisseur-eng",
    "supplier_standardized_name": "supplierStandardizedName-nomNormaliseFournisseur-eng",
    "supplier_operating_name": "supplierOperatingName-nomCommercialFournisseur-eng",
    "supplier_employee_count": "supplierEmployeeCount-fournisseurNombreEmployes-eng",
    "supplier_province": "supplierAddressProvince-fournisseurAdresseProvince-eng",
    "supplier_country": "supplierAddressCountry-fournisseurAdressePays-eng",
    "contracting_entity": "contractingEntityName-nomEntitContractante-eng",
    "client_department": "endUserEntitiesName-nomEntitesUtilisateurFinal-eng",
}

TENDER_COLUMNS = {
    "title": "title-titre-eng",
    "reference_number": "referenceNumber-numeroReference",
    "amendment_number": "amendmentNumber-numeroModification",
    "solicitation_number": "solicitationNumber-numeroSollicitation",
    "publication_date": "publicationDate-datePublication",
    "closing_date": "tenderClosingDate-appelOffresDateCloture",
    "amendment_date": "amendmentDate-dateModification",
    "expected_start_date": "expectedContractStartDate-dateDebutContratPrevue",
    "expected_end_date": "expectedContractEndDate-dateFinContratPrevue",
    "tender_status": "tenderStatus-appelOffresStatut-eng",
    "gsin": "gsin-nibs",
    "unspsc": "unspsc",
    "procurement_category": "procurementCategory-categorieApprovisionnement",
    "notice_type": "noticeType-avisType-eng",
    "procurement_method": "procurementMethod-methodeApprovisionnement-eng",
    "selection_criteria": "selectionCriteria-criteresSelection-eng",
    "limited_tendering_reason": "limitedTenderingReason-raisonAppelOffresLimite-eng",
    "contracting_entity": "contractingEntityName-nomEntitContractante-eng",
    "client_department": "endUserEntitiesName-nomEntitesUtilisateurFinal-eng",
}

DATE_COLUMNS = ["publication_date", "award_date", "amendment_date", "start_date", "end_date",
                "closing_date", "expected_start_date", "expected_end_date"]
NUMBER_COLUMNS = ["contract_amount", "total_value", "number_of_records"]

# Columns that must never be loaded: contact people, e-mail, phone, fax, street
# address and postal code (province and country of a supplier company are allowed).
_CONTACT_RE = re.compile(r"contactinfo|courriel|e-?mail|phone|fax|postal|addressline|ligneadresse|"
                         r"entitiesaddress|adresseentites|contractingentityaddress", re.IGNORECASE)

# Contracting-entity label written by the old (pre-CanadaBuys) system; see docs/project_log.md #1.
OLD_SYSTEM_ENTITY = "Public Works and Government Services Canada"


def assert_no_contact_columns(columns) -> None:
    bad = [c for c in columns if _CONTACT_RE.search(c)]
    if bad:
        raise ValueError(f"refusing to load contact/address columns: {bad}")


def find_file(label: str, raw_dir: Path | str = RAW_DIR) -> Path:
    """The one CSV in raw_dir whose name contains the label's fragment."""
    frag = SOURCES[label].lower()
    hits = [p for p in Path(raw_dir).glob("*.csv") if frag in p.name.lower()]
    if len(hits) != 1:
        raise FileNotFoundError(f"expected one file containing '{SOURCES[label]}' in {raw_dir}, found {len(hits)}: "
                                f"{[p.name for p in hits]}")
    return hits[0]


def read_csv(path: Path | str, columns: dict[str, str]) -> pd.DataFrame:
    """Read the listed columns as trimmed strings, renamed to their short names."""
    assert_no_contact_columns(columns.values())
    df = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=NA_MARKERS,
                     usecols=list(columns.values()), encoding="utf-8-sig")
    df = df[list(columns.values())]          # usecols keeps file order; reorder before renaming
    df.columns = list(columns)
    for col in df.columns:
        df[col] = df[col].str.strip()
        # a cell that was only whitespace is blank, not a value
        df.loc[df[col].eq(""), col] = pd.NA
    return df


def _cached(name: str, sources: list[Path], columns: list[str], build, cache_dir: Path | str) -> pd.DataFrame:
    cache = Path(cache_dir) / f"{name}.parquet"
    if cache.exists() and cache.stat().st_mtime >= max(p.stat().st_mtime for p in sources):
        df = pd.read_parquet(cache)
        if list(df.columns) == columns:
            return df
    df = build()
    cache.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache, index=False)
    return df


def load(label: str, raw_dir: Path | str = RAW_DIR, cache_dir: Path | str = CACHE_DIR) -> pd.DataFrame:
    """One source file as a raw string frame, plus a ``source`` column with its label."""
    path = find_file(label, raw_dir)
    cols = CONTRACT_COLUMNS if label.startswith("contracts") else TENDER_COLUMNS
    return _cached(label, [path], list(cols) + ["source"],
                   lambda: read_csv(path, cols).assign(source=label), cache_dir)


def load_yearly(raw_dir: Path | str = RAW_DIR, cache_dir: Path | str = CACHE_DIR) -> pd.DataFrame:
    """All per-fiscal-year contract files in raw_dir/yearly, with a ``source`` column holding the file name."""
    paths = sorted((Path(raw_dir) / "yearly").glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"no CSV files in {Path(raw_dir) / 'yearly'}")
    build = lambda: pd.concat([read_csv(p, CONTRACT_COLUMNS).assign(source=p.name) for p in paths],
                              ignore_index=True)
    return _cached("contracts_yearly", paths, list(CONTRACT_COLUMNS) + ["source"], build, cache_dir)


def parse_types(df: pd.DataFrame) -> pd.DataFrame:
    """Copy with known date columns as datetimes and value columns as floats."""
    out = df.copy()
    for col in DATE_COLUMNS:
        if col in out:
            out[col] = pd.to_datetime(out[col], errors="coerce", format="ISO8601")
    for col in NUMBER_COLUMNS:
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def amendment_seq(amendment_number: pd.Series) -> pd.Series:
    """Sort key: '000' -> 0, '012' -> 12; non-numeric codes such as 'T01'/'S01' sort last (1000), as in v1."""
    return pd.to_numeric(amendment_number, errors="coerce").fillna(1000).astype(int)


def first_rows(df: pd.DataFrame) -> pd.DataFrame:
    """The earliest record of each contract (its original where present), indexed by contract number."""
    ordered = df.assign(_seq=amendment_seq(df["amendment_number"])).sort_values(
        ["contract_number", "_seq"], kind="stable")
    return ordered.drop_duplicates("contract_number").drop(columns="_seq").set_index("contract_number")


def record_system(contracting_entity: pd.Series) -> pd.Series:
    """'old' for rows written by the pre-CanadaBuys system, else 'new' (by the contracting-entity label)."""
    return contracting_entity.eq(OLD_SYSTEM_ENTITY).map({True: "old", False: "new"})
