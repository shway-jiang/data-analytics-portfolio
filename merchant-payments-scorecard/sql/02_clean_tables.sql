-- =============================================================================
-- 02  CLEAN REPORTING TABLES
-- Fixes the issues found in 01_data_quality.sql and adds the business rules
-- (revenue, service level) in one place, so every report uses the same logic.
-- Business rules are documented in docs/metric_definitions.md.
-- =============================================================================

DROP TABLE IF EXISTS merchants;
CREATE TABLE merchants AS
WITH ranked AS (
    -- duplicates can differ slightly (e.g. one copy is missing the province),
    -- so keep the most complete copy of each merchant
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY merchant_id
               ORDER BY (province IS NULL OR TRIM(province) = '')   -- complete rows first
           ) AS rn
    FROM raw_merchants
)
SELECT
    merchant_id,
    DATE(application_date)                         AS application_date,
    sales_channel,
    CASE
        WHEN LOWER(TRIM(industry)) IN ('restaurant', 'restaurants') THEN 'Restaurants'
        WHEN LOWER(TRIM(industry)) = 'e-commerce'                   THEN 'E-commerce'
        ELSE TRIM(industry)
    END                                            AS industry,
    COALESCE(NULLIF(TRIM(province), ''), 'Unknown') AS province,
    product,
    pricing_plan,
    application_status,
    DATE(decision_date)                            AS decision_date,
    DATE(first_transaction_date)                   AS first_transaction_date,
    DATE(closed_date)                              AS closed_date,
    -- onboarding timings (Snowflake: DATEDIFF('day', a, b))
    CAST(julianday(decision_date) - julianday(application_date) AS INTEGER)          AS days_to_decision,
    CAST(julianday(first_transaction_date) - julianday(decision_date) AS INTEGER)    AS days_to_first_txn,
    SUBSTR(application_date, 1, 7)                 AS application_month,
    SUBSTR(first_transaction_date, 1, 7)           AS activation_month,
    SUBSTR(closed_date, 1, 7)                      AS closed_month
FROM ranked
WHERE rn = 1;


DROP TABLE IF EXISTS monthly_volume;
CREATE TABLE monthly_volume AS
WITH deduped AS (
    SELECT DISTINCT * FROM raw_monthly_volume
)
SELECT
    v.merchant_id,
    v.month,
    v.card_type,
    v.attempted_txns,
    v.approved_txns,
    v.approved_volume,
    v.refund_volume,
    v.chargeback_count,
    -- net revenue rule: margin kept on approved volume, by pricing plan and card type
    ROUND(v.approved_volume *
        CASE
            WHEN v.card_type = 'Amex'                                      THEN 0.0025
            WHEN m.pricing_plan = 'Flat Rate'        AND v.card_type = 'Interac Debit' THEN 0.0040
            WHEN m.pricing_plan = 'Flat Rate'                              THEN 0.0085
            WHEN m.pricing_plan = 'Interchange Plus' AND v.card_type = 'Interac Debit' THEN 0.0015
            ELSE 0.0030
        END, 2)                                    AS processing_revenue
FROM deduped v
JOIN merchants m USING (merchant_id);


-- one row per merchant per active month, with the monthly platform fee
DROP TABLE IF EXISTS merchant_months;
CREATE TABLE merchant_months AS
SELECT
    v.merchant_id,
    v.month,
    m.sales_channel,
    m.industry,
    m.product,
    m.pricing_plan,
    m.province,
    SUM(v.attempted_txns)      AS attempted_txns,
    SUM(v.approved_txns)       AS approved_txns,
    SUM(v.approved_volume)     AS approved_volume,
    SUM(v.refund_volume)       AS refund_volume,
    SUM(v.chargeback_count)    AS chargeback_count,
    SUM(CASE WHEN v.card_type <> 'Interac Debit' THEN v.approved_txns ELSE 0 END) AS credit_txns,
    SUM(v.processing_revenue)  AS processing_revenue,
    CASE m.product
        WHEN 'Countertop Terminal' THEN 25
        WHEN 'Mobile POS'          THEN 15
        WHEN 'Online Gateway'      THEN 20
    END                        AS platform_fee
FROM monthly_volume v
JOIN merchants m USING (merchant_id)
GROUP BY v.merchant_id, v.month;


DROP TABLE IF EXISTS support_tickets;
CREATE TABLE support_tickets AS
SELECT DISTINCT
    t.ticket_id,
    t.merchant_id,
    t.opened_at,
    t.resolved_at,
    SUBSTR(t.opened_at, 1, 7)   AS opened_month,
    t.category,
    t.contact_channel,
    t.csat_score,
    m.product,
    -- Snowflake: DATEDIFF('minute', opened_at, resolved_at) / 60.0
    ROUND((julianday(t.resolved_at) - julianday(t.opened_at)) * 24, 1) AS resolution_hours,
    CASE
        WHEN t.resolved_at IS NULL           THEN 'Open'
        WHEN t.resolved_at < t.opened_at     THEN 'Invalid timestamp'
        ELSE 'Resolved'
    END                                       AS ticket_status
FROM raw_support_tickets t
LEFT JOIN merchants m USING (merchant_id);
