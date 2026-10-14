-- =============================================================================
-- 03  SCORECARD QUERIES
-- Each query starts with "-- name: <name>". The refresh script runs them in
-- order and saves each result to outputs/<name>.csv.
-- Reporting period: Jan 2017 - Aug 2018 (full months only). Amounts in R$.
-- Metric rules: docs/metric_definitions.md
-- =============================================================================


-- name: monthly_scorecard
-- One row per month for the leadership scorecard, with month-over-month change.
WITH sales AS (
    SELECT
        order_month AS month,
        COUNT(*)                                                       AS orders,
        ROUND(100.0 * AVG(is_canceled), 2)                             AS canceled_pct,
        SUM(CASE WHEN is_canceled = 0 THEN merchandise_value END)      AS gmv,
        SUM(CASE WHEN is_canceled = 0 AND merchandise_value IS NOT NULL THEN 1 ELSE 0 END) AS paid_orders,
        SUM(CASE WHEN is_canceled = 0 AND main_payment_type = 'credit_card' THEN amount_paid END)
            / SUM(CASE WHEN is_canceled = 0 THEN amount_paid END)      AS credit_card_share,
        AVG(CASE WHEN is_canceled = 0 AND main_payment_type = 'credit_card' THEN installments END) AS avg_card_installments,
        AVG(delivered_on_time)                                         AS on_time,
        AVG(delivery_days)                                             AS delivery_days,
        AVG(seller_shipped_on_time)                                    AS seller_on_time,
        AVG(review_score)                                              AS avg_review,
        AVG(CASE WHEN review_score IS NOT NULL THEN (review_score <= 2) END) AS low_review
    FROM orders
    WHERE in_period = 1
    GROUP BY order_month
),
seller_months AS (
    SELECT DISTINCT seller_id, order_month AS month
    FROM order_items
    WHERE in_period = 1 AND is_canceled = 0
),
seller_activity AS (
    -- active sellers, and how many of last month's active sellers sold again this month
    SELECT
        cur.month,
        COUNT(*)                                              AS active_sellers,
        SUM(CASE WHEN prev.seller_id IS NOT NULL THEN 1 ELSE 0 END) AS repeat_from_last_month
    FROM seller_months cur
    LEFT JOIN seller_months prev
           ON prev.seller_id = cur.seller_id
          AND prev.month = SUBSTR(DATE(cur.month || '-01', '-1 month'), 1, 7)
    GROUP BY cur.month
),
new_sellers AS (
    SELECT first_sale_month AS month, COUNT(*) AS new_sellers FROM sellers GROUP BY first_sale_month
)
SELECT
    s.month,
    s.orders,
    s.canceled_pct,
    ROUND(s.gmv, 0)                                                    AS gmv,
    ROUND(100.0 * (s.gmv / LAG(s.gmv) OVER (ORDER BY s.month) - 1), 1) AS gmv_mom_pct,
    ROUND(s.gmv / s.paid_orders, 2)                                    AS avg_order_value,
    a.active_sellers,
    COALESCE(n.new_sellers, 0)                                         AS new_sellers,
    ROUND(100.0 * a.repeat_from_last_month / LAG(a.active_sellers) OVER (ORDER BY s.month), 1) AS seller_retention_pct,
    ROUND(s.gmv / a.active_sellers, 0)                                 AS gmv_per_active_seller,
    ROUND(100.0 * s.credit_card_share, 1)                              AS credit_card_share_pct,
    ROUND(s.avg_card_installments, 2)                                  AS avg_card_installments,
    ROUND(100.0 * s.seller_on_time, 1)                                 AS seller_shipped_on_time_pct,
    ROUND(100.0 * s.on_time, 1)                                        AS delivered_on_time_pct,
    ROUND(s.delivery_days, 1)                                          AS avg_delivery_days,
    ROUND(s.avg_review, 2)                                             AS avg_review_score,
    ROUND(100.0 * s.low_review, 1)                                     AS low_review_pct
FROM sales s
JOIN seller_activity a USING (month)
LEFT JOIN new_sellers n USING (month)
ORDER BY s.month;


-- name: payment_methods
-- How each payment method performs: share of sales, speed of approval, cancellations.
WITH base AS (
    SELECT * FROM orders WHERE in_period = 1 AND main_payment_type IS NOT NULL
),
median_approval AS (
    -- median hours to approve payment (Snowflake: MEDIAN(approval_hours))
    SELECT main_payment_type, AVG(approval_hours) AS median_approval_hours
    FROM (
        SELECT main_payment_type, approval_hours,
               ROW_NUMBER() OVER (PARTITION BY main_payment_type ORDER BY approval_hours) AS rn,
               COUNT(*)     OVER (PARTITION BY main_payment_type)                         AS cnt
        FROM base
        WHERE approval_hours IS NOT NULL
    )
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
    GROUP BY main_payment_type
),
totals AS (
    SELECT COUNT(*) AS orders, SUM(amount_paid) AS paid FROM base WHERE is_canceled = 0
)
SELECT
    b.main_payment_type                                                   AS payment_method,
    SUM(1 - b.is_canceled)                                                AS orders,
    ROUND(100.0 * SUM(1 - b.is_canceled) / t.orders, 1)                   AS order_share_pct,
    ROUND(100.0 * SUM(CASE WHEN b.is_canceled = 0 THEN b.amount_paid END) / t.paid, 1) AS value_share_pct,
    ROUND(AVG(CASE WHEN b.is_canceled = 0 THEN b.amount_paid END), 2)     AS avg_amount_paid,
    ROUND(m.median_approval_hours, 1)                                     AS median_hours_to_approve,
    ROUND(100.0 * AVG(b.is_canceled), 2)                                  AS canceled_pct,
    ROUND(AVG(b.review_score), 2)                                         AS avg_review_score
FROM base b, totals t
JOIN median_approval m USING (main_payment_type)
GROUP BY b.main_payment_type
ORDER BY orders DESC;


-- name: card_installments
-- Credit card orders split by number of installments (a key card product in Brazil).
SELECT
    CASE
        WHEN installments = 1  THEN '1) Paid in full'
        WHEN installments <= 3 THEN '2) 2-3 installments'
        WHEN installments <= 6 THEN '3) 4-6 installments'
        WHEN installments <= 10 THEN '4) 7-10 installments'
        ELSE                        '5) 11+ installments'
    END                                                             AS installment_plan,
    COUNT(*)                                                        AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)              AS order_share_pct,
    ROUND(100.0 * SUM(amount_paid) / SUM(SUM(amount_paid)) OVER (), 1) AS value_share_pct,
    ROUND(AVG(amount_paid), 2)                                      AS avg_amount_paid
FROM orders
WHERE in_period = 1 AND is_canceled = 0 AND main_payment_type = 'credit_card'
GROUP BY 1
ORDER BY 1;


-- name: seller_funnel_by_channel
-- Seller acquisition: marketing lead -> signed seller -> first sale, by lead channel.
-- First-sale rate uses only deals won by 30 Jun 2018, so each seller had 2+ months to sell.
WITH median_close AS (
    SELECT origin, AVG(days_to_close) AS median_days_to_close
    FROM (
        SELECT origin, days_to_close,
               ROW_NUMBER() OVER (PARTITION BY origin ORDER BY days_to_close) AS rn,
               COUNT(*)     OVER (PARTITION BY origin)                        AS cnt
        FROM seller_leads WHERE won = 1 AND days_to_close IS NOT NULL
    )
    WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
    GROUP BY origin
)
SELECT
    l.origin                                                         AS lead_channel,
    COUNT(*)                                                         AS leads,
    SUM(l.won)                                                       AS signed_sellers,
    ROUND(100.0 * SUM(l.won) / COUNT(*), 1)                          AS lead_to_signed_pct,
    m.median_days_to_close,
    ROUND(100.0 * SUM(CASE WHEN l.won_date <= '2018-06-30' AND l.first_sale_at IS NOT NULL THEN 1 ELSE 0 END)
               / NULLIF(SUM(CASE WHEN l.won_date <= '2018-06-30' THEN 1 ELSE 0 END), 0), 1) AS signed_with_first_sale_pct,
    ROUND(SUM(l.lifetime_gmv) / NULLIF(SUM(l.won), 0), 0)            AS gmv_per_signed_seller
FROM seller_leads l
LEFT JOIN median_close m USING (origin)
GROUP BY l.origin
ORDER BY leads DESC;


-- name: seller_activation_by_type
-- Which kinds of signed sellers actually start selling? (deals won by 30 Jun 2018)
SELECT
    COALESCE(lead_type, 'unknown')                                  AS seller_type,
    COUNT(*)                                                        AS signed_sellers,
    ROUND(100.0 * AVG(first_sale_at IS NOT NULL), 1)                AS with_first_sale_pct,
    ROUND(AVG(days_won_to_first_sale), 0)                           AS avg_days_to_first_sale,
    ROUND(SUM(lifetime_gmv) / COUNT(*), 0)                          AS gmv_per_signed_seller
FROM seller_leads
WHERE won = 1 AND won_date <= '2018-06-30'
GROUP BY 1
HAVING COUNT(*) >= 10
ORDER BY signed_sellers DESC;


-- name: seller_concentration
-- How concentrated are sales? Sellers ranked into 10 equal groups by GMV.
WITH seller_gmv AS (
    SELECT seller_id, SUM(price) AS gmv
    FROM order_items
    WHERE in_period = 1 AND is_canceled = 0
    GROUP BY seller_id
),
ranked AS (
    SELECT seller_id, gmv, NTILE(10) OVER (ORDER BY gmv DESC) AS decile FROM seller_gmv
)
SELECT
    decile                                                           AS seller_decile,
    COUNT(*)                                                         AS sellers,
    ROUND(SUM(gmv), 0)                                               AS gmv,
    ROUND(100.0 * SUM(gmv) / SUM(SUM(gmv)) OVER (), 1)               AS gmv_share_pct,
    ROUND(100.0 * SUM(SUM(gmv)) OVER (ORDER BY decile) / SUM(SUM(gmv)) OVER (), 1) AS cumulative_share_pct
FROM ranked
GROUP BY decile
ORDER BY decile;


-- name: delivery_vs_review
-- Customer experience: how review scores change when an order arrives late.
SELECT
    CASE
        WHEN delivered_on_time = 1                                         THEN '1) On time'
        WHEN julianday(DATE(d.order_delivered_customer_date)) - julianday(DATE(d.order_estimated_delivery_date)) <= 3 THEN '2) 1-3 days late'
        WHEN julianday(DATE(d.order_delivered_customer_date)) - julianday(DATE(d.order_estimated_delivery_date)) <= 7 THEN '3) 4-7 days late'
        ELSE                                                                    '4) 8+ days late'
    END                                                         AS delivery,
    COUNT(*)                                                    AS orders,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)          AS share_pct,
    ROUND(AVG(o.review_score), 2)                               AS avg_review_score,
    ROUND(100.0 * AVG(CASE WHEN o.review_score IS NOT NULL THEN (o.review_score <= 2) END), 1) AS low_review_pct
FROM orders o
JOIN raw_orders d USING (order_id)
WHERE o.in_period = 1 AND o.delivered_on_time IS NOT NULL
GROUP BY 1
ORDER BY 1;


-- name: late_delivery_cause
-- When an order is late, was the seller late handing it over, or was transit slow?
SELECT
    CASE seller_shipped_on_time WHEN 1 THEN 'Seller shipped on time' ELSE 'Seller shipped late' END AS seller_handoff,
    COUNT(*)                                                    AS delivered_orders,
    ROUND(100.0 * (1 - AVG(delivered_on_time)), 1)              AS late_delivery_pct,
    ROUND(AVG(review_score), 2)                                 AS avg_review_score
FROM orders
WHERE in_period = 1 AND delivered_on_time IS NOT NULL AND seller_shipped_on_time IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC;


-- name: category_performance
-- Top 10 product categories by GMV.
WITH cat AS (
    SELECT
        i.category,
        SUM(i.price)                         AS gmv,
        COUNT(DISTINCT i.order_id)           AS orders,
        COUNT(DISTINCT i.seller_id)          AS sellers,
        AVG(i.price)                         AS avg_item_price
    FROM order_items i
    WHERE i.in_period = 1 AND i.is_canceled = 0
    GROUP BY i.category
),
cat_cx AS (
    SELECT i.category, AVG(o.delivered_on_time) AS on_time, AVG(o.review_score) AS review
    FROM (SELECT DISTINCT order_id, category FROM order_items WHERE in_period = 1 AND is_canceled = 0) i
    JOIN orders o USING (order_id)
    GROUP BY i.category
)
SELECT
    c.category,
    ROUND(c.gmv, 0)                                       AS gmv,
    ROUND(100.0 * c.gmv / (SELECT SUM(gmv) FROM cat), 1)  AS gmv_share_pct,
    c.orders,
    c.sellers,
    ROUND(c.avg_item_price, 2)                            AS avg_item_price,
    ROUND(100.0 * x.on_time, 1)                           AS delivered_on_time_pct,
    ROUND(x.review, 2)                                    AS avg_review_score
FROM cat c
JOIN cat_cx x USING (category)
ORDER BY c.gmv DESC
LIMIT 10;


-- name: delivery_by_state
-- Delivery service by customer state (10 states with the most orders).
SELECT
    customer_state,
    COUNT(*)                                       AS delivered_orders,
    ROUND(AVG(delivery_days), 1)                   AS avg_delivery_days,
    ROUND(100.0 * AVG(delivered_on_time), 1)       AS delivered_on_time_pct,
    ROUND(AVG(review_score), 2)                    AS avg_review_score
FROM orders
WHERE in_period = 1 AND delivered_on_time IS NOT NULL
GROUP BY customer_state
ORDER BY delivered_orders DESC
LIMIT 10;
