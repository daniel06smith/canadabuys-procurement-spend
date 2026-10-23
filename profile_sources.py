#!/usr/bin/env python3
"""Profile the CanadaBuys source CSVs. Read-only: nothing in data/raw is modified.

Run from the project root, after putting the CSVs in data/raw/:

    python scripts/profile_sources.py
    python scripts/profile_sources.py --nrows 50000        # quick trial on the first 50k rows of each file
    python scripts/profile_sources.py --raw data/raw --out data/processed/profile

It writes one text report per CSV plus schema_comparison.txt into the output folder
(default data/processed/profile/) and prints a short summary. The reports are small even
when the CSVs are huge, so they can be attached to a chat.

Files expected in data/raw/ (download links are in the README):
    contractHistoryComplete-contratsOctroyesComplet.csv               contracts, Jun 2023 onwards
    2009-2023-contractHistoryHistorical-contratsOctroyesHistorique.csv   contracts, Jan 2009 - May 2023
    tenderNoticeComplete-avisAppelOffresComplet.csv                   tender notices, Aug 2022 onwards
    2009-2022-tenderNoticeHistorical-AvisAppelOffresHistorique.csv    tender notices, 2009 - Aug 2022

Privacy: contact, e-mail, phone, fax, address and postal-code columns are profiled for
completeness only. Their values are never printed (no samples, no value counts).

Needs only pandas (3.0 or newer).
"""
from __future__ import annotations

import argparse
import codecs
import re
import sys
import time
from collections import Counter
from pathlib import Path

import pandas as pd

# file-name fragment -> label used for the report name and the schema comparison
KNOWN = {
    "contractHistoryComplete": "contracts_current",
    "contractHistoryHistorical": "contracts_legacy",
    "tenderNoticeComplete": "tenders_current",
    "tenderNoticeHistorical": "tenders_legacy",
}
DOWNLOADS = {
    "contracts_current": "https://canadabuys.canada.ca/opendata/pub/contractHistoryComplete-contratsOctroyesComplet.csv",
    "contracts_legacy": "https://canadabuys.canada.ca/opendata/pub/2009-2023-contractHistoryHistorical-contratsOctroyesHistorique.csv",
    "tenders_current": "https://canadabuys.canada.ca/opendata/pub/tenderNoticeComplete-avisAppelOffresComplet.csv",
    "tenders_legacy": "https://canadabuys.canada.ca/opendata/pub/2009-2022-tenderNoticeHistorical-AvisAppelOffresHistorique.csv",
}

CHUNK = 200_000          # rows per chunk
DISTINCT_CAP = 3_000     # stop tracking distinct values of a column beyond this
CATEGORICAL_MAX = 60     # print value counts for columns with at most this many distinct values
TOP = 15                 # value-count lines per column
MARKERS = {"N/A", "n/a", "NULL", "null"}   # strings treated as missing (as in the v1 pipeline)
PLAUSIBLE_YEARS = (1990, 2059)             # dates outside this are reported as suspect/placeholder

PII_RE = re.compile(r"contactinfo|e-?mail|phone|fax|address|postal|contactname")
DATE_RE = re.compile(r"date")
NUM_RE = re.compile(r"amount|montant|value|valeur|percentage|pourcentage|numberofrecords")
KEY_RE = re.compile(r"^(contractnumber|referencenumber|solicitationnumber|procurementnumber)")


# --------------------------------------------------------------------------- per-column accumulator
class Col:
    def __init__(self, name: str):
        self.name = name
        low = name.lower()
        self.pii = bool(PII_RE.search(low))
        self.is_key = bool(KEY_RE.match(low))
        self.is_date = bool(DATE_RE.search(low)) and not self.pii
        self.is_num = bool(NUM_RE.search(low)) and not self.pii
        self.n = self.blank = self.marker = self.edge_ws = self.maxlen = 0
        self.counter: Counter = Counter()
        self.overflow = False
        self.samples: list[str] = []
        self.keys_raw: set[str] = set()
        self.keys_trim: set[str] = set()
        # numeric
        self.num_n = self.num_bad = self.num_neg = self.num_zero = 0
        self.num_sum = 0.0
        self.num_min = self.num_max = None
        # dates
        self.dt_n = self.dt_bad = self.dt_future = self.dt_old = self.dt_noniso = 0
        self.dt_noniso_samples: list[str] = []
        self.dt_min = self.dt_max = None
        self.dt_bad_samples: list[str] = []
        self.years: Counter = Counter()

    def update(self, s: pd.Series) -> None:
        present = s.notna()
        marker = present & s.isin(MARKERS)
        self.n += len(s)
        self.blank += int((~present).sum())
        self.marker += int(marker.sum())
        v = s[present & ~marker]
        if v.empty:
            return
        lens = v.str.len()
        self.maxlen = max(self.maxlen, int(lens.max()))
        trimmed = v.str.strip()
        self.edge_ws += int((trimmed.str.len() != lens).sum())

        if not self.pii and len(self.samples) < 3:
            for x in v.drop_duplicates().head(6):
                x = x.replace("\n", "\\n")
                if x not in self.samples and len(self.samples) < 3:
                    self.samples.append(x)

        if self.is_key:
            self.keys_raw.update(v.tolist())
            self.keys_trim.update(trimmed.tolist())
        elif not self.pii and not self.overflow:
            for k, c in v.value_counts().items():
                if k in self.counter:
                    self.counter[k] += c
                elif len(self.counter) < DISTINCT_CAP:
                    self.counter[k] = c
                else:
                    self.overflow = True
                    break

        if self.is_num:
            x = pd.to_numeric(v.str.replace(r"[$,\s]", "", regex=True), errors="coerce")
            ok = x.notna()
            self.num_bad += int((~ok).sum())
            xv = x[ok].astype("float64")
            if len(xv):
                self.num_n += len(xv)
                self.num_sum += float(xv.sum())
                self.num_neg += int((xv < 0).sum())
                self.num_zero += int((xv == 0).sum())
                lo, hi = float(xv.min()), float(xv.max())
                self.num_min = lo if self.num_min is None else min(self.num_min, lo)
                self.num_max = hi if self.num_max is None else max(self.num_max, hi)

        if self.is_date:
            d = pd.to_datetime(v, errors="coerce", utc=True, format="ISO8601")
            bad = d.isna()
            if bad.any():
                self.dt_noniso += int(bad.sum())
                for x in v[bad].head(3):
                    if len(self.dt_noniso_samples) < 3 and x not in self.dt_noniso_samples:
                        self.dt_noniso_samples.append(x)
                d.loc[bad] = pd.to_datetime(v[bad], errors="coerce", utc=True, format="mixed")
            still_bad = d.isna()
            self.dt_bad += int(still_bad.sum())
            for x in v[still_bad].head(3):
                if len(self.dt_bad_samples) < 3 and x not in self.dt_bad_samples:
                    self.dt_bad_samples.append(x)
            yr = d.dt.year.astype("float64")
            self.dt_n += int(yr.notna().sum())
            self.dt_future += int((yr >= PLAUSIBLE_YEARS[1] + 1).sum())
            self.dt_old += int((yr < PLAUSIBLE_YEARS[0]).sum())
            plaus = yr.between(*PLAUSIBLE_YEARS)
            if plaus.any():
                lo, hi = d[plaus].min(), d[plaus].max()
                self.dt_min = lo if self.dt_min is None else min(self.dt_min, lo)
                self.dt_max = hi if self.dt_max is None else max(self.dt_max, hi)
                self.years.update({int(k): int(c) for k, c in yr[plaus].value_counts().items()})

    @property
    def present(self) -> int:
        return self.n - self.blank - self.marker

    def distinct_label(self) -> str:
        if self.pii:
            return "withheld"
        if self.is_key:
            return f"{len(self.keys_trim):,}"
        return f">{DISTINCT_CAP:,}" if self.overflow else f"{len(self.counter):,}"


# --------------------------------------------------------------------------- reading
def detect_encoding(path: Path) -> str:
    dec = codecs.getincrementaldecoder("utf-8-sig")()
    try:
        with open(path, "rb") as f:
            while chunk := f.read(1 << 24):
                dec.decode(chunk)
        dec.decode(b"", final=True)
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "cp1252"


def pick(header: list[str], prefix: str) -> str | None:
    return next((h for h in header if h.lower().startswith(prefix)), None)


def _scan(path: Path, enc: str, header: list[str], nrows: int | None, skip_bad: bool) -> dict:
    cols = [Col(c) for c in header]
    key_col = pick(header, "contractnumber") or pick(header, "referencenumber") or pick(header, "solicitationnumber")
    amend_col = pick(header, "amendmentnumber")
    pair_hashes: set[int] = set()
    pair_rows = rows = 0
    reader = pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""], encoding=enc,
                         encoding_errors="replace", chunksize=CHUNK, nrows=nrows,
                         on_bad_lines="skip" if skip_bad else "error")
    for chunk in reader:
        rows += len(chunk)
        for col in cols:
            col.update(chunk[col.name])
        if key_col:
            k = chunk[key_col].fillna("").str.strip()
            a = chunk[amend_col].fillna("").str.strip() if amend_col else ""
            pair_hashes.update(pd.util.hash_pandas_object(k + "|" + a, index=False).tolist())
            pair_rows += len(chunk)
        print(f"    ... {rows:,} rows", flush=True)
    return dict(rows=rows, cols=cols, key_col=key_col, amend_col=amend_col,
                pair_rows=pair_rows, pair_unique=len(pair_hashes))


def profile_file(path: Path, nrows: int | None) -> dict:
    t0 = time.time()
    enc = detect_encoding(path)
    header = pd.read_csv(path, nrows=0, encoding=enc, encoding_errors="replace").columns.tolist()
    error = None
    try:
        res = _scan(path, enc, header, nrows, skip_bad=False)
    except (pd.errors.ParserError, ValueError) as e:
        error = f"{type(e).__name__}: {e}"
        print("    !! malformed row found; re-reading with bad lines skipped", flush=True)
        res = _scan(path, enc, header, nrows, skip_bad=True)
    return dict(path=path, enc=enc, error=error, seconds=time.time() - t0,
                size_mb=path.stat().st_size / 1e6, nrows=nrows, **res)


# --------------------------------------------------------------------------- rendering
def pct(a: int, b: int) -> str:
    return f"{100 * a / b:5.1f}%" if b else "  n/a"


def render(p: dict) -> str:
    cols: list[Col] = p["cols"]
    rows = p["rows"]
    out: list[str] = []
    w = out.append
    w(f"PROFILE: {p['path'].name}")
    w("=" * 100)
    w(f"size {p['size_mb']:,.1f} MB | encoding {p['enc']} | rows {rows:,} | columns {len(cols)} | {p['seconds']:.0f}s"
      + (f" | FIRST {p['nrows']:,} ROWS ONLY" if p["nrows"] else ""))
    if p["error"]:
        w(f"!! MALFORMED ROW(S): the strict read failed ({p['error']}).")
        w("!! The file was re-read with bad lines skipped, so the statistics below leave out an unknown number of rows.")
    w("'present' = not blank and not an N/A / NULL marker. 'marks' = cells holding N/A / n/a / NULL / null.")
    w("'edge-ws' = present cells with leading or trailing whitespace.")
    w("")
    w("1. COLUMNS")
    w(f"{'#':>3} {'column':<46} {'present':>7} {'distinct':>9} {'marks':>7} {'edge-ws':>8} {'maxlen':>6}  samples")
    for i, c in enumerate(cols, 1):
        samples = "[withheld: contact/address field]" if c.pii else " | ".join(s[:30] for s in c.samples)
        w(f"{i:>3} {c.name[:46]:<46} {pct(c.present, rows):>7} {c.distinct_label():>9} {c.marker:>7,} "
          f"{c.edge_ws:>8,} {c.maxlen:>6}  {samples}")

    w("")
    w("2. CATEGORICAL COLUMNS (value counts of the present values)")
    shown = False
    for c in cols:
        if c.pii or c.is_key or c.is_date or c.is_num or c.overflow or not c.counter:
            continue
        if len(c.counter) > CATEGORICAL_MAX:
            continue
        shown = True
        w(f"\n  {c.name}   (present {pct(c.present, rows).strip()}, {len(c.counter)} distinct)")
        for val, cnt in c.counter.most_common(TOP):
            label = val[:58].replace("\n", "\\n")
            w(f"     {label:<58} {cnt:>10,}  {100 * cnt / c.present:5.1f}%")
        if len(c.counter) > TOP:
            w(f"     ... and {len(c.counter) - TOP} more")
    if not shown:
        w("  (none)")

    w("")
    w(f"3. DATE COLUMNS (plausible range {PLAUSIBLE_YEARS[0]}-{PLAUSIBLE_YEARS[1]}; others counted as suspect)")
    dcols = [c for c in cols if c.is_date and c.present]
    for c in dcols:
        lo = c.dt_min.strftime("%Y-%m-%d") if c.dt_min is not None else "-"
        hi = c.dt_max.strftime("%Y-%m-%d") if c.dt_max is not None else "-"
        w(f"\n  {c.name}   present {c.present:,} | parsed {c.dt_n:,} | unparsed {c.dt_bad:,} | "
          f"range {lo} to {hi} | year>={PLAUSIBLE_YEARS[1] + 1}: {c.dt_future:,} | year<{PLAUSIBLE_YEARS[0]}: {c.dt_old:,}")
        if c.dt_noniso:
            w(f"     !! {c.dt_noniso:,} values were not ISO (YYYY-MM-DD...) and were parsed by guessing; "
              f"check day/month order. Examples: {c.dt_noniso_samples}")
        if c.dt_bad_samples:
            w(f"     unparsed examples: {c.dt_bad_samples}")
        if c.years:
            w("     rows per year: " + "  ".join(f"{y}:{n:,}" for y, n in sorted(c.years.items())))
    if not dcols:
        w("  (none)")

    w("")
    w("4. NUMERIC COLUMNS")
    ncols = [c for c in cols if c.is_num and c.present]
    for c in ncols:
        rng = f"{c.num_min:,.2f} to {c.num_max:,.2f}" if c.num_min is not None else "-"
        w(f"\n  {c.name}   present {c.present:,} | numeric {c.num_n:,} | non-numeric {c.num_bad:,} | range {rng} | "
          f"sum {c.num_sum:,.2f} | negative {c.num_neg:,} | zero {c.num_zero:,}")
    if not ncols:
        w("  (none)")

    w("")
    w("5. IDENTIFIER COLUMNS")
    for c in [c for c in cols if c.is_key]:
        w(f"  {c.name}: present {c.present:,} ({pct(c.present, rows).strip()}) | distinct as-is {len(c.keys_raw):,} | "
          f"distinct after trimming {len(c.keys_trim):,} | cells with edge whitespace {c.edge_ws:,}")
    if p["key_col"]:
        dup = p["pair_rows"] - p["pair_unique"]
        what = f"{p['key_col']} + {p['amend_col']}" if p["amend_col"] else p["key_col"]
        w(f"  Row uniqueness on ({what}, trimmed): {p['pair_rows']:,} rows, {p['pair_unique']:,} unique, {dup:,} repeated")
    else:
        w("  (no contract / reference / solicitation number column found)")
    w("")
    return "\n".join(out)


def stem(name: str) -> str:
    """'referenceNumber-numeroReference' -> 'referencenumber'; '...-fra' columns keep a '_fra' tag."""
    low = name.strip().lower()
    return low.split("-")[0] + ("_fra" if low.endswith("-fra") else "")


def schema_comparison(profiles: dict[str, dict]) -> str:
    def names(label):
        return {stem(c.name): c.name for c in profiles[label]["cols"]}

    pairs = [("contracts_current", "contracts_legacy"), ("tenders_current", "tenders_legacy"),
             ("contracts_current", "tenders_current")]
    out = ["SCHEMA COMPARISON (names compared by their English stem, e.g. referenceNumber-numeroReference = referenceNumber)", "=" * 100]
    for a, b in pairs:
        if a not in profiles or b not in profiles:
            out.append(f"\n{a} vs {b}: skipped (a file is missing)")
            continue
        na, nb = names(a), names(b)
        both, only_a, only_b = sorted(set(na) & set(nb)), sorted(set(na) - set(nb)), sorted(set(nb) - set(na))
        out.append(f"\n{a} ({len(na)} cols) vs {b} ({len(nb)} cols): {len(both)} in both")
        out.append(f"  only in {a} ({len(only_a)}): " + ", ".join(na[k] for k in only_a))
        out.append(f"  only in {b} ({len(only_b)}): " + ", ".join(nb[k] for k in only_b))
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", default="data/raw", help="folder holding the source CSVs (default data/raw)")
    ap.add_argument("--out", default="data/processed/profile", help="folder for the reports")
    ap.add_argument("--nrows", type=int, default=None, help="only read the first N rows of each file (quick trial)")
    args = ap.parse_args()

    raw, out = Path(args.raw), Path(args.out)
    files = sorted(raw.glob("*.csv")) if raw.is_dir() else []
    if not files:
        print(f"No CSV files found in {raw}/. Download these into it:")
        for label, url in DOWNLOADS.items():
            print(f"  {label:<18} {url}")
        return 1
    out.mkdir(parents=True, exist_ok=True)

    profiles: dict[str, dict] = {}
    for f in files:
        label = next((lab for frag, lab in KNOWN.items() if frag.lower() in f.name.lower()), f.stem)
        print(f"\n[{label}] {f.name}", flush=True)
        p = profile_file(f, args.nrows)
        profiles[label] = p
        (out / f"{label}.txt").write_text(render(p), encoding="utf-8")
        print(f"  -> {out / (label + '.txt')}")
    (out / "schema_comparison.txt").write_text(schema_comparison(profiles), encoding="utf-8")

    print("\n" + "=" * 100 + "\nSUMMARY")
    for label, p in profiles.items():
        flag = "  (malformed rows skipped - see report)" if p["error"] else ""
        print(f"{label:<18} {p['rows']:>10,} rows  {len(p['cols']):>3} cols  {p['size_mb']:>8,.1f} MB{flag}")
        for c in p["cols"]:
            if c.is_date and c.dt_min is not None and re.search(r"award|publication|closing", c.name.lower()):
                print(f"    {c.name[:44]:<44} {c.dt_min:%Y-%m-%d} to {c.dt_max:%Y-%m-%d}")
    missing = [lab for lab in DOWNLOADS if lab not in profiles]
    if missing:
        print(f"\nNot found in {raw}/: {', '.join(missing)}")
    print(f"\nReports written to {out}/ - attach those .txt files in the chat (they contain no contact details).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
