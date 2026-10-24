# Decision log

One entry per decision Daniel makes, with the reasoning, so the README and interview answers can be written from it.
Newest at the bottom. Format: **Stage - decision** / options considered / chosen / why.

## Stage 1 - purpose and outputs (2026-10-23)

**Questions the project answers**
1. Where does the money go? Spend by category, over time.
2. How dependent are we on a few suppliers? Concentration and the long tail.
3. Where does competition lie? Replaces the earlier "how much is competed". Two lenses:
   *process competition* (competed or not, and the stated reason, by category / department / size / fiscal year)
   and *market competition* (supplier count and HHI per category). Plotting competed share against concentration
   per category flags categories that are both non-competed and dominated by few suppliers.
4. How do contracts change after award? Amendments and value changes (metric unvalidated; see CLAUDE.md).
5. How does sourcing activity behave? Tender volume, posting-to-closing window, cancellation rate, method mix,
   and whether tenders can be traced to the contracts they produced (match rate to be measured in stage 3).
6. How have these shifted from 2009 to 2026? Handled as a time axis on every page (fiscal year > quarter > month
   drill-down plus slicers), not as a separate page. Trend breaks around the 2023 system change must be tested first.

**Outputs**: monthly Excel report, Power BI dashboard (Daniel builds it, Claude guides), README with download
links and run instructions.

**Dashboard shape**: five pages (overview, suppliers and concentration, competition, contract changes, tender
pipeline) with time as a slicer on all of them. *Status: recommended default; Daniel moved on without objecting.
Revisit in stage 7 if the data does not support a page.*

**Both lenses of "competition" kept.** *Same status as above.*

**Data layout**: raw CSVs in `data/raw/` (links in README), pipeline output in `data/processed/`. Both gitignored.

## Stage 2 - data tour (2026-10-23)

**Source files: the two complete contract files, not the 19 per-fiscal-year files.**
Options: (a) complete files only; (b) per-year files only; (c) both, de-duplicated.
Evidence: 509,388 (contract, amendment) rows match. The per-year files have 108 extra rows (and 125 rows with a newer
totalContractValue) only because they were refreshed later than the complete files (project log entry 5).
Chosen: (a). Why: two files instead of 21, one consistent layout, no merge step. The small refresh gap closes at the
next monthly update and does not matter for a portfolio project. Same rule for tenders: the two complete files.

## Stage 2 - tooling (2026-10-23)

**EDA in notebooks.** Options: throwaway scripts / evidence scripts in `scripts/` / Jupyter notebooks. Chosen:
notebooks in `notebooks/`, numbered, one question each, with findings written under the code that produced them.
Why: every number in the log and decisions stays reproducible and readable next to its code, which matters for
explaining the project. Shared loading code lives in `spendpipe/sources.py` (tested), not in the notebooks, so all
notebooks read the data the same way; cleaning rules found in EDA move into `spendpipe/` with tests.

**matplotlib and pyarrow installed** (added to `requirements.txt`). pyarrow enables a Parquet cache in
`data/interim/`: the 834 MB legacy file loads in 0.1 s from cache instead of 8 s from CSV (measured).

**Notebooks are committed with outputs.** Options: keep outputs / strip them (nbstripout). Chosen: keep. Why: GitHub
renders them, so a reader can see the EDA without the 1.6 GB of data. Safe because the data is public (OGL) and
contact/address columns are never loaded (enforced by `assert_no_contact_columns`; notebooks scanned for e-mail and
phone patterns before commit). Cost: noisier diffs.

**Stage 2 evidence rebuilt as notebooks** rather than starting fresh at stage 3, so no logged number lacks code.
