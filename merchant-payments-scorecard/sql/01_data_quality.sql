-- =============================================================================
-- 01  DATA QUALITY CHECKS
-- Run on the raw Olist tables before any reporting. Each check returns one row:
-- what was checked, how many records fail, and how the clean tables handle it.
-- Written for SQLite; comments show the Snowflake equivalent where it differs.
-- =============================================================================

-- name: data_quality_checks
WITH
sparse_months AS (
    -- months with fewer than 500 orders are the start/end of the data extract
    SELECT COALESCE(SUM(n), 0) AS n
    FROM (SELECT SUBSTR(order_purchase_timestamp, 1, 7) AS m, COUNT(*) AS n
          FROM raw_orders GROUP BY m HAVING COUNT(*) < 500)
),
orders_no_items AS (
    SELECT COUNT(*) AS n FROM raw_orders o
    WHERE NOT EXISTS (SELECT 1 FROM raw_order_items i WHERE i.order_id = o.order_id)
),
orders_no_payment AS (
    SELECT COUNT(*) AS n FROM raw_orders o
    WHERE NOT EXISTS (SELECT 1 FROM raw_order_payments p WHERE p.order_id = o.order_id)
),
payment_mismatch AS (
    -- amount paid should equal item prices + freight (allowing R$1 for rounding)
    SELECT COUNT(*) AS n
    FROM (SELECT order_id, SUM(payment_value) AS paid FROM raw_order_payments GROUP BY order_id) p
    JOIN (SELECT order_id, SUM(price + freight_value) AS billed FROM raw_order_items GROUP BY order_id) i
      USING (order_id)
    WHERE ABS(p.paid - i.billed) > 1
),
bad_payment_rows AS (
    SELECT COUNT(*) AS n FROM raw_order_payments
    WHERE payment_type = 'not_defined' OR payment_value <= 0 OR payment_installments < 1
),
duplicate_reviews AS (
    -- orders with more than one review row
    SELECT COALESCE(SUM(cnt - 1), 0) AS n
    FROM (SELECT order_id, COUNT(*) AS cnt FROM raw_order_reviews GROUP BY order_id HAVING COUNT(*) > 1)
),
delivered_no_date AS (
    SELECT COUNT(*) AS n FROM raw_orders
    WHERE order_status = 'delivered' AND order_delivered_customer_date IS NULL
),
carrier_before_approval AS (
    SELECT COUNT(*) AS n FROM raw_orders
    WHERE order_delivered_carrier_date < order_approved_at
),
products_no_category AS (
    SELECT COUNT(*) AS n FROM raw_products WHERE product_category_name IS NULL
),
category_no_translation AS (
    SELECT COUNT(DISTINCT p.product_category_name) AS n
    FROM raw_products p
    LEFT JOIN raw_category_translation t USING (product_category_name)
    WHERE p.product_category_name IS NOT NULL AND t.product_category_name IS NULL
),
leads_no_origin AS (
    SELECT COUNT(*) AS n FROM raw_marketing_qualified_leads WHERE origin IS NULL
),
deals_unknown_lead AS (
    SELECT COUNT(*) AS n FROM raw_closed_deals d
    LEFT JOIN raw_marketing_qualified_leads l USING (mql_id)
    WHERE l.mql_id IS NULL
),
deals_won_before_contact AS (
    SELECT COUNT(*) AS n FROM raw_closed_deals d
    JOIN raw_marketing_qualified_leads l USING (mql_id)
    WHERE DATE(d.won_date) < DATE(l.first_contact_date)
)
SELECT 'Orders in partial months (outside Jan 2017 - Aug 2018)' AS check_name, n AS failing_rows, 'Excluded from monthly trends'                  AS action FROM sparse_months
UNION ALL SELECT 'Orders with no items',                         n, 'Excluded from sales metrics (mostly canceled)'     FROM orders_no_items
UNION ALL SELECT 'Orders with no payment record',                n, 'Excluded from payment metrics'                     FROM orders_no_payment
UNION ALL SELECT 'Amount paid differs from items + freight',     n, 'Kept; sales use item prices, payments use amount paid' FROM payment_mismatch
UNION ALL SELECT 'Payment rows: undefined type, R$0 or 0 installments', n, 'Excluded from payment-method metrics'        FROM bad_payment_rows
UNION ALL SELECT 'Extra review rows for the same order',         n, 'Keep the latest review per order'                  FROM duplicate_reviews
UNION ALL SELECT 'Delivered orders missing delivery date',       n, 'Excluded from delivery metrics'                    FROM delivered_no_date
UNION ALL SELECT 'Handed to carrier before payment approved',    n, 'Kept; timestamps come from different systems'       FROM carrier_before_approval
UNION ALL SELECT 'Products with no category',                    n, 'Reported as "unknown"'                             FROM products_no_category
UNION ALL SELECT 'Categories missing an English name',           n, 'Translated in the clean table'                     FROM category_no_translation
UNION ALL SELECT 'Seller leads with no origin channel',          n, 'Reported as "unknown"'                             FROM leads_no_origin
UNION ALL SELECT 'Closed deals with no matching lead',           n, 'Investigate if > 0'                                FROM deals_unknown_lead
UNION ALL SELECT 'Deals won before first contact',               n, 'Excluded from days-to-close'                                FROM deals_won_before_contact;
