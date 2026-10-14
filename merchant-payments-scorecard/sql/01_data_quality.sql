-- =============================================================================
-- 01  DATA QUALITY CHECKS
-- Run on the raw tables before any reporting. Each check returns one row:
-- the check name, how many records fail it, and what we do about it.
-- Written for SQLite; notes show the Snowflake equivalent where it differs.
-- =============================================================================

-- name: data_quality_checks
WITH
merchant_dupes AS (
    SELECT COUNT(*) - COUNT(DISTINCT merchant_id) AS n FROM raw_merchants
),
missing_province AS (
    SELECT COUNT(*) AS n FROM raw_merchants WHERE province IS NULL OR TRIM(province) = ''
),
bad_industry_labels AS (
    -- labels that don't match the approved list exactly
    SELECT COUNT(*) AS n
    FROM raw_merchants
    WHERE industry NOT IN ('Restaurants', 'Retail', 'Grocery & Convenience', 'Health & Beauty',
                           'Professional Services', 'Automotive', 'Hospitality', 'E-commerce')
),
activation_before_approval AS (
    SELECT COUNT(*) AS n
    FROM raw_merchants
    WHERE first_transaction_date < decision_date
),
declined_but_transacting AS (
    SELECT COUNT(*) AS n
    FROM raw_merchants
    WHERE application_status = 'Declined' AND first_transaction_date IS NOT NULL
),
volume_dupes AS (
    SELECT COALESCE(SUM(cnt - 1), 0) AS n
    FROM (
        SELECT COUNT(*) AS cnt
        FROM raw_monthly_volume
        GROUP BY merchant_id, month, card_type
        HAVING COUNT(*) > 1
    )
),
volume_orphans AS (
    -- volume rows whose merchant isn't in the merchant table
    SELECT COUNT(*) AS n
    FROM raw_monthly_volume v
    LEFT JOIN (SELECT DISTINCT merchant_id FROM raw_merchants) m USING (merchant_id)
    WHERE m.merchant_id IS NULL
),
volume_logic AS (
    SELECT COUNT(*) AS n
    FROM raw_monthly_volume
    WHERE approved_txns > attempted_txns OR approved_volume < 0 OR refund_volume > approved_volume
),
ticket_time_errors AS (
    SELECT COUNT(*) AS n
    FROM raw_support_tickets
    WHERE resolved_at < opened_at          -- Snowflake: same comparison on TIMESTAMP columns
),
ticket_csat_range AS (
    SELECT COUNT(*) AS n FROM raw_support_tickets WHERE csat_score NOT BETWEEN 1 AND 5
)
SELECT 'Duplicate merchant records'            AS check_name, n AS failing_rows, 'Keep one copy'                      AS action FROM merchant_dupes
UNION ALL SELECT 'Merchant missing province',          n, 'Report as "Unknown"'                FROM missing_province
UNION ALL SELECT 'Industry label not on approved list', n, 'Map to the standard label'          FROM bad_industry_labels
UNION ALL SELECT 'First transaction before approval',  n, 'Investigate if > 0'                 FROM activation_before_approval
UNION ALL SELECT 'Declined merchant with transactions', n, 'Investigate if > 0'                FROM declined_but_transacting
UNION ALL SELECT 'Duplicate monthly volume rows',      n, 'Keep one copy'                      FROM volume_dupes
UNION ALL SELECT 'Volume rows with unknown merchant',  n, 'Investigate if > 0'                 FROM volume_orphans
UNION ALL SELECT 'Volume rows failing logic checks',   n, 'Investigate if > 0'                 FROM volume_logic
UNION ALL SELECT 'Ticket resolved before opened',      n, 'Exclude from service-level metrics' FROM ticket_time_errors
UNION ALL SELECT 'CSAT score outside 1-5',             n, 'Exclude from CSAT'                  FROM ticket_csat_range;
