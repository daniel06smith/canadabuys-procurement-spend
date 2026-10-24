# Where the project stands (end of stage 2, 2026-10-23)

A plain-language summary of what has been done so far and what we learned. Numbers come from the files downloaded
2026-10-23 (profile reports in `data/processed/profile/`, notebooks 01-05). Problems in detail: `project_log.md`.
Decisions: `decisions.md`.

## What has been done

* **Stage 1 (purpose):** six questions the project answers (where the money goes, supplier dependence, competition,
  contract changes, tender activity, change over time) and three outputs (monthly Excel report, Power BI dashboard,
  README). The five dashboard pages are a working default, to be confirmed by stage 7.
* **Stage 2 (data tour):** all four source files are in `data/raw/`. A read-only profiler described every column of
  every file. Five notebooks dug into the questions it raised. `spendpipe/sources.py` is the shared loader the
  notebooks use: it trims whitespace, treats `N/A`/`NULL` as missing, never loads contact or address columns, and
  caches each file so it reloads in about a second. 60 tests pass.

## The four files at a glance

| File | Rows | Covers | Notes |
|---|---|---|---|
| contracts_legacy | 486,151 | award dates 2009-01-01 to 2023-05-31 | 210,543 contracts |
| contracts_current | 23,238 | award dates 2023-06-01 to 2026-09-25 | 14,169 contracts |
| tenders_legacy | 71,310 | published 2010-03-16 to 2022-08-05 | one row per notice |
| tenders_current | 30,830 | published 2022-08-08 to 2026-10-22 | one row per notice |

Both contract files have the same 91 columns, and both tender files have the same 67, so stacking them is
straightforward. The date boundaries meet cleanly (the tender files are split over a weekend). Combined, the contract
files hold 509,389 rows and 224,307 distinct contracts.

## What we learned (the stage 2 checklist)

1. **Same columns, but two record systems inside them.** Each contract row was written either by the old PWGSC
   system (467,679 legacy + 1,761 current rows) or the new CanadaBuys system (18,472 legacy + 21,477 current rows).
   You can tell them apart by the contracting-entity name. Old-system rows have a GSIN product code but no UNSPSC
   code, instrument type, solicitation number or status. This is why the empty columns line up the way they do, and
   it is the main problem stage 3 has to solve: making 2009-2026 one consistent series.
   The switch was gradual, with no single cutover date: the new system wrote 2% of a year's contracts in FY2017-18,
   13% in FY2021-22, 54% in FY2022-23 and 99% in FY2025-26. 4,918 contracts have rows from both systems.
   *Correction made along the way:* contract counts fall from 25,883 (FY2009-10) to 6,394 (FY2021-22), and we first
   blamed the new system. Comparing the two systems within the same years showed similar contract sizes, so the drop
   happened inside the old system. Why is still a stage 3 question.
2. **Dates.** The publisher puts each *row* in a file by that row's award date, or by its amendment date when the
   award date is blank. So 405 contracts ($6.41B) have rows in both files. v1, which read only the current file,
   counted them as new contracts. Fix: stack both files *before* grouping rows into contracts. End dates include
   placeholders: 8,465 legacy rows and 83 current rows are year 2060 or later.
3. **Row grain.** Still one row per original or amendment. No (contract number, amendment number) pair repeats in
   any file. Stray spaces in identifiers are back in the legacy file: 81 contract-number cells, which make 65
   contract numbers look new until trimmed. The loader trims, so this is already handled.
4. **Amendment numbers.** The legacy file has 237 distinct values, mostly `000`-style plus `T01`-style ones as in v1.
   27,522 legacy contracts have no original (`000`) row at all. One guess, not yet tested, is that they were
   awarded before 2009. To deal with in stage 3/4.
5. **Linking tenders to contracts.** `referenceNumber` cannot be used: it is a notice ID and matches no contract.
   Matching solicitation numbers exactly links almost no old-system contracts (0.3%). Legacy tender numbers carry a
   letter suffix (`01581-210906/A`). With the suffix stripped, the match rate is 29.7% for old-system contracts
   (about 50-60% a year from FY2012-13, when tender data starts) and 61.6% for new-system contracts. These are
   candidate matches that stage 3 must validate. Tender notices come from many departments, but the contracts are
   PSPC awards only, so many tenders will never have a contract to match.
6. **Values.** Legacy `contractAmount` has 19,352 negative rows and a maximum of $10.5B. `totalContractValue` has
   251 negatives. The v1 rule still holds (use `totalContractValue` once per contract and never add it up across
   amendment rows). Amendment amounts look like deltas: where the original row exists, a contract's amounts add up
   to its total value in 97.1% of old-system and 74.7% of new-system contracts, and negative amounts appear only on
   amendments. Negatives and the new-system exceptions need rules in stage 4.
7. **File quality.** No malformed rows or encoding problems in any file. The per-year files matched the complete
   files on 509,388 rows, and the only differences came from the per-year files being refreshed later.
   **Decision: use the complete files only** (see `decisions.md`).

Process lessons: an early evidence script put column labels on the wrong columns. We caught it because the output
looked implausible, and the shared loader now prevents it, with a test (log entry 6). Throwaway scripts were lost
when a temp folder was cleared, so all evidence now lives in executed notebooks that reproduce every logged number
(log entry 13).

## Still open (carried into stage 3 and later)

* How to make old- and new-system rows comparable:
  * categories: `procurementCategory` is not used the same way by both systems, so it cannot serve as a shared
    field. A GSIN-prefix map looks feasible: 34 prefixes cover 95% of old-system value, and on 5,498 contracts coded
    both ways it agrees with the v1 category 76.4% of the time (first estimate).
  * instrument type and procurement method.
* Testing for trend breaks across the transition years FY2017-18 to FY2023-24, rather than at one date.
* Validating the tender-to-contract matches.
* Client-department lists appear in a different order in different files ("A / B" vs "B / A"). Split and sort them
  in stage 4.
* One award date per contract for the 405 contracts split across files.
* What to do with the legacy contracts that have no original record.
* Rules for negative values and placeholder dates.
* 4,918 (contracts with rows from both systems) and 5,498 (contracts carrying both codes) measure different things.
  Some new-system rows also carry a GSIN code. Notebook 05 links the two in its text, so the difference needs a
  one-line check and a clarification.
* The five dashboard pages (confirm by stage 7).
