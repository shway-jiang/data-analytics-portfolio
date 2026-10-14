# Metric definitions and business rules

Every report in this project uses these definitions. The logic lives in one place, [`sql/02_clean_tables.sql`](../sql/02_clean_tables.sql), so a metric can't mean one thing in Excel and another on the dashboard.

**Reporting period:** January 2017 – August 2018. The few orders from Sept–Dec 2016 and Sept–Oct 2018 are partial months at the edges of the data extract and are left out of trends. **Currency:** Brazilian reais (R$).

## Sales

| Metric | Definition |
|---|---|
| **Orders** | All orders placed in the month, including canceled ones. |
| **Canceled orders** | Orders with status `canceled` or `unavailable`. |
| **GMV** (gross merchandise value) | Sum of item prices on orders that weren't canceled. Freight is excluded. |
| **Average order value** | GMV ÷ orders with items that weren't canceled. |

## Payments

| Metric | Definition |
|---|---|
| **Main payment method** | Some orders are split across methods (e.g. card + voucher). The method that paid the largest share is the order's main method. |
| **Share of value** | Amount paid with that main method ÷ total amount paid (orders not canceled). |
| **Hours to approve** | Hours from purchase to payment approval; the median is reported because a few orders take weeks. |
| **Installments** | Number of monthly installments chosen for a credit card payment (1 = paid in full). |

## Sellers (the marketplace's merchants)

| Metric | Definition |
|---|---|
| **Active seller** | A seller with at least one item sold (not canceled) in the month. |
| **New seller** | A seller whose first-ever sale falls in the month. |
| **Seller retention** | Share of last month's active sellers who also sold this month. |
| **GMV per active seller** | GMV ÷ active sellers. |
| **Seller concentration** | Sellers ranked by GMV and split into 10 equal groups. |

## Seller onboarding funnel

| Metric | Definition |
|---|---|
| **Lead** | A marketing-qualified seller lead, with the channel it came from (organic search, paid search, social…). |
| **Signed seller** | A lead that became a closed deal. |
| **Lead to signed** | Signed sellers ÷ leads. |
| **Days to close** | Days from first contact to deal won (median). One deal dated before its lead is excluded. |
| **Signed with first sale** | Signed sellers who made at least one sale in the data. Only deals won by 30 June 2018 are counted, so each seller had at least two months to sell. |

## Service and customer experience

| Metric | Definition |
|---|---|
| **Seller shipped on time** | The parcel reached the carrier by the seller's shipping deadline. |
| **Delivered on time** | Delivered on or before the estimated delivery date shown to the customer. Only delivered orders with a delivery date count. |
| **Delivery days** | Days from purchase to delivery. |
| **Review score** | Customer review, 1–5 stars. If an order has several reviews, the latest is used. |
| **Low reviews** | Share of reviews with 1 or 2 stars. |

## Data-quality rules

Checked by [`sql/01_data_quality.sql`](../sql/01_data_quality.sql) on every refresh.

| Issue found | Count | Rule |
|---|---|---|
| Orders in partial months | 349 | Left out of monthly trends |
| Orders with no items (mostly canceled) | 775 | Left out of sales metrics |
| Order with no payment record | 1 | Left out of payment metrics |
| Amount paid ≠ item prices + freight | 249 | Kept; sales metrics use item prices, payment metrics use the amount paid |
| Payment rows with undefined method, R$0 or 0 installments | 11 | Left out of payment metrics |
| Extra review rows for the same order | 551 | Latest review kept |
| Delivered orders missing a delivery date | 8 | Left out of delivery metrics |
| Parcel handed to carrier before payment approval | 1,359 | Kept; timestamps come from different systems |
| Products with no category | 610 | Reported as "unknown" |
| Categories with no English name | 2 | Translated in the clean table |
| Seller leads with no channel | 60 | Reported as "unknown" |
| Deal won before first contact | 1 | Left out of days-to-close |
