# Where Is the Store Losing Customers and Ad Money?
*E-commerce funnel & ad efficiency analysis: personal portfolio project by Xue Jiang*

## Summary
An online store's data shows that **only 7.2% of shoppers who view a product end up buying**, and **80% leave before adding anything to the cart**. Returning customers are the store's most valuable group: they convert **4.6× better** than new visitors and bring in two-thirds of revenue. On the advertising side, **95% of the budget goes to the least efficient campaign**, which costs **$64 per sale**, compared with **$6** for the most efficient one.

**Three recommendations:** fix the product page (the biggest leak), invest in bringing customers back, and move ad budget toward the campaigns and audiences that convert cheaply.

---

## 1. The purchase funnel
| Step | Users | % of viewers |
|---|---|---|
| View product | 61,252 | 100% |
| Add to cart | 12,545 | 20.5% |
| Begin checkout | 9,715 | 15.9% |
| Add payment | 5,751 | 9.4% |
| Purchase | 4,419 | **7.2%** |

- **The biggest drop is the product page:** 4 out of 5 viewers never add to cart.
- **The second leak is payment:** 41% of shoppers who reach shipping never enter payment details.
- **One product stands out:** the *Navy Speckled Tee* has the most views (56K) and a 25% add-to-cart rate, but a 0.3% purchase rate. It's a clear cart-abandonment case worth investigating (price, sizing, shipping cost).

## 2. Who buys
- **Returning visitors convert at 3.1%, new visitors at 0.68%.** Returning visitors make up only about a quarter of sessions but bring in about **two-thirds of revenue**.
- **Mobile converts as well as desktop** (7.5% vs 7.0%), so there's no sign of a mobile checkout problem.
- **Referral traffic converts best (2.2%).** Paid search (cpc) converts worst (1.0%), although its orders are the largest ($78 average).
- **Seasonality:** revenue peaks on Cyber Monday and Dec 8–16, then falls sharply after **Dec 19**, likely the holiday shipping cut-off.

## 3. Ad efficiency (Facebook campaigns)
| Campaign | Share of spend | Cost per sale |
|---|---|---|
| A | 0.3% | **$6.24** |
| B | 4.9% | $15.81 |
| C | **94.8%** | $63.83 |

- **Budget is concentrated in the most expensive campaign.**
- **Age:** 30–34-year-olds cost **$31** per sale and 45–49-year-olds **$100**, even though the older group clicks the most. Clicks aren't the same as buyers.
- **Gender:** men cost $41 per sale, women $70.
- **Interests** (groups with at least $500 in ad spend): the cheapest (#2, 65, 101, 21) cost $26–31 per sale. The most expensive (#27, 109, 105) cost $96–108.

---

## Recommendations
| # | Action | Why | What to measure |
|---|---|---|---|
| 1 | **Improve product pages**: better photos, size guides, reviews, and shipping cost shown early | 80% drop at view → cart | Add-to-cart rate |
| 2 | **Simplify payment**: add express pay options (Apple Pay, PayPal) and guest checkout | 41% drop at payment | Shipping → payment rate |
| 3 | **Win back customers**: email and remarketing after the first visit or purchase | Returning visitors convert 4.6× better | Repeat-visit rate, revenue per user |
| 4 | **Shift ad budget**: test moving part of Campaign C's budget to A and B, and target ages 30–34 and the top interest groups | C costs 10× more per sale | Cost per sale, ROAS |
| 5 | **Plan around the calendar**: push promotions before Dec 19 and communicate shipping cut-offs | Sales collapse after mid-December | Revenue in the Dec 15–24 window |

**Illustrative impact (estimate, not a forecast):** if the add-to-cart rate rose from 20.5% to 23% and every later step kept its current rate, purchases would grow by about 12%, roughly 540 extra orders over the same period. Moving $10K from Campaign C to Campaign B at B's current cost per sale would buy about 630 sales instead of about 160. *Smaller campaigns may not scale at the same cost, so this should be tested gradually.*

**A test to run with real traffic:** A/B test a product page with reviews and a size guide against the current page. Primary metric: add-to-cart rate.

---

## Data, method & limitations
- **Data:** the Google Merchandise Store GA4 sample (BigQuery public data, Nov 2020 – Jan 2021, 4.3M events) and Kaggle's "Clicks conversion tracking" Facebook ads data (1,143 ads). The two datasets aren't linked, so they're analysed separately.
- **Tools:** SQL (BigQuery) for the funnel, channel and segment queries; Python (pandas) for the ad metrics; Power BI for the dashboard.
- **Limitations:**
  - Google obfuscates the GA4 sample: about 42% of users have a hidden traffic source, and order IDs are missing for parts of Nov and Jan.
  - The funnel counts users who did each step at any time, not a strict in-order path.
  - **The ad data has no revenue, so ROAS assumes $100 per sale.**
  - The data is historical (2017–2021). It's used to show the method, not to describe any company's current performance.
