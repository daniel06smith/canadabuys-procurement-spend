# Public Procurement Spend Analytics Pipeline

A Python + SQL pipeline that turns the Government of Canada's **CanadaBuys contract history**
into a clean spend database, a set of procurement KPIs, an automated monthly Excel operating
report, and a Power BI-ready star schema.

It is built around the questions a supply-chain data team asks of spend data:
*where is the money going, who are we dependent on, how much is competed, and how often do
contracts grow after award?*

> **Scope note.** This is real *public-sector* procurement data (federal contracts), not
> manufacturing or electronics spend. The file has no delivery dates, quantities, unit prices
> or invoices, so on-time delivery, price variance and invoice reconciliation are **not**
> computed. See [Limitations](#limitations).

## Results at a glance (data through 2026-09-27)

| | |
|---|---|
| Source rows -> contracts | 23,238 records -> **14,169 contracts** (amendment history collapsed) |
| Award dates | Jun 2023 - Sep 2026 (40 months) |
| Valued contracts / total value | 10,228 / **$62.3B CAD**; a further 3,940 contracts carry $0 (standing offers, supply arrangements) |
| Supplier name resolution | 6,961 raw legal names -> **6,661 suppliers** |
| Spend categorisation | **86.8%** of spend via UNSPSC code, 13.2% via keyword fallback on legacy records, <0.1% unclassified |
| Supplier concentration | top 10 suppliers = 51.4% of value, top 50 = 74.3% (one icebreaker contract alone is ~$13B) |
| Competitive share | 77.1% of *reported* competitive + non-competitive value; 16.7% of value has no method reported |
| Contracts amended after award | 42.5% of all contracts; of 2,539 comparable stand-alone contracts, 49.2% ended above their original award (median +42.6% when they grew; +$3.2B on a $23.7B original base) |
| Data-quality exceptions | 3,808 flagged items across 9 checks (see below) |

Nine contracts of $1B+ make up 47% of all valued spend, so every report offers a view
**excluding contracts over $100M**.

## Data source

[CanadaBuys contract history, 2023-06-01 onwards](https://open.canada.ca/data/en/dataset/4fe645a1-ffcd-40c1-9385-2c771be956a4)
(Public Services and Procurement Canada), file `contractHistoryComplete-contratsOctroyesComplet.csv`.
The raw file is not stored in this repo.

*Contains information licensed under the
[Open Government Licence - Canada](https://open.canada.ca/en/open-government-licence-canada).*

## What the pipeline does

```
CSV (23,238 rows, 91 cols)
   |  load_raw      keep the 28 English columns used, drop contact-person PII, trim whitespace
   v
clean_events        dates, numbers, locations, placeholder flags       (spendpipe/clean.py)
   v
collapse_to_contracts   one row per contract, original vs final value  (spendpipe/clean.py)
   v
add_categories      UNSPSC -> 14 business categories (+ keyword fallback) (categorize.py)
   v
resolve_suppliers   rule-based entity resolution                       (suppliers.py)
   v
SQLite star schema  + KPI views (sql/views.sql) + Power BI CSVs        (build_db.py)
   v
Excel monthly report (openpyxl, live formulas)                         (report.py)
```

### Things the data forced me to handle

* **Amendment history.** 23,238 rows describe 14,169 contracts (original + amendments). Spend
  is taken from the final record, never summed across amendments.
* **Value fields are not what they look like.** `totalContractValue` is identical on every
  record of a contract (0 exceptions), so it is the contract's final value. `contractAmount`
  is cumulative on some amendment rows and a delta on others, so it is used only from the
  *original* record to measure growth after award.
* **Duplicate contract numbers.** 24 contract numbers appeared both with and without a
  trailing space, which double-counted about **$5.1B** (one $3.7B contract twice). Fixed by
  trimming every text cell on load; covered by a unit test.
* **Standing offers and supply arrangements** have $0 value (a ceiling, not a spend). They are
  counted as contracts but add no spend, and are excluded from the value-growth metric.
* **Placeholder dates.** End dates of 2099, 2100, 2126 and 3000 are flagged and blanked.
* **Messy locations.** 185 province/state spellings (abbreviations, French names,
  "Quebec"/"Québec"), and countries as both `CA` and `Canada`, normalised to one canonical set.
* **Legacy-format records.** 7.6% of rows carry a GSIN code but no UNSPSC code; they are classified
  from the GSIN description with keyword rules (their title is just the supplier name, so it is
  deliberately *not* used).
* **Missing-value markers.** `N/A`/`NULL` strings are treated as missing.

### Spend categorisation

The first UNSPSC code on each contract is mapped by its 2-digit segment to one of 14 business
categories (plus *Unclassified*), with family `8111` (computer services) split out as *IT
Services & Software Support*. The mapping is a plain dictionary in `spendpipe/config.py`.

### Supplier resolution

Names are normalised (accents, `&`, punctuation, legal suffixes such as Inc/Ltd/Ltée), then the
publisher's own *standardized name* is used wherever a row has both names to learn legal-name
aliases for rows that lack it. There is intentionally **no fuzzy matching**: a false merge of two
different companies is worse for a concentration analysis than leaving a duplicate.

## Quick start

```bash
pip install -r requirements.txt
python -m spendpipe build  --csv path/to/contractHistoryComplete-contratsOctroyesComplet.csv
python -m spendpipe report                    # latest settled month
python -m spendpipe report --month 2026-03    # a specific month
python -m pytest -q                           # 53 unit tests
```

`build` writes `data/procurement.db` (SQLite) and `output/powerbi/*.csv`; `report` writes
`output/monthly_report_<month>.xlsx`. Re-running is idempotent. Tested with Python 3.13,
pandas 3.0, openpyxl 3.1.

## The database

Star schema (`sql/schema.sql`): `fact_contract` (one row per contract), `fact_contract_event`
(one row per record), `dim_supplier`, `dim_category`, `dim_department`, `dim_date`,
`dim_unspsc_segment`, `dq_issue`.

KPI views (`sql/views.sql`), all plain SQLite SQL with window functions:

| View | Answers |
|---|---|
| `v_spend_by_category` | spend, share and supplier count per category, with and without mega-contracts |
| `v_supplier_pareto` | supplier ranking with cumulative share |
| `v_category_concentration` | top-supplier share and HHI inside each category |
| `v_monthly_spend` | monthly awards with a 3-month moving average |
| `v_sourcing_mix`, `v_competitive_by_fy`, `v_limited_tendering` | competitive vs non-competitive, and why contracts were not competed |
| `v_amendment_summary`, `v_amendment_by_category` | how often and by how much contracts grow after award |
| `v_regional_spend`, `v_supplier_size_mix` | supplier geography and size (small / medium / large) |
| `v_dq_summary` | data-quality exceptions |

## Monthly operating report

`python -m spendpipe report --month YYYY-MM` rebuilds an 8-tab workbook
(sample: [`docs/sample_monthly_report_2026-03.xlsx`](docs/sample_monthly_report_2026-03.xlsx)):
Summary (month vs prior month vs same month last year), Category, Suppliers (top 15 + cumulative
share), Sourcing, Amendments, Monthly Data (with charts), Data Quality, Notes.

Totals, shares, changes and cumulative percentages are live Excel formulas over the aggregates
the database supplies (292 formulas; recalculated with zero errors and cross-checked against
direct SQL). Months close to the newest publication date are labelled **provisional**, because
awards are often posted late (median lag across contracts: 30 days; 75th percentile: 201 days).

## Power BI

The star schema CSVs in `output/powerbi/` load straight into Power BI Desktop.
[`docs/powerbi_spec.md`](docs/powerbi_spec.md) has the relationships, the DAX measures, and a
five-page layout (overview, suppliers & concentration, sourcing governance, contract changes,
data quality). The `.pbix` is not included.

## Data-quality exceptions (whole file)

| Check | Contracts |
|---|---|
| Amended contract whose original record (amendment 000) is not in the file | 2,069 |
| Sourcing method not reported | 1,194 |
| Missing award date | 279 |
| Award published before its award date | 147 |
| End date is a system placeholder | 70 |
| Zero value on a stand-alone contract | 40 |
| Supplier province unknown (Canadian supplier) | 6 |
| End date before start date | 2 |
| Negative contract value | 1 |

## Limitations

* **Not a manufacturing data set.** Categories are dominated by ships, aircraft, defence, IT and
  professional services; electronic components are about 0.1% of value.
* **No delivery, quantity, unit-price or invoice fields.** On-time delivery, price variance and
  PO-to-invoice checks cannot be computed from this file.
* **Categories follow the code the buyer entered.** Some UNSPSC codes disagree with the
  contract's title (for example a fighter-jet support contract coded as teaching aids). 17% of
  contracts list UNSPSC codes that map to more than one business category; the first code is
  used, and contracts spanning more than one UNSPSC segment are flagged (`multi_category`).
* **Keyword-fallback categories are unvalidated** (13.2% of spend).
* **Supplier matching is conservative**, so related entities (for example *MDA* and *MDA Systems*)
  can remain separate and concentration is somewhat understated.
* **Growth-after-award is indicative.** It compares the original record's `contractAmount` to
  the final total for stand-alone contracts and has not been validated against source contracts.
* **Awards are posted late**, so recent months are incomplete until later refreshes.
* Spend is attributed to the **award month**, not to when money is paid.

## Project layout

```
spendpipe/      config.py  clean.py  categorize.py  suppliers.py  build_db.py  report.py  cli.py
sql/            schema.sql  views.sql
tests/          test_core.py            (53 tests)
docs/           powerbi_spec.md  sample_monthly_report_2026-03.xlsx
```

## Ideas for next steps

Fuzzy supplier matching with a manual override file; allocating multi-code contracts across
categories instead of using the first code; a tariff-exposure overlay using supplier country;
scheduling the monthly refresh.
