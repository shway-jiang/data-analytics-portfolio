-- ============================================================
-- Demo 2: E-commerce conversion funnel & channel analysis
-- Data: Google Merchandise Store GA4 sample (public, free)
--       bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*
--       Covers 2020-11-01 to 2021-01-31 (obfuscated sample data)
-- Run each query separately in the BigQuery sandbox,
-- then Save results -> CSV -> load into Power BI.
-- ============================================================


-- ------------------------------------------------------------
-- Q0. Data check: rows, users and date range (run this first)
-- ------------------------------------------------------------
SELECT
  COUNT(*)                              AS events,
  COUNT(DISTINCT user_pseudo_id)        AS users,
  MIN(PARSE_DATE('%Y%m%d', event_date)) AS first_day,
  MAX(PARSE_DATE('%Y%m%d', event_date)) AS last_day
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`;


-- ------------------------------------------------------------
-- Q1. Overall funnel (users who reached each step)
--     view_item -> add_to_cart -> begin_checkout
--     -> add_shipping_info -> add_payment_info -> purchase
-- ------------------------------------------------------------
WITH steps AS (
  SELECT
    user_pseudo_id,
    MAX(IF(event_name = 'view_item',         1, 0)) AS s1_view_item,
    MAX(IF(event_name = 'add_to_cart',       1, 0)) AS s2_add_to_cart,
    MAX(IF(event_name = 'begin_checkout',    1, 0)) AS s3_begin_checkout,
    MAX(IF(event_name = 'add_shipping_info', 1, 0)) AS s4_add_shipping,
    MAX(IF(event_name = 'add_payment_info',  1, 0)) AS s5_add_payment,
    MAX(IF(event_name = 'purchase',          1, 0)) AS s6_purchase
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  GROUP BY user_pseudo_id
)
SELECT step_order, step, users,
       ROUND(users / FIRST_VALUE(users) OVER (ORDER BY step_order), 4) AS pct_of_viewers,
       ROUND(users / LAG(users) OVER (ORDER BY step_order), 4)         AS pct_of_previous_step
FROM (
  SELECT 1 AS step_order, '1 View item'      AS step, SUM(s1_view_item)      AS users FROM steps UNION ALL
  SELECT 2, '2 Add to cart',     SUM(s2_add_to_cart)    FROM steps UNION ALL
  SELECT 3, '3 Begin checkout',  SUM(s3_begin_checkout) FROM steps UNION ALL
  SELECT 4, '4 Add shipping',    SUM(s4_add_shipping)   FROM steps UNION ALL
  SELECT 5, '5 Add payment',     SUM(s5_add_payment)    FROM steps UNION ALL
  SELECT 6, '6 Purchase',        SUM(s6_purchase)       FROM steps
)
ORDER BY step_order;
-- Note: this counts users who did each step at any time, not a strict
-- in-order path, so later steps can occasionally exceed earlier ones.
-- Mention this in the report.


-- ------------------------------------------------------------
-- Q2. Channel performance (first-touch traffic source per user)
--     users, purchasers, conversion rate, revenue, AOV
-- ------------------------------------------------------------
WITH user_channel AS (
  SELECT
    user_pseudo_id,
    ANY_VALUE(traffic_source.medium) AS medium,
    ANY_VALUE(traffic_source.source) AS source
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  GROUP BY user_pseudo_id
),
purchases AS (
  SELECT
    user_pseudo_id,
    COUNT(DISTINCT ecommerce.transaction_id) AS orders,
    SUM(ecommerce.purchase_revenue_in_usd)   AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  WHERE event_name = 'purchase'
  GROUP BY user_pseudo_id
)
SELECT
  uc.medium,
  COUNT(*)                                        AS users,
  COUNTIF(p.orders > 0)                           AS purchasers,
  ROUND(COUNTIF(p.orders > 0) / COUNT(*), 4)      AS conversion_rate,
  ROUND(SUM(IFNULL(p.revenue, 0)), 2)             AS revenue_usd,
  SUM(IFNULL(p.orders, 0))                        AS orders,
  ROUND(SAFE_DIVIDE(SUM(p.revenue), SUM(p.orders)), 2) AS avg_order_value_usd
FROM user_channel uc
LEFT JOIN purchases p USING (user_pseudo_id)
GROUP BY uc.medium
ORDER BY users DESC;
-- In this sample, values like '<Other>' and '(data deleted)' are
-- obfuscated by Google. Group them as "Unknown" in Power BI.


-- ------------------------------------------------------------
-- Q3. New vs returning users (by session number)
-- ------------------------------------------------------------
WITH events AS (
  SELECT
    user_pseudo_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_id')     AS session_id,
    (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'ga_session_number') AS session_number,
    IF(event_name = 'purchase', 1, 0)                                   AS is_purchase,
    IF(event_name = 'purchase', ecommerce.purchase_revenue_in_usd, 0)   AS revenue
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
),
per_session AS (
  SELECT
    user_pseudo_id, session_id,
    MAX(session_number)  AS session_number,
    MAX(is_purchase)     AS converted,
    SUM(IFNULL(revenue, 0)) AS revenue
  FROM events
  WHERE session_id IS NOT NULL
  GROUP BY user_pseudo_id, session_id
)
SELECT
  IF(session_number = 1, 'New', 'Returning') AS user_type,
  COUNT(*)                                   AS sessions,
  SUM(converted)                             AS converting_sessions,
  ROUND(SUM(converted) / COUNT(*), 4)        AS session_conversion_rate,
  ROUND(SUM(revenue), 2)                     AS revenue_usd
FROM per_session
GROUP BY user_type;


-- ------------------------------------------------------------
-- Q4. Daily trend: users, purchases, revenue
-- ------------------------------------------------------------
SELECT
  PARSE_DATE('%Y%m%d', event_date)                          AS day,
  COUNT(DISTINCT user_pseudo_id)                            AS users,
  COUNT(DISTINCT IF(event_name = 'purchase', ecommerce.transaction_id, NULL)) AS orders,
  ROUND(SUM(IF(event_name = 'purchase', ecommerce.purchase_revenue_in_usd, 0)), 2) AS revenue_usd
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
GROUP BY day
ORDER BY day;


-- ------------------------------------------------------------
-- Q5. Funnel by device (where do mobile vs desktop users drop off?)
-- ------------------------------------------------------------
WITH steps AS (
  SELECT
    user_pseudo_id,
    ANY_VALUE(device.category) AS device,
    MAX(IF(event_name = 'view_item',      1, 0)) AS viewed,
    MAX(IF(event_name = 'add_to_cart',    1, 0)) AS carted,
    MAX(IF(event_name = 'begin_checkout', 1, 0)) AS checkout,
    MAX(IF(event_name = 'purchase',       1, 0)) AS purchased
  FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`
  GROUP BY user_pseudo_id
)
SELECT
  device,
  SUM(viewed)    AS viewed,
  SUM(carted)    AS added_to_cart,
  SUM(checkout)  AS began_checkout,
  SUM(purchased) AS purchased,
  ROUND(SAFE_DIVIDE(SUM(purchased), SUM(viewed)), 4) AS view_to_purchase_rate
FROM steps
GROUP BY device
ORDER BY viewed DESC;


-- ------------------------------------------------------------
-- Q6. Top products: views, add-to-carts, purchases, revenue
-- ------------------------------------------------------------
SELECT
  item.item_name,
  COUNTIF(event_name = 'view_item')   AS views,
  COUNTIF(event_name = 'add_to_cart') AS add_to_carts,
  COUNTIF(event_name = 'purchase')    AS purchases,
  ROUND(SUM(IF(event_name = 'purchase', item.item_revenue_in_usd, 0)), 2) AS item_revenue_usd,
  ROUND(SAFE_DIVIDE(COUNTIF(event_name = 'purchase'), COUNTIF(event_name = 'view_item')), 4) AS view_to_purchase_rate
FROM `bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*`,
     UNNEST(items) AS item
GROUP BY item.item_name
HAVING views >= 500
ORDER BY item_revenue_usd DESC
LIMIT 25;
