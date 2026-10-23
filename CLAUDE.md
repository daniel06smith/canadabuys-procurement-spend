# CLAUDE.md - Public procurement spend analytics project

Daniel (SFU Computing Science, Vancouver) is building this project for his application to the **Celestica
"Student Intern, SCM Data Analyst"** role (Toronto, May 2027 start). The posting asks for spend categorisation,
KPI reporting, automating manual reporting with Python, executive dashboards, Power BI, SQL and Python.
The data is Government of Canada procurement data from CanadaBuys.

## How to work with Daniel on this project

This is a **guided build, not a hand-off.** Daniel wants to understand every decision and every output well enough
to explain the project in an interview. So:

* Work **one stage at a time** (plan below). Do not run ahead, and do not build a later stage "to save time".
* For every cleaning, modelling or metric choice: say what the problem is, show real evidence from the data,
  give the options with their trade-offs, recommend one, and let **Daniel decide**. Log the decision in
  `docs/decisions.md`.
* Explain in plain language first, then show code. Define each KPI in words before writing the SQL.
* Show real rows and real counts rather than describing them. Never state a number you have not computed from
  the data in this project.
* End each stage with a checkpoint: a short recap of what was decided and what is still open. Move on only when
  Daniel says so.
* Daniel will build the Power BI dashboard himself, with guidance. DAX cannot be run or tested without Power BI
  Desktop, so say clearly when a measure is untested.
* Keep replies concise. Prose for explanations; a table or list only when comparing options.

## Standing rules (from Daniel)

* **Do not source, download or substitute datasets on your own.** Use the files Daniel puts in `data/raw/`. If a
  file is missing, ask him for it.
* **Nothing goes on a resume without Daniel's explicit approval.** The tailored one-page resume for Celestica is
  built separately, from his master LaTeX file in the claude.ai project "Fall 2026 Co-op applications", after
  this project is done and he has approved including it. Resume claims may only use measured numbers.
* Do not claim analysis the data cannot support (see "What the data cannot do").
* Raw data and personal-contact fields: `data/` and `output/` are gitignored. Contact, e-mail, phone, address and
  postal-code columns are never loaded into the pipeline and never printed.

## Stage plan and status

| # | Stage | Status |
|---|---|---|
| 1 | Purpose and outputs | **Done except the page list** - see `docs/decisions.md`. Both lenses of competition confirmed; the five proposed dashboard pages are not yet confirmed (settle by stage 7 at the latest) |
| 2 | Data tour: profile every source against the data dictionary | **In progress** - profiler written; waiting for Daniel's four source files to be profiled |
| 3 | Data model: how contracts (old + new) and tenders fit together; measure the tender-to-contract match rate; test for a trend break at the 2023 system change | Not started |
| 4 | Cleaning rules, one decision at a time | Not started |
| 5 | Categorisation and supplier resolution | Not started |
| 6 | KPIs: definition in words, then SQL views | Not started |
| 7 | Outputs: Excel monthly report, Power BI star schema and dashboard | Not started |
| 8 | README (download links, `data/raw` instructions), decision write-up, then resume wording (only with approval) | Not started |

**Phasing (confirmed by Daniel):** Phase 1 = dashboard pages 1-3 (overview, suppliers, competition) from the contract
history files only. Phase 2 = page 4 (contract changes, also contract history) and page 5 (tender pipeline, the
only page needing tender files). Stages 3-7 are run for phase 1 first. All four sources are still profiled in
stage 2, because that tells us early whether page 5 and the tender-to-contract link are realistic.

**Next action:** run `python scripts/profile_sources.py` (Daniel's machine has the files; if they are in
`data/raw/` you can run it yourself), read the reports in `data/processed/profile/` with Daniel, and work through
the stage 2 checklist below.

### Stage 2 checklist (questions the profile must answer)

1. Do the legacy files use the same columns as the current ones? (`schema_comparison.txt`) Which fields are missing
   before 2023: UNSPSC or GSIN, procurementMethod, limitedTenderingReason, supplier standardized name?
2. Date coverage and boundaries: do legacy and current contract files meet cleanly around May/Jun 2023, and the
   tender files around Aug 2022? Any overlap, gap, or placeholder dates?
3. Row grain: is a contract still one original + amendments in the legacy file? Are there repeated
   (contractNumber, amendmentNumber) pairs? How common is stray whitespace in identifiers?
4. How are amendments numbered in legacy rows (alphanumeric values)?
5. How well populated are `referenceNumber` and `solicitationNumber` in the tender files? (Needed for linking.)
6. Value fields: are legacy values comparable, and are there negatives, zeros or implausible maxima?
7. Encoding or malformed rows in any file? Do the "complete" files really make the per-year files unnecessary?

## Data sources (all Open Government Licence - Canada)

Put these in `data/raw/`. The per-fiscal-year files overlap these and should **not** be loaded as well (verify with
row counts in stage 2).

| Label | File | Covers |
|---|---|---|
| contracts_current | `contractHistoryComplete-contratsOctroyesComplet.csv` | Jun 2023 onwards (dataset 4fe645a1-ffcd-40c1-9385-2c771be956a4) |
| contracts_legacy | `2009-2023-contractHistoryHistorical-contratsOctroyesHistorique.csv` | Jan 2009 - May 2023 |
| tenders_current | `tenderNoticeComplete-avisAppelOffresComplet.csv` | Aug 2022 onwards (dataset 6abd20d4-7a1c-4b38-baa2-9525d0bb2fd2) |
| tenders_legacy | `2009-2022-tenderNoticeHistorical-AvisAppelOffresHistorique.csv` | 2009 - Aug 2022 |

Base URL for all four: `https://canadabuys.canada.ca/opendata/pub/` + file name. The agency restructured these CSVs
between 17 Mar and 10 Apr 2026, so files downloaded earlier may have a different layout. Contract files refresh
monthly (around the third week), tender files daily. Data dictionary: `docs/data_dictionary.md`.

Only `contracts_current` has been inspected so far (it is what v1 was built on). Nothing is yet known about the
other three beyond what the dictionary and the dataset pages say.

## What the data cannot do

* No bidder counts: "competitive" means the recorded method, not that several bids arrived.
* No delivery dates, quantities, unit prices or invoices: no on-time delivery, price variance or PO-to-invoice work.
* Tender notices carry no dollar value: tender analysis is counts and timing only.
* This is federal public-sector procurement, not manufacturing or electronics spend. Say so in the README.
* No explicit tender-to-contract key exists. Linking via `referenceNumber` / `solicitationNumber` is a hypothesis
  until its match rate is measured.

## Lessons from the v1 build (contracts_current only, Jun 2023 - Sep 2026)

These are verified facts about that one file; re-check each on the legacy data rather than assuming.

* 23,238 rows = 14,169 contracts (original + amendments). 14,193 contract numbers before trimming: **24 appear
  twice because of trailing whitespace** (67 contract-number cells and 71 reference-number cells affected). Failing
  to trim double-counted about $5.1B. Trim every text cell on load.
* `totalContractValue` is identical on every record of a contract: it is the final cumulative value (the data
  dictionary agrees). **Never sum it across amendment rows.**
* `contractAmount` on amendment rows is sometimes a running total and sometimes a delta (the dictionary does not say).
  It is used only from the original record (amendment `000`). The "grew after award" metric is therefore
  **unvalidated**; restrict it to Contract / Contract against SA / Task Authorization Based Contract, because standing
  offers and supply arrangements carry a ceiling value, not spend.
* Strings `N/A`, `n/a`, `NULL`, `null` are missing values. Read with `keep_default_na=False, na_values=[...]`.
* Placeholder end dates (2099, 2100, 2126, 3000) exist; 83 end dates in the file are year 2060 or later.
* `amendmentNumber` is mostly `000`..`0NN` but includes `T01` / `S01` style values (treated as sequence 1000).
* 7.6% of rows (1,762) have a GSIN code but no UNSPSC code, and all of them also have a blank instrumentType (only
  3 other rows have one blank). They were categorised from the GSIN description with keyword rules; the title
  column holds the supplier name, so do not use it.
* Segment 95 and family 8111 needed special handling in the UNSPSC to category map. Categories follow the buyer's
  code; some codes disagree with the contract title.
* Supplier names are matched by rule (accents, punctuation, legal suffixes, publisher's standardized name), no fuzzy
  matching. Related entities (for example MDA and MDA Systems) stay separate, so concentration is slightly understated.
* Government of Canada fiscal year runs April-March. Awards are posted late (contract-level lag 25th/50th/75th
  percentile 4 / 30 / 201 days), so the newest months are provisional.
* Nine contracts of $1B or more are 47% of valued spend; offer a view excluding contracts over $100M.
* v1 headline numbers (corrected after a whitespace bug): 14,169 contracts, 10,228 valued, $62.25B total, top-10
  suppliers 51.4%, competitive share 77.1% of reported value, 42.5% of contracts amended.

## Code map and commands

Python 3.13, pandas >= 3.0, openpyxl, pytest. Not a git repository yet (`.gitignore` is ready).

```
scripts/profile_sources.py   read-only profiler for every CSV in data/raw -> data/processed/profile/*.txt
spendpipe/config.py          column map, category maps, keyword rules, constants
spendpipe/clean.py           load_raw, clean_events, collapse_to_contracts, data_quality_issues
spendpipe/categorize.py      UNSPSC / GSIN-keyword categorisation
spendpipe/suppliers.py       rule-based supplier resolution
spendpipe/build_db.py        SQLite star schema + Power BI CSV export
spendpipe/report.py          8-tab Excel monthly report (openpyxl, live formulas)
sql/schema.sql, sql/views.sql
tests/test_core.py           53 tests (python -m pytest -q)
docs/                        data_dictionary.md, decisions.md, powerbi_spec.md, sample report
```

```bash
python scripts/profile_sources.py                    # add --nrows 50000 for a quick trial
python -m spendpipe build  --csv data/raw/contractHistoryComplete-contratsOctroyesComplet.csv
python -m spendpipe report --month 2026-03
python -m pytest -q
```

The v1 pipeline still reads one CSV and writes `data/procurement.db` and `output/`. It will be reworked to read
all sources from `data/raw/` and write to `data/processed/` as stages 3-7 progress. `README.md` and
`docs/powerbi_spec.md` describe v1 and must be rewritten at the end, not before.
Keep the test suite passing; add tests for every new cleaning or matching rule.
