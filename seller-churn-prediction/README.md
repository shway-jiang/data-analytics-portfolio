# Seller Churn Prediction with a Rolling Backtest

**Status:** 🔧 In progress. The code and notebook are ready. Results will be added after the first run on the full Olist data.

A personal portfolio project. Which active sellers on an online marketplace are likely to stop selling in the next 90 days, and how much of the sales at risk can a limited outreach budget reach? A marketplace or payments team could use the answer to decide which merchants an account manager calls first.

**Data:** real, anonymized data from [Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce), a Brazilian online marketplace (3,000 sellers, 2017 to August 2018). Download steps: [`data/README.md`](data/README.md). It builds on the cleaned tables from the [Merchant Payments Scorecard](../merchant-payments-scorecard).

## Approach
1. **Seller-month table.** For every month start from April 2017, one row per active seller (1+ order in the last 90 days), with features built only from orders before that date.
2. **Label.** `churned = 1` if the seller has no orders in the next 90 days.
3. **Features.** Orders and sales over the last 30 and 90 days and the 90 days before that, days since the last order, tenure, average order value, late-delivery rate, average and low review scores, main category, state and sign-up channel.
4. **Rolling backtest.** For each test month, models train only on earlier months whose 90-day outcome was already known on that date, so the model never sees the future.
5. **Models.** Logistic regression and gradient boosting, against two simple rules: contact the sellers who have been silent the longest, or the biggest recent sellers.
6. **Scored in money.** If outreach is limited to the top 100 sellers a month, what share of the sales at risk do they hold?

All analysis decisions are listed in [`docs/decisions.md`](docs/decisions.md).

## Files
| File | What it does |
|---|---|
| [`python/churn_pipeline.py`](python/churn_pipeline.py) | Builds the seller-month table, runs the rolling backtest and saves tables and charts. Run with `python churn_pipeline.py --data ../data/raw --out ../outputs` |
| [`notebooks/churn_backtest.ipynb`](notebooks/churn_backtest.ipynb) | Step-by-step walkthrough with exploration cells |
| [`docs/decisions.md`](docs/decisions.md) | The six analysis decisions and metric definitions |
| `outputs/` | Backtest tables and charts (added after the first run) |

## Results
To be added after the first run.

## Limitations
- The data covers 20 months, so each backtest month rests on a short history.
- Churn is measured as "no orders", and a seller who pauses for a season counts as churned.
- "Sales at risk" is the sales a churned seller made before leaving. It shows where the money sits, not how much outreach would save.
