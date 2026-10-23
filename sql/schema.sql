-- Star schema for the procurement spend database (SQLite).
-- Dates are stored as ISO-8601 text (YYYY-MM-DD). Amounts are CAD.

DROP VIEW IF EXISTS v_valued;
DROP TABLE IF EXISTS dq_issue;
DROP TABLE IF EXISTS fact_contract_event;
DROP TABLE IF EXISTS fact_contract;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_unspsc_segment;
DROP TABLE IF EXISTS dim_department;
DROP TABLE IF EXISTS dim_supplier;
DROP TABLE IF EXISTS dim_category;

CREATE TABLE dim_category (
    category_id    INTEGER PRIMARY KEY,
    category_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_unspsc_segment (
    segment_code   TEXT PRIMARY KEY,
    segment_name   TEXT NOT NULL,
    category_name  TEXT
);

CREATE TABLE dim_department (
    department_id    INTEGER PRIMARY KEY,
    department_name  TEXT NOT NULL UNIQUE
);

CREATE TABLE dim_supplier (
    supplier_id            INTEGER PRIMARY KEY,
    supplier_key           TEXT NOT NULL UNIQUE,   -- normalised name used for matching
    supplier_name          TEXT NOT NULL,          -- display name
    n_legal_name_variants  INTEGER NOT NULL,       -- legal-name spellings merged into this supplier
    country                TEXT,
    province               TEXT,
    region                 TEXT,                   -- province (Canada) or country (foreign)
    city                   TEXT,
    size_band              TEXT                    -- Small / Medium / Large / Unknown
);

CREATE TABLE dim_date (
    date           TEXT PRIMARY KEY,
    year           INTEGER NOT NULL,
    quarter        INTEGER NOT NULL,
    month          INTEGER NOT NULL,
    month_name     TEXT NOT NULL,
    year_month     TEXT NOT NULL,                  -- e.g. 2026-03
    month_start    TEXT NOT NULL,                  -- first day of the month
    fiscal_year    TEXT NOT NULL                   -- Government of Canada FY (Apr-Mar)
);

-- One row per contract (amendment history collapsed).
CREATE TABLE fact_contract (
    contract_number           TEXT PRIMARY KEY,
    title                     TEXT,
    supplier_id               INTEGER NOT NULL REFERENCES dim_supplier(supplier_id),
    category_id               INTEGER NOT NULL REFERENCES dim_category(category_id),
    department_id             INTEGER NOT NULL REFERENCES dim_department(department_id),
    category_method           TEXT,                -- UNSPSC / Keyword fallback / Unclassified
    unspsc_primary            TEXT,
    unspsc_segment            TEXT,
    multi_category            INTEGER,             -- 1 if UNSPSC codes span several segments
    procurement_category      TEXT,                -- Goods / Services / Construction / ...
    instrument_type           TEXT,
    procurement_method        TEXT,
    sourcing_type             TEXT,                -- Competitive / Non-competitive / ...
    limited_tendering_reason  TEXT,
    status                    TEXT,
    delivery_region           TEXT,
    award_date                TEXT,
    award_month               TEXT,
    fiscal_year               TEXT,
    start_date                TEXT,
    end_date                  TEXT,
    first_publication_date    TEXT,
    last_amendment_date       TEXT,
    publication_lag_days      INTEGER,
    n_records                 INTEGER NOT NULL,
    n_amendments              INTEGER NOT NULL,
    has_original_record       INTEGER NOT NULL,
    original_amount           REAL,
    final_value               REAL,
    value_class               TEXT,                -- Valued / No value ($0) / Negative (adjustment)
    value_band                TEXT,
    growth_eligible           INTEGER NOT NULL,
    value_change              REAL,
    growth_pct                REAL,
    end_date_placeholder      INTEGER NOT NULL,
    end_before_start          INTEGER NOT NULL
);

-- One row per published record (original + each amendment).
CREATE TABLE fact_contract_event (
    contract_number   TEXT NOT NULL REFERENCES fact_contract(contract_number),
    amendment_number  TEXT,
    amendment_seq     INTEGER NOT NULL,
    amendment_type    TEXT,
    publication_date  TEXT,
    amendment_date    TEXT,
    contract_amount   REAL,
    total_value       REAL
);

CREATE TABLE dq_issue (
    contract_number  TEXT NOT NULL,
    issue_type       TEXT NOT NULL
);

CREATE INDEX ix_fc_supplier ON fact_contract(supplier_id);
CREATE INDEX ix_fc_category ON fact_contract(category_id);
CREATE INDEX ix_fc_month    ON fact_contract(award_month);
CREATE INDEX ix_fce_contract ON fact_contract_event(contract_number);
CREATE INDEX ix_dq_type ON dq_issue(issue_type);
