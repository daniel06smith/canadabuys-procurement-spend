# Project log: obstacles and how they were handled

One entry per obstacle: what went wrong or looked wrong, the evidence from the data, what was done, and status.
Decisions themselves live in `decisions.md`; this file records the problems that led to them.
Numbers are from the files downloaded 2026-10-23.

## Stage 2 - data tour (2026-10-23)

**1. Two record systems inside the same files.**
Both contract files have the same 91 columns, but each row was written by one of two systems, identifiable by the
contracting-entity label. "Public Works and Government Services Canada" (old system): 467,679 legacy rows and 1,761
current rows, GSIN codes only, no UNSPSC, instrument type, solicitation number or status. "Department of Public Works
and Government Services (PSPC)" (new CanadaBuys system): 18,472 legacy rows and 21,477 current rows, UNSPSC on every row.
The split is by row, not by file, and a single contract can have rows from both systems (128 of the 405 contracts in
obstacle 2). This explains v1's 1,761 "GSIN but no UNSPSC" rows. *Status: open - harmonisation approach for stage 3.*

**2. 405 contracts split across the legacy and current files.**
The publisher files each *row* by the award date on that row, or by its amendment date when the award date is
blank (0 exceptions in 509,389 rows; legacy <= 2023-05-31, current >= 2023-06-01). A contract therefore splits when
its rows disagree: 246 of the 405 have a blank award date on the rows that moved (236 with no award date on any
row, 10 with one only on their legacy rows), so those rows were filed by amendment date; 159 have rows carrying
different award dates (e.g. a contract awarded 2018-06-03 whose amendment 019 says "awarded"
2026-09-02, while its amendments 012-018, dated 2023-2026, stayed in the legacy file). No (contract, amendment) row
is duplicated. v1 read only the current file, so it counted these as new 2023-2026 contracts. totalContractValue
agrees across files for all 405; supplier legal name agrees for 74.1%. Value involved: $6.41B.
*Correction:* first logged as "older amendments in legacy, newer in current"; notebook 01 showed that was wrong.
*Status: open - fix is to stack both files before collapsing to contracts, and take one award date per contract (stage 3).*

**3. Legacy contracts with no original record.** 27,522 of 210,543 legacy contracts have no amendment `000` row, and
23,354 have no award date on any row. Hypothesis (untested): amendments to contracts awarded before 2009.
*Status: open - stage 3/4.*

**4. Tender reference numbers are not a link key.** `referenceNumber` is unique on every tender row (a notice ID) and
matches zero contracts. Exact match on solicitation number links 7,946 of 14,169 current contracts (56%) but only
1,792 of 210,543 legacy contracts, because only 4,789 legacy contracts carry a solicitation number. Also, contracts are
PSPC-awarded only, while PSPC posts 58% (legacy) / 38% (current) of tender notices. *Status: open - stage 3 measures
the match properly; tender-to-contract linking looks feasible only from Jun 2023.*

**5. Are the per-year files needed?** 19 per-fiscal-year contract files (Jan 2009 - FY2026-27), split by award fiscal
year, same 91-column header. 509,496 rows vs 509,389 in the two complete files; 509,388 (contract, amendment) rows match.
The 108 rows only in the yearly files and the 1 row only in the complete files are all `CW...` contracts awarded in
FY2025-26, carrying amendments dated October 2026: the yearly files were refreshed more recently. 125 matched rows
differ in totalContractValue for the same reason; no other field differs except one award date and one amendment date.
*Status: closed - Daniel chose the complete files only (decisions.md, stage 2).*

**7. The drop in contract counts is not the system change (correction).** First read: the old system records
smaller contracts (median $59K vs $212K), so the count drop is a recording change. Notebook 02 compared the two
systems *within the same fiscal years* and found similar sizes (FY2021-22 median $157K new vs $209K old; under-$25K
share 6.6% vs 5.1%). The overall gap is timing: counts fall from 25,883 (FY2009-10) to 6,394 (FY2021-22) inside the
old system, before the new one mattered; yearly value stays about $10-29B. Lesson: compare groups within the same
period before blaming the group. *Status: open - why small contracts fell is a stage 3 question.*

**8. The switch between systems was gradual.** New-system share of a year's contracts: 2% FY2017-18, 13% FY2021-22,
54% FY2022-23, 99% FY2025-26. 4,918 contracts have rows from both systems. There is no single cutover date to
test for a trend break; stage 3 must test across the transition years. *Status: open.*

**9. Amendment amounts are deltas (validates a v1 assumption, partly).** Where the original record is present, the
amounts of an amended contract sum to its total value in 97.1% of old-system and 74.7% of new-system contracts;
negative amounts appear only on amendments. *Status: old system settled; new system to examine in stage 4.*

**10. Tender links for old contracts need a normalised key.** Exact matching linked 0.3% of old-system contracts.
Legacy tender solicitation numbers carry a letter suffix (`01581-210906/A`); stripping it raises old-system
matches to 29.7% (about 50-60% per year from FY2012-13, when tender data starts) and new-system matches from
54.7% to 61.6%. Sample matches look plausible. *Status: open - matches must be validated in stage 3.*

**11. No shared category field to fall back on.** `procurementCategory` looked common to both systems, but in the
same years the new system almost never uses Construction (0.1% vs 7.3%) or Services-related-to-goods (0.0% vs 5.8%).
A GSIN-prefix map checked against UNSPSC on 5,498 dual-coded contracts agrees with the v1 category for 76.4% of
them (first estimate). *Status: open - stage 5.*

**12. Multi-department client lists have no fixed order.** The same contract lists "A / B" in one file and "B / A"
in another (most of the 241 client-department differences in notebook 03). *Status: open - split and sort in stage 4.*

**6. A bug in our own evidence script.** The first follow-up script read columns with `usecols` and renamed them in the
order listed, but pandas returns them in file order, so labels landed on the wrong columns. Caught because the output
made no sense (the "contracting entity" column held UNSPSC codes). Fixed by reordering before renaming. Lesson: check
that output is plausible before interpreting it. The shared loader (`spendpipe/sources.py`) now does the reordering
and has a test for it.

**13. Throwaway scripts were lost.** The first evidence scripts lived in a temporary folder that was cleared, so
some logged numbers had no surviving code. Fixed by moving all stage 2 evidence into executed notebooks
(`notebooks/01-05`) that reproduce every number in this log.
