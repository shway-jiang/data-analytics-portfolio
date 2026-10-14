-- =============================================================================
-- 02  CLEAN REPORTING TABLES
-- Fixes the issues found in 01_data_quality.sql and puts every business rule
-- in one place, so Excel, the notebook and the dashboard all agree.
-- Rules are documented in docs/metric_definitions.md.
-- Snowflake notes: julianday(b) - julianday(a)  ->  DATEDIFF('hour', a, b) / 24.0
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Orders: one row per order, with payment, delivery and review facts attached
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS order_payment_summary;
CREATE TABLE order_payment_summary AS
WITH valid AS (
    SELECT * FROM raw_order_payments
    WHERE payment_type <> 'not_defined' AND payment_value > 0 AND payment_installments >= 1
),
ranked AS (
    -- the payment method that paid the most of the order is its "main" method
    SELECT order_id, payment_type, payment_installments,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY payment_value DESC, payment_sequential) AS rn
    FROM valid
)
SELECT
    v.order_id,
    r.payment_type                       AS main_payment_type,
    r.payment_installments               AS installments,
    SUM(v.payment_value)                 AS amount_paid,
    COUNT(*)                             AS payment_rows,
    MAX(CASE WHEN v.payment_type = 'voucher' THEN 1 ELSE 0 END) AS used_voucher
FROM valid v
JOIN ranked r ON r.order_id = v.order_id AND r.rn = 1
GROUP BY v.order_id;


DROP TABLE IF EXISTS order_reviews;
CREATE TABLE order_reviews AS
SELECT order_id, review_score
FROM (
    SELECT order_id, review_score,
           ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC) AS rn
    FROM raw_order_reviews
)
WHERE rn = 1;


DROP TABLE IF EXISTS orders;
CREATE TABLE orders AS
WITH items AS (
    SELECT order_id,
           COUNT(*)                 AS item_count,
           SUM(price)               AS merchandise_value,
           SUM(freight_value)       AS freight_value,
           MIN(shipping_limit_date) AS shipping_limit_date,
           COUNT(DISTINCT seller_id) AS seller_count
    FROM raw_order_items
    GROUP BY order_id
)
SELECT
    o.order_id,
    c.customer_unique_id,
    c.customer_state,
    o.order_status,
    o.order_purchase_timestamp                                         AS purchased_at,
    SUBSTR(o.order_purchase_timestamp, 1, 7)                           AS order_month,
    CASE WHEN SUBSTR(o.order_purchase_timestamp, 1, 7) BETWEEN '2017-01' AND '2018-08'
         THEN 1 ELSE 0 END                                             AS in_period,
    CASE WHEN o.order_status IN ('canceled', 'unavailable') THEN 1 ELSE 0 END AS is_canceled,
    i.item_count,
    i.merchandise_value,
    i.freight_value,
    p.main_payment_type,
    p.installments,
    p.amount_paid,
    p.used_voucher,
    -- hours from purchase to payment approval
    ROUND((julianday(o.order_approved_at) - julianday(o.order_purchase_timestamp)) * 24, 2) AS approval_hours,
    -- did the seller hand the parcel to the carrier by the promised shipping date?
    CASE WHEN o.order_delivered_carrier_date IS NULL OR i.shipping_limit_date IS NULL THEN NULL
         WHEN o.order_delivered_carrier_date <= i.shipping_limit_date THEN 1 ELSE 0 END AS seller_shipped_on_time,
    -- delivery: only delivered orders with a delivery date
    CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
         THEN ROUND(julianday(o.order_delivered_customer_date) - julianday(o.order_purchase_timestamp), 1) END AS delivery_days,
    CASE WHEN o.order_status = 'delivered' AND o.order_delivered_customer_date IS NOT NULL
         THEN CASE WHEN DATE(o.order_delivered_customer_date) <= DATE(o.order_estimated_delivery_date) THEN 1 ELSE 0 END
    END                                                                AS delivered_on_time,
    r.review_score
FROM raw_orders o
JOIN raw_customers c USING (customer_id)
LEFT JOIN items i USING (order_id)
LEFT JOIN order_payment_summary p USING (order_id)
LEFT JOIN order_reviews r USING (order_id);


-- ---------------------------------------------------------------------------
-- Order items: one row per item, with seller and English category
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS order_items;
CREATE TABLE order_items AS
SELECT
    i.order_id,
    i.seller_id,
    i.product_id,
    COALESCE(t.product_category_name_english,
             CASE p.product_category_name
                 WHEN 'pc_gamer' THEN 'pc_gamer'
                 WHEN 'portateis_cozinha_e_preparadores_de_alimentos' THEN 'portable_kitchen_appliances'
             END,
             'unknown')                       AS category,
    i.price,
    i.freight_value,
    o.order_month,
    o.in_period,
    o.is_canceled,
    o.purchased_at
FROM raw_order_items i
JOIN orders o USING (order_id)
LEFT JOIN raw_products p USING (product_id)
LEFT JOIN raw_category_translation t USING (product_category_name);


-- ---------------------------------------------------------------------------
-- Sellers (the marketplace's merchants)
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS sellers;
CREATE TABLE sellers AS
SELECT
    s.seller_id,
    s.seller_state,
    MIN(i.purchased_at)                           AS first_sale_at,
    SUBSTR(MIN(i.purchased_at), 1, 7)             AS first_sale_month,
    SUM(CASE WHEN i.is_canceled = 0 THEN i.price ELSE 0 END) AS lifetime_gmv
FROM raw_sellers s
LEFT JOIN order_items i USING (seller_id)
GROUP BY s.seller_id, s.seller_state;


-- ---------------------------------------------------------------------------
-- Seller acquisition funnel: marketing leads -> closed deals -> first sale
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS seller_leads;
CREATE TABLE seller_leads AS
SELECT
    l.mql_id,
    DATE(l.first_contact_date)                       AS first_contact_date,
    SUBSTR(l.first_contact_date, 1, 7)               AS lead_month,
    COALESCE(l.origin, 'unknown')                    AS origin,
    CASE WHEN d.mql_id IS NOT NULL THEN 1 ELSE 0 END AS won,
    DATE(d.won_date)                                 AS won_date,
    CASE WHEN DATE(d.won_date) >= DATE(l.first_contact_date)      -- 1 deal is dated before its lead
         THEN CAST(julianday(DATE(d.won_date)) - julianday(DATE(l.first_contact_date)) AS INTEGER)
    END                                              AS days_to_close,
    d.seller_id,
    d.business_segment,
    d.lead_type,
    d.business_type,
    s.first_sale_at,
    CAST(julianday(DATE(s.first_sale_at)) - julianday(DATE(d.won_date)) AS INTEGER)      AS days_won_to_first_sale,
    COALESCE(s.lifetime_gmv, 0)                      AS lifetime_gmv
FROM raw_marketing_qualified_leads l
LEFT JOIN raw_closed_deals d USING (mql_id)
LEFT JOIN sellers s ON s.seller_id = d.seller_id;


-- indexes for the scorecard queries (not needed in Snowflake)
CREATE INDEX ix_o_id     ON orders(order_id);
CREATE INDEX ix_o_month  ON orders(order_month);
CREATE INDEX ix_oi_order ON order_items(order_id);
CREATE INDEX ix_oi_sell  ON order_items(seller_id, order_month);
