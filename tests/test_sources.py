"""Tests for the shared EDA loader."""
import os
import time

import pandas as pd
import pytest

from spendpipe import sources as S

COLS = {"contract_number": "contractNumber-numeroContrat", "total_value": "totalContractValue-valeurTotaleContrat",
        "contracting_entity": "contractingEntityName-nomEntitContractante-eng"}


def write_csv(path, rows, extra_cols=()):
    header = ["contactInfoEmail-informationsContactCourriel", *COLS.values(), *extra_cols]
    df = pd.DataFrame(rows, columns=header)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def test_contact_columns_are_refused():
    with pytest.raises(ValueError):
        S.assert_no_contact_columns(["contractNumber-numeroContrat", "contactInfoEmail-informationsContactCourriel"])
    with pytest.raises(ValueError):
        S.assert_no_contact_columns(["supplierAddressPostalCode-fournisseurAdresseCodePostal"])
    with pytest.raises(ValueError):
        S.assert_no_contact_columns(["contractingEntityAddressCity-entiteContractanteAdresseVille-eng"])
    # supplier province / country and entity names are allowed
    S.assert_no_contact_columns(list(S.CONTRACT_COLUMNS.values()) + list(S.TENDER_COLUMNS.values()))


def test_read_csv_trims_marks_missing_and_skips_unlisted_columns(tmp_path):
    p = tmp_path / "x.csv"
    write_csv(p, [["someone@example.com", "C1 ", "100", "Public Works and Government Services Canada"],
                  ["other@example.com", " C2", "N/A", "   "],
                  ["", "C3", "NULL", "Department of Public Works and Government Services (PSPC)"]])
    df = S.read_csv(p, COLS)
    assert list(df.columns) == list(COLS)                     # renamed, contact column not read
    assert df.contract_number.tolist() == ["C1", "C2", "C3"]  # trimmed
    assert df.total_value.isna().tolist() == [False, True, True]
    assert pd.isna(df.contracting_entity[1])                  # whitespace-only cell is blank


def test_read_csv_keeps_requested_order_not_file_order(tmp_path):
    p = tmp_path / "x.csv"
    write_csv(p, [["", "C1", "5", "E"]])
    reordered = {"total_value": COLS["total_value"], "contract_number": COLS["contract_number"]}
    df = S.read_csv(p, reordered)
    assert df.iloc[0].tolist() == ["5", "C1"]


def test_find_file_matches_fragment_and_rejects_ambiguity(tmp_path):
    (tmp_path / "contractHistoryComplete-contratsOctroyesComplet(1).csv").write_text("a\n")
    assert S.find_file("contracts_current", tmp_path).name.startswith("contractHistoryComplete")
    with pytest.raises(FileNotFoundError):
        S.find_file("tenders_current", tmp_path)
    (tmp_path / "contractHistoryComplete-copy.csv").write_text("a\n")
    with pytest.raises(FileNotFoundError):
        S.find_file("contracts_current", tmp_path)


def test_cache_is_used_and_rebuilt_when_source_changes(tmp_path):
    src = tmp_path / "src.csv"
    src.write_text("x\n")
    calls = []

    def build():
        calls.append(1)
        return pd.DataFrame({"a": [str(len(calls))]})

    first = S._cached("t", [src], ["a"], build, tmp_path / "cache")
    second = S._cached("t", [src], ["a"], build, tmp_path / "cache")
    assert len(calls) == 1 and second.equals(first)
    later = time.time() + 5
    os.utime(src, (later, later))                             # source is now newer than the cache
    S._cached("t", [src], ["a"], build, tmp_path / "cache")
    assert len(calls) == 2
    S._cached("t", [src], ["a", "b"], lambda: pd.DataFrame({"a": ["x"], "b": ["y"]}), tmp_path / "cache")
    assert pd.read_parquet(tmp_path / "cache" / "t.parquet").columns.tolist() == ["a", "b"]


def test_first_rows_prefers_original_and_sorts_letter_codes_last():
    df = pd.DataFrame({"contract_number": ["A", "A", "A", "B", "B"],
                       "amendment_number": ["T01", "001", "000", "S01", "002"], "x": [1, 2, 3, 4, 5]})
    f = S.first_rows(df)
    assert f.loc["A", "amendment_number"] == "000"
    assert f.loc["B", "amendment_number"] == "002"            # no original: lowest numbered amendment
    assert S.amendment_seq(pd.Series(["000", "012", "T01"])).tolist() == [0, 12, 1000]


def test_parse_types_and_record_system():
    df = pd.DataFrame({"award_date": ["2023-05-31", None], "total_value": ["1500.50", "x"],
                       "contracting_entity": [S.OLD_SYSTEM_ENTITY,
                                              "Department of Public Works and Government Services (PSPC)"]})
    t = S.parse_types(df)
    assert t.award_date[0] == pd.Timestamp("2023-05-31") and pd.isna(t.award_date[1])
    assert t.total_value[0] == 1500.5 and pd.isna(t.total_value[1])
    assert S.record_system(df.contracting_entity).tolist() == ["old", "new"]
