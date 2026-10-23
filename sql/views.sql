-- KPI views. "Spend" = final cumulative contract value (CAD) of contracts with
-- a value above zero, attributed to the month the contract was awarded.
-- Standing offers / supply arrangements usually carry no value ($0), so they
-- are counted as contracts but contribute no spend.

DROP VIEW IF EXISTS v_valued;
DROP VIEW IF EXISTS v_spend_by_category;
DROP VIEW IF EXISTS v_supplier_pareto;
DROP VIEW IF EXISTS v_monthly_spend;
DROP VIEW IF EXISTS v_sourcing_mix;
DROP VIEW IF EXISTS v_competitive_by_fy;
DROP VIEW IF EXISTS v_limited_tendering;
DROP VIEW IF EXISTS v_amendment_summary;
DROP VIEW IF EXISTS v_amendment_by_category;
DROP VIEW IF EXISTS v_regional_spend;
DROP VIEW IF EXISTS v_supplier_size_mix;
DROP VIEW IF EXISTS v_category_concentration;
DROP VIEW IF EXISTS v_department_spend;
DROP VIEW IF EXISTS v_dq_summary;

-- Base view: valued contracts joined to their dimensions
CREATE VIEW v_valued AS
SELECT f.*,
       c.category_name,
       s.supplier_name,
       s.region      AS supplier_region,
       s.country     AS supplier_country,
       s.size_band   AS supplier_size_band,
       d.department_name
FROM fact_contract f
JOIN dim_category   c ON c.category_id   = f.category_id
JOIN dim_supplier   s ON s.supplier_id   = f.supplier_id
JOIN dim_department d ON d.department_id = f.department_id
WHERE f.final_value > 0;

-- Spend by business category (with and without >$100M mega-contracts)
CREATE VIEW v_spend_by_category AS
SELECT category_name,
       COUNT(*)                                                    AS n_contracts,
       SUM(final_value)                                            AS total_value,
       ROUND(100.0 * SUM(final_value) / SUM(SUM(final_value)) OVER (), 2) AS share_pct,
       AVG(final_value)                                            AS avg_value,
       SUM(CASE WHEN final_value < 100000000 THEN final_value ELSE 0 END) AS value_excl_over_100m,
       COUNT(DISTINCT supplier_id)                                 AS n_suppliers
FROM v_valued
GROUP BY category_name
ORDER BY total_value DESC;

-- Supplier ranking with cumulative share (Pareto)
CREATE VIEW v_supplier_pareto AS
WITH s AS (
    SELECT supplier_id, supplier_name, supplier_region,
           COUNT(*) AS n_contracts, SUM(final_value) AS total_value
    FROM v_valued
    GROUP BY supplier_id
)
SELECT RANK() OVER (ORDER BY total_value DESC)                       AS supplier_rank,
       supplier_id, supplier_name, supplier_region, n_contracts, total_value,
       ROUND(100.0 * total_value / SUM(total_value) OVER (), 2)      AS share_pct,
       ROUND(100.0 * SUM(total_value) OVER (ORDER BY total_value DESC
             ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
             / SUM(total_value) OVER (), 2)                           AS cumulative_share_pct
FROM s
ORDER BY total_value DESC;

-- Monthly awards (contracts with an award date only) + 3-month moving average
CREATE VIEW v_monthly_spend AS
SELECT award_month,
       COUNT(*)                                                           AS n_contracts,
       SUM(CASE WHEN final_value > 0 THEN 1 ELSE 0 END)                   AS n_valued_contracts,
       SUM(CASE WHEN final_value > 0 THEN final_value ELSE 0 END)         AS total_value,
       SUM(CASE WHEN final_value > 0 AND final_value < 100000000
                THEN final_value ELSE 0 END)                              AS value_excl_over_100m,
       AVG(COUNT(*)) OVER (ORDER BY award_month
                           ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)      AS n_contracts_3m_avg
FROM fact_contract
WHERE award_month IS NOT NULL
GROUP BY award_month
ORDER BY award_month;

-- Sourcing mix: competitive vs non-competitive
CREATE VIEW v_sourcing_mix AS
SELECT sourcing_type,
       COUNT(*)                                                           AS n_contracts,
       SUM(final_value)                                                   AS total_value,
       ROUND(100.0 * SUM(final_value) / SUM(SUM(final_value)) OVER (), 2) AS share_of_value_pct
FROM v_valued
GROUP BY sourcing_type
ORDER BY total_value DESC;

-- Competitive share of *reported* value, by fiscal year
-- (excludes advance-notice awards and contracts with no method reported)
CREATE VIEW v_competitive_by_fy AS
SELECT fiscal_year,
       SUM(CASE WHEN sourcing_type = 'Competitive'     THEN final_value ELSE 0 END) AS competitive_value,
       SUM(CASE WHEN sourcing_type = 'Non-competitive' THEN final_value ELSE 0 END) AS non_competitive_value,
       ROUND(100.0 * SUM(CASE WHEN sourcing_type = 'Competitive' THEN final_value ELSE 0 END)
             / NULLIF(SUM(CASE WHEN sourcing_type IN ('Competitive', 'Non-competitive')
                               THEN final_value ELSE 0 END), 0), 2)               AS competitive_share_pct,
       SUM(CASE WHEN sourcing_type = 'Competitive'     THEN 1 ELSE 0 END)         AS competitive_contracts,
       SUM(CASE WHEN sourcing_type = 'Non-competitive' THEN 1 ELSE 0 END)         AS non_competitive_contracts
FROM v_valued
WHERE fiscal_year IS NOT NULL
GROUP BY fiscal_year
ORDER BY fiscal_year;

-- Why contracts were not competed
CREATE VIEW v_limited_tendering AS
SELECT COALESCE(limited_tendering_reason, 'Not stated') AS reason,
       COUNT(*)                                          AS n_contracts,
       SUM(final_value)                                  AS total_value
FROM v_valued
WHERE sourcing_type = 'Non-competitive'
GROUP BY 1
ORDER BY total_value DESC;

-- Value change after award, stand-alone contracts with a visible original record
CREATE VIEW v_amendment_summary AS
WITH inc AS (
    SELECT growth_pct,
           ROW_NUMBER() OVER (ORDER BY growth_pct) AS rn,
           COUNT(*)     OVER ()                    AS cnt
    FROM fact_contract
    WHERE growth_eligible = 1 AND value_change > 0.5
)
SELECT
    (SELECT COUNT(*) FROM fact_contract)                                              AS all_contracts,
    (SELECT COUNT(*) FROM fact_contract WHERE n_amendments > 0)                       AS amended_contracts,
    (SELECT COUNT(*) FROM fact_contract WHERE growth_eligible = 1)                    AS eligible_contracts,
    (SELECT COUNT(*) FROM fact_contract WHERE growth_eligible = 1 AND value_change >  0.5) AS increased,
    (SELECT COUNT(*) FROM fact_contract WHERE growth_eligible = 1 AND value_change < -0.5) AS decreased,
    (SELECT COUNT(*) FROM fact_contract WHERE growth_eligible = 1 AND ABS(value_change) <= 0.5) AS unchanged,
    ROUND(100.0 * (SELECT COUNT(*) FROM fact_contract WHERE growth_eligible = 1 AND value_change > 0.5)
          / NULLIF((SELECT COUNT(*) FROM fact_contract WHERE growth_eligible = 1), 0), 1) AS pct_increased,
    (SELECT SUM(original_amount) FROM fact_contract WHERE growth_eligible = 1)        AS original_value,
    (SELECT SUM(value_change) FROM fact_contract WHERE growth_eligible = 1 AND value_change > 0.5) AS total_increase,
    (SELECT AVG(growth_pct) FROM inc WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2))      AS median_growth_when_increased;

CREATE VIEW v_amendment_by_category AS
SELECT c.category_name,
       COUNT(*)                                                         AS eligible_contracts,
       SUM(CASE WHEN f.value_change >  0.5 THEN 1 ELSE 0 END)           AS increased,
       ROUND(100.0 * SUM(CASE WHEN f.value_change > 0.5 THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_increased,
       SUM(CASE WHEN f.value_change > 0.5 THEN f.value_change ELSE 0 END) AS total_increase
FROM fact_contract f
JOIN dim_category c ON c.category_id = f.category_id
WHERE f.growth_eligible = 1
GROUP BY c.category_name
ORDER BY total_increase DESC;

-- Supplier geography
CREATE VIEW v_regional_spend AS
SELECT supplier_region                                                    AS region,
       COUNT(*)                                                           AS n_contracts,
       COUNT(DISTINCT supplier_id)                                        AS n_suppliers,
       SUM(final_value)                                                   AS total_value,
       ROUND(100.0 * SUM(final_value) / SUM(SUM(final_value)) OVER (), 2) AS share_pct
FROM v_valued
GROUP BY supplier_region
ORDER BY total_value DESC;

-- Supplier size (Innovation Canada bands from the employee-count field)
CREATE VIEW v_supplier_size_mix AS
SELECT supplier_size_band                                                 AS size_band,
       COUNT(*)                                                           AS n_contracts,
       COUNT(DISTINCT supplier_id)                                        AS n_suppliers,
       SUM(final_value)                                                   AS total_value,
       ROUND(100.0 * SUM(final_value) / SUM(SUM(final_value)) OVER (), 2) AS share_pct
FROM v_valued
GROUP BY supplier_size_band
ORDER BY total_value DESC;

-- Supplier concentration inside each category (HHI: 0-10,000; >2,500 = highly concentrated)
CREATE VIEW v_category_concentration AS
WITH ss AS (
    SELECT category_name, supplier_id, SUM(final_value) AS v
    FROM v_valued
    GROUP BY category_name, supplier_id
), tot AS (
    SELECT category_name, SUM(v) AS t, COUNT(*) AS n_suppliers, MAX(v) AS top_v
    FROM ss
    GROUP BY category_name
)
SELECT ss.category_name,
       tot.n_suppliers,
       tot.t                                                      AS total_value,
       ROUND(100.0 * tot.top_v / tot.t, 1)                        AS top_supplier_share_pct,
       ROUND(SUM((ss.v * 100.0 / tot.t) * (ss.v * 100.0 / tot.t)), 0) AS hhi
FROM ss
JOIN tot ON tot.category_name = ss.category_name
GROUP BY ss.category_name
ORDER BY hhi DESC;

CREATE VIEW v_department_spend AS
SELECT department_name,
       COUNT(*)         AS n_contracts,
       SUM(final_value) AS total_value
FROM v_valued
GROUP BY department_name
ORDER BY total_value DESC;

CREATE VIEW v_dq_summary AS
SELECT issue_type,
       COUNT(*) AS n_contracts,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM fact_contract), 2) AS pct_of_contracts
FROM dq_issue
GROUP BY issue_type
ORDER BY n_contracts DESC;
