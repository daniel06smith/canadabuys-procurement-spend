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
