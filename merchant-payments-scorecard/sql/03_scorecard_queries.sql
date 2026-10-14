-- =============================================================================
-- 03  SCORECARD QUERIES
-- Each query starts with "-- name: <name>". The refresh script runs them in
-- order and saves each result to outputs/<name>.csv.
-- Reporting period: Jan 2025 - Jun 2026. Metric rules: docs/metric_definitions.md
-- =============================================================================


-- name: monthly_scorecard
-- One row per month for the leadership scorecard, with month-over-month change.
WITH volume AS (
    SELECT
        month,
        COUNT(DISTINCT CASE WHEN approved_txns > 0 THEN merchant_id END) AS active_merchants,
        SUM(attempted_txns)                       AS attempted_txns,
        SUM(approved_txns)                        AS approved_txns,
        SUM(approved_volume)                      AS approved_volume,
        SUM(refund_volume)                        AS refund_volume,
        SUM(chargeback_count)                     AS chargebacks,
        SUM(credit_txns)                          AS credit_txns,
        SUM(processing_revenue + platform_fee)    AS net_revenue
    FROM merchant_months
    GROUP BY month
),
activations AS (
    SELECT activation_month AS month, COUNT(*) AS new_merchants
    FROM merchants WHERE activation_month IS NOT NULL GROUP BY activation_month
),
closures AS (
    SELECT closed_month AS month, COUNT(*) AS closed_merchants
    FROM merchants WHERE closed_month IS NOT NULL GROUP BY closed_month
),
service AS (
    SELECT
        opened_month AS month,
        COUNT(*)                                                         AS tickets,
        AVG(CASE WHEN resolution_hours <= 48 THEN 1.0 ELSE 0.0 END)      AS pct_within_sla,
        AVG(csat_score)                                                  AS avg_csat
    FROM support_tickets
    WHERE ticket_status = 'Resolved'
    GROUP BY opened_month
)
SELECT
    v.month,
    v.active_merchants,
    COALESCE(a.new_merchants, 0)                           AS new_merchants,
    COALESCE(c.closed_merchants, 0)                        AS closed_merchants,
    ROUND(v.approved_volume, 0)                            AS approved_volume,
    ROUND(100.0 * (v.approved_volume / LAG(v.approved_volume) OVER (ORDER BY v.month) - 1), 1) AS volume_mom_pct,
    v.approved_txns,
    ROUND(v.approved_volume / v.approved_txns, 2)          AS avg_ticket,
    ROUND(100.0 * v.approved_txns / v.attempted_txns, 2)   AS approval_rate_pct,
    ROUND(v.net_revenue, 0)                                AS net_revenue,
    ROUND(100.0 * (v.net_revenue / LAG(v.net_revenue) OVER (ORDER BY v.month) - 1), 1)         AS revenue_mom_pct,
    ROUND(v.net_revenue / v.active_merchants, 2)           AS revenue_per_merchant,
    ROUND(100.0 * v.chargebacks / v.credit_txns, 3)        AS chargeback_rate_pct,
    COALESCE(s.tickets, 0)                                 AS resolved_tickets,
    ROUND(100.0 * s.pct_within_sla, 1)                     AS pct_within_48h_sla,
    ROUND(s.avg_csat, 2)                                   AS avg_csat
FROM volume v
LEFT JOIN activations a USING (month)
LEFT JOIN closures   c USING (month)
LEFT JOIN service    s USING (month)
ORDER BY v.month;


-- name: onboarding_by_channel
-- How each sales channel performs from application to a retained, paying merchant.
WITH base AS (
    SELECT
        m.*,
        CASE WHEN application_status = 'Approved' THEN 1 ELSE 0 END                AS is_approved,
        -- activation is judged only on merchants approved 30+ days before period end
        CASE WHEN application_status = 'Approved' AND decision_date <= DATE('2026-06-30', '-30 days')
             THEN 1 ELSE 0 END                                                       AS activation_eligible,
        CASE WHEN days_to_first_txn <= 30 THEN 1 ELSE 0 END                          AS activated_30d,
        -- 6-month retention is judged only on merchants active for 6+ months of the period
        CASE WHEN activation_month <= '2025-12' THEN 1 ELSE 0 END                    AS retention_eligible,
        CASE WHEN closed_date IS NULL
               OR julianday(closed_date) - julianday(first_transaction_date) >= 183
             THEN 1 ELSE 0 END                                                       AS retained_6m
    FROM merchants m
),
median_days AS (
    -- median days from approval to first transaction (Snowflake: MEDIAN())
    SELECT sales_channel, AVG(days_to_first_txn) AS median_days_to_first_txn
    FROM (
        SELECT sales_channel, days_to_first_txn,
               ROW_NUMBER() OVER (PARTITION BY sales_channel ORDER BY days_to_first_txn) AS rn,
               COUNT(*)     OVER (PARTITION BY sales_channel)                            AS cnt
        FROM merchants
        WHERE days_to_first_txn IS NOT NULL
    )
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
    GROUP BY sales_channel
),
revenue AS (
    SELECT sales_channel,
           AVG(processing_revenue + platform_fee) AS revenue_per_active_month
    FROM merchant_months
    GROUP BY sales_channel
)
SELECT
    b.sales_channel,
    COUNT(*)                                                                         AS applications,
    ROUND(100.0 * AVG(b.is_approved), 1)                                             AS approval_rate_pct,
    ROUND(AVG(b.days_to_decision), 1)                                                AS avg_days_to_decision,
    ROUND(100.0 * SUM(b.activated_30d * b.activation_eligible) / SUM(b.activation_eligible), 1) AS activated_within_30d_pct,
    md.median_days_to_first_txn,
    ROUND(100.0 * SUM(b.retained_6m * b.retention_eligible)
              / SUM(CASE WHEN b.retention_eligible = 1 AND b.first_transaction_date IS NOT NULL THEN 1 END), 1)
                                                                                     AS retained_6m_pct,
    ROUND(r.revenue_per_active_month, 2)                                             AS revenue_per_active_month
FROM base b
JOIN median_days md USING (sales_channel)
JOIN revenue r USING (sales_channel)
GROUP BY b.sales_channel
ORDER BY retained_6m_pct DESC;


-- name: activation_speed_vs_retention
-- Do merchants who start processing quickly stay longer?
SELECT
    CASE
        WHEN days_to_first_txn <= 7  THEN '1) 0-7 days'
        WHEN days_to_first_txn <= 14 THEN '2) 8-14 days'
        ELSE                              '3) 15+ days'
    END                                                         AS time_to_first_txn,
    COUNT(*)                                                    AS merchants,
    ROUND(100.0 * AVG(CASE WHEN closed_date IS NULL
                             OR julianday(closed_date) - julianday(first_transaction_date) >= 183
                           THEN 1.0 ELSE 0.0 END), 1)           AS retained_6m_pct
FROM merchants
WHERE first_transaction_date IS NOT NULL
  AND activation_month <= '2025-12'
GROUP BY 1
ORDER BY 1;


-- name: industry_performance
-- Last 6 months (Jan-Jun 2026): which industries drive volume and revenue.
WITH h1 AS (
    SELECT * FROM merchant_months WHERE month BETWEEN '2026-01' AND '2026-06'
),
totals AS (
    SELECT SUM(approved_volume) AS vol, SUM(processing_revenue + platform_fee) AS rev FROM h1
)
SELECT
    industry,
    COUNT(DISTINCT merchant_id)                                        AS active_merchants,
    ROUND(SUM(approved_volume), 0)                                     AS approved_volume,
    ROUND(100.0 * SUM(approved_volume) / t.vol, 1)                     AS volume_share_pct,
    ROUND(SUM(processing_revenue + platform_fee), 0)                   AS net_revenue,
    ROUND(100.0 * SUM(processing_revenue + platform_fee) / t.rev, 1)   AS revenue_share_pct,
    ROUND(SUM(approved_volume) / SUM(approved_txns), 2)                AS avg_ticket,
    ROUND(100.0 * SUM(approved_txns) / SUM(attempted_txns), 2)         AS approval_rate_pct,
    ROUND(100.0 * SUM(chargeback_count) / NULLIF(SUM(credit_txns), 0), 3) AS chargeback_rate_pct,
    ROUND(SUM(processing_revenue + platform_fee) / COUNT(*), 2)        AS revenue_per_merchant_month
FROM h1, totals t
GROUP BY industry
ORDER BY net_revenue DESC;


-- name: product_performance
-- Last 6 months (Jan-Jun 2026): each payment product's revenue, risk and support load.
WITH h1 AS (
    SELECT * FROM merchant_months WHERE month BETWEEN '2026-01' AND '2026-06'
),
tickets AS (
    SELECT product, COUNT(*) AS tickets
    FROM support_tickets
    WHERE opened_month BETWEEN '2026-01' AND '2026-06'
    GROUP BY product
)
SELECT
    h1.product,
    COUNT(DISTINCT h1.merchant_id)                                       AS active_merchants,
    ROUND(SUM(h1.approved_volume), 0)                                    AS approved_volume,
    ROUND(SUM(h1.processing_revenue + h1.platform_fee), 0)               AS net_revenue,
    ROUND(SUM(h1.processing_revenue + h1.platform_fee) / COUNT(*), 2)    AS revenue_per_merchant_month,
    ROUND(100.0 * SUM(h1.approved_txns) / SUM(h1.attempted_txns), 2)     AS approval_rate_pct,
    ROUND(100.0 * SUM(h1.chargeback_count) / SUM(h1.credit_txns), 3)     AS chargeback_rate_pct,
    ROUND(100.0 * t.tickets / COUNT(*), 1)                               AS tickets_per_100_merchant_months
FROM h1
LEFT JOIN tickets t USING (product)
GROUP BY h1.product
ORDER BY net_revenue DESC;


-- name: card_type_mix
-- Card mix for the full period: share of volume vs share of revenue.
WITH totals AS (
    SELECT SUM(approved_volume) AS vol, SUM(processing_revenue) AS rev FROM monthly_volume
)
SELECT
    card_type,
    ROUND(100.0 * SUM(approved_volume) / t.vol, 1)            AS volume_share_pct,
    ROUND(100.0 * SUM(processing_revenue) / t.rev, 1)         AS processing_revenue_share_pct,
    ROUND(100.0 * SUM(approved_txns) / SUM(attempted_txns), 2) AS approval_rate_pct
FROM monthly_volume, totals t
GROUP BY card_type
ORDER BY volume_share_pct DESC;


-- name: service_levels_by_category
-- Service levels by ticket type, comparing normal months with the Mar-Apr 2026 incident.
SELECT
    category,
    CASE WHEN opened_month IN ('2026-03', '2026-04') THEN 'Mar-Apr 2026' ELSE 'Other months' END AS period,
    COUNT(*)                                                        AS resolved_tickets,
    ROUND(AVG(resolution_hours), 1)                                 AS avg_resolution_hours,
    ROUND(100.0 * AVG(CASE WHEN resolution_hours <= 48 THEN 1.0 ELSE 0.0 END), 1) AS pct_within_48h_sla,
    ROUND(AVG(csat_score), 2)                                       AS avg_csat
FROM support_tickets
WHERE ticket_status = 'Resolved'
GROUP BY category, period
ORDER BY category, period DESC;


-- name: slow_ticket_vs_churn
-- Merchants who wait more than 48 hours for a ticket: are they more likely to
-- close their account in the next 3 months? (merchant-months up to Mar 2026,
-- so every row has a full 3 months of follow-up)
WITH slow_months AS (
    SELECT DISTINCT merchant_id, opened_month AS month
    FROM support_tickets
    WHERE ticket_status = 'Resolved' AND resolution_hours > 48
),
mm AS (
    SELECT
        x.merchant_id,
        x.month,
        CASE WHEN s.merchant_id IS NOT NULL THEN 'Had a ticket over 48h' ELSE 'No slow ticket' END AS ticket_experience,
        CASE WHEN m.closed_month >= x.month
              AND m.closed_month <= SUBSTR(DATE(x.month || '-01', '+3 months'), 1, 7)
             THEN 1 ELSE 0 END AS closed_within_3m
    FROM merchant_months x
    JOIN merchants m USING (merchant_id)
    LEFT JOIN slow_months s USING (merchant_id, month)
    WHERE x.month <= '2026-03'
)
SELECT
    ticket_experience,
    COUNT(*)                                   AS merchant_months,
    ROUND(100.0 * AVG(closed_within_3m), 2)    AS closed_within_3_months_pct
FROM mm
GROUP BY ticket_experience
ORDER BY ticket_experience;
