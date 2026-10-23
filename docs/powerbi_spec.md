# Power BI dashboard spec

The pipeline writes a star schema to `output/powerbi/`. Build the report in
Power BI Desktop from those CSVs. Everything below (model, DAX, page layout) was
written to be pasted in; **the .pbix itself is not included and the DAX has not
been run in Power BI**, so check each measure as you add it.

## 1. Load the data

`Get data > Text/CSV` for each file in `output/powerbi/`:

| Table | Role | Grain |
|---|---|---|
| `fact_contract` | fact | one row per contract (14,169) |
| `dim_supplier` | dimension | one row per resolved supplier (6,661) |
| `dim_category` | dimension | 15 business categories |
| `dim_department` | dimension | client department |
| `dim_date` | dimension | one row per day (mark as date table) |
| `dq_issue` | fact | one row per data-quality exception |
| `fact_contract_event` | fact (optional) | one row per published record / amendment |
| `dim_unspsc_segment` | lookup (optional) | UNSPSC segment names |

Column types (Power Query > Transform):

* Dates -> **Date**: `fact_contract[award_date]`, `[start_date]`, `[end_date]`, `[first_publication_date]`,
  `[last_amendment_date]`, `dim_date[date]`, `dim_date[month_start]`.
* `final_value`, `original_amount`, `value_change` -> **Fixed decimal number**; `growth_pct` -> Decimal number.
* Flags (`has_original_record`, `growth_eligible`, `multi_category`, ...) -> Whole number.
* Leave `award_month` (text) alone and use `dim_date[month_start]` for monthly axes.

## 2. Relationships (all many-to-one, single direction)

```
fact_contract[supplier_id]      -> dim_supplier[supplier_id]
fact_contract[category_id]      -> dim_category[category_id]
fact_contract[department_id]    -> dim_department[department_id]
fact_contract[award_date]       -> dim_date[date]
dq_issue[contract_number]       -> fact_contract[contract_number]
fact_contract_event[contract_number] -> fact_contract[contract_number]
```

Mark `dim_date` as the date table (`Table tools > Mark as date table`, column `date`).
Sort `dim_date[month_name]` by `dim_date[month]`.

## 3. Disconnected helper table (mega-contract switch)

Nine contracts of $1B+ make up 47% of all valued spend, so a toggle is essential.
`Modeling > New table`:

```dax
Value Mode = DATATABLE("Mode", STRING, {{"All contracts"}, {"Excl. contracts over $100M"}})
```

## 4. Measures

Create a `_Measures` table (Enter data, one blank column, then hide the column) and add:

```dax
-- Counts and value ---------------------------------------------------------
Contracts = COUNTROWS ( fact_contract )

Valued Contracts =
CALCULATE ( COUNTROWS ( fact_contract ), fact_contract[final_value] > 0 )

Zero Value Contracts =
CALCULATE ( COUNTROWS ( fact_contract ), fact_contract[final_value] = 0 )

Awarded Value =
CALCULATE ( SUM ( fact_contract[final_value] ), fact_contract[final_value] > 0 )

Awarded Value Excl Mega =
CALCULATE (
    SUM ( fact_contract[final_value] ),
    fact_contract[final_value] > 0,
    fact_contract[final_value] < 100000000
)

Awarded Value (Selected) =
IF (
    SELECTEDVALUE ( 'Value Mode'[Mode], "All contracts" ) = "All contracts",
    [Awarded Value],
    [Awarded Value Excl Mega]
)

Avg Valued Contract = DIVIDE ( [Awarded Value], [Valued Contracts] )

Distinct Suppliers = DISTINCTCOUNT ( fact_contract[supplier_id] )

-- Time intelligence ----------------------------------------------------------
Awarded Value PY =
CALCULATE ( [Awarded Value (Selected)], SAMEPERIODLASTYEAR ( dim_date[date] ) )

Awarded Value YoY % =
DIVIDE ( [Awarded Value (Selected)] - [Awarded Value PY], [Awarded Value PY] )

Awarded Value T12M =
CALCULATE (
    [Awarded Value (Selected)],
    DATESINPERIOD ( dim_date[date], MAX ( dim_date[date] ), -12, MONTH )
)

Contracts 3M Avg =
AVERAGEX (
    DATESINPERIOD ( dim_date[month_start], MAX ( dim_date[month_start] ), -3, MONTH ),
    CALCULATE ( [Contracts] )
)

-- Sourcing --------------------------------------------------------------------
Competitive Value =
CALCULATE ( [Awarded Value], fact_contract[sourcing_type] = "Competitive" )

Non-Competitive Value =
CALCULATE ( [Awarded Value], fact_contract[sourcing_type] = "Non-competitive" )

Competitive Share (Reported) =
DIVIDE ( [Competitive Value], [Competitive Value] + [Non-Competitive Value] )

-- Suppliers -------------------------------------------------------------------
Supplier Rank =
RANKX ( ALLSELECTED ( dim_supplier ), [Awarded Value (Selected)], , DESC, Skip )

Awarded Value (Top 15) =
IF ( [Supplier Rank] <= 15, [Awarded Value (Selected)] )

Supplier Share =
DIVIDE (
    [Awarded Value (Selected)],
    CALCULATE ( [Awarded Value (Selected)], ALLSELECTED ( dim_supplier ) )
)

Top 10 Supplier Share =
VAR Top10 = TOPN ( 10, ALLSELECTED ( dim_supplier ), [Awarded Value (Selected)], DESC )
RETURN
    DIVIDE (
        CALCULATE ( [Awarded Value (Selected)], Top10 ),
        CALCULATE ( [Awarded Value (Selected)], ALLSELECTED ( dim_supplier ) )
    )

-- Herfindahl-Hirschman Index of supplier concentration (0-10,000)
Supplier HHI =
VAR Total = CALCULATE ( [Awarded Value (Selected)], ALLSELECTED ( dim_supplier ) )
RETURN
    SUMX (
        ALLSELECTED ( dim_supplier ),
        VAR s = DIVIDE ( [Awarded Value (Selected)], Total )
        RETURN s * s * 10000
    )

-- Contract changes after award ----------------------------------------------
Amended Contracts =
CALCULATE ( COUNTROWS ( fact_contract ), fact_contract[n_amendments] > 0 )

% Contracts Amended = DIVIDE ( [Amended Contracts], [Contracts] )

Growth-Eligible Contracts =
CALCULATE ( COUNTROWS ( fact_contract ), fact_contract[growth_eligible] = 1 )

Contracts With Value Increase =
CALCULATE (
    COUNTROWS ( fact_contract ),
    fact_contract[growth_eligible] = 1,
    fact_contract[value_change] > 0.5
)

% Increased = DIVIDE ( [Contracts With Value Increase], [Growth-Eligible Contracts] )

Total Value Increase =
CALCULATE (
    SUM ( fact_contract[value_change] ),
    fact_contract[growth_eligible] = 1,
    fact_contract[value_change] > 0.5
)

Original Value (Eligible) =
CALCULATE ( SUM ( fact_contract[original_amount] ), fact_contract[growth_eligible] = 1 )

Net Change % of Original =
DIVIDE (
    CALCULATE ( SUM ( fact_contract[value_change] ), fact_contract[growth_eligible] = 1 ),
    [Original Value (Eligible)]
)

-- Data quality ----------------------------------------------------------------
DQ Exceptions = COUNTROWS ( dq_issue )
Contracts With Any Issue = DISTINCTCOUNT ( dq_issue[contract_number] )
% Contracts With Issue = DIVIDE ( [Contracts With Any Issue], [Contracts] )
```

> Why `Awarded Value (Top 15)` instead of a Top N visual filter: a Top N filter on
> the visual changes what `ALLSELECTED` returns, so the shares would be computed
> against the top 15 only. Filtering on a measure ("is not blank") does not.

Format `% ...`, `Share`, `YoY %` measures as percentages; `Awarded Value*` as
Currency (CAD) with display units in millions.

## 5. Pages

Global slicers (sync across pages): **Fiscal year** (`dim_date[fiscal_year]`),
**Value Mode**, **Category**, **Supplier region** (`dim_supplier[region]`),
**Client department**, **Procurement category** (`fact_contract[procurement_category]`).

### Page 1 - Executive overview
* Cards: `Awarded Value T12M`, `Contracts`, `Distinct Suppliers`, `Competitive Share (Reported)`, `Top 10 Supplier Share`.
* Combo chart by `dim_date[month_start]`: columns = `Awarded Value (Selected)`, line = `Contracts 3M Avg`.
* Bar chart: `Awarded Value (Selected)` by `dim_category[category_name]` (sorted descending).
* Filled map or bar: `Awarded Value (Selected)` by `dim_supplier[region]`.
* Footnote text box: *"Awards are posted months after the award date; the most recent months are provisional."*

### Page 2 - Suppliers and concentration
* Pareto: columns = `Awarded Value (Top 15)` by `dim_supplier[supplier_name]` (sorted by value), tooltip = `Supplier Share`.
* Table: category, `Awarded Value (Selected)`, `Distinct Suppliers`, `Top 10 Supplier Share`, `Supplier HHI` (conditional-format HHI: > 2,500 red).
* Donut: `Awarded Value (Selected)` by `dim_supplier[size_band]` (small / medium / large / unknown).

### Page 3 - Sourcing governance
* 100% stacked column by `dim_date[fiscal_year]`: `Awarded Value` by `fact_contract[sourcing_type]`.
* Bar: non-competitive value by `fact_contract[limited_tendering_reason]` (filter `sourcing_type = Non-competitive`).
* Matrix: category x `Competitive Share (Reported)` with conditional-format colour scale.

### Page 4 - Contract changes after award
* Cards: `% Contracts Amended`, `% Increased`, `Total Value Increase`, `Net Change % of Original`.
* Table (top 25 by `value_change`): contract number, title, supplier, `original_amount`, `final_value`, `value_change`, `growth_pct`, `n_amendments`; filter `growth_eligible = 1`.
* Note box: *"Stand-alone contracts with a visible original record; standing offers and supply arrangements excluded."*

### Page 5 - Data quality
* Bar: `DQ Exceptions` by `dq_issue[issue_type]`; card `% Contracts With Issue`.
* Text box listing the three most material caveats (late postings, $0-value standing offers, UNSPSC codes follow the buyer's entry).

## 6. Design notes

* One accent colour for the measure of interest, grey for context; keep all value axes in millions with a "CAD" axis title.
* Show the mega-contract switch prominently - without it the Davie icebreaker contract (about $13B) flattens every other bar.
* Add a tooltip page on supplier bars with their contracts, region and size band.
