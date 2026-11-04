# Analysis decisions

Decisions 1 to 6 were set by the analyst before any model was built. Decisions 7 and 8, the final choice and the review fixes came later, after seeing test results, so no test month is truly held out.

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | What counts as churn? | An active seller places **no orders in the next 90 days** | A clear signal, and the data still leaves enough months to backtest |
| 2 | Who counts as active? | **1+ order in the 90 days before** the cutoff date | Only predicts churn for sellers who were recently selling |
| 3 | Small sellers | **Kept**; results are scored in money | The top 10% of sellers make 67% of sales, so a miss on a big seller matters more |
| 4 | Backtest | **Monthly cutoffs**; each model trains only on months whose outcome was already known on the test date | Matches how the model would run in real life, with no peeking at the future |
| 5 | Features | Sales trend, service quality (late deliveries), reviews, seller profile (state, main category, sign-up channel) | Signals a marketplace team already tracks |
| 6 | Business goal | **Sales at risk reached** if outreach is limited to the top 100 sellers a month | Shows the value in money, not just accuracy |
| 7 | How to rank sellers for outreach (added in the second run) | Test two ways: **plain** (churn probability) and **x_sales** (churn probability x `gmv_90`, the expected money lost) | Decision 3 keeps all sellers, so the ranking should also care about how much money each seller holds |
| 8 | How to train (added in the second run) | Test two ways: **unweighted** and **weighted** (each training row weighted by `gmv_90`) | Lets the model pay more attention to big sellers. Both ways run for both models, giving four variants: `plain`, `x_sales`, `weighted`, `weighted_x_sales` |

## Definitions
- **Sales (GMV):** item price, excluding freight. Canceled and unavailable orders are removed.
- **Sales at risk:** a churned seller's sales in the 90 days before the cutoff date. Added up over months, this counts repeated sales again, because a seller who stops stays active at later cutoffs. Reais totals count each order once (`outputs/money_each_order_once.csv`).
- **Reached:** sales at risk that belong to the sellers the model puts in the top 100.
- **Benchmarks:** three simple rules scored the same way: contact the sellers who have been silent longest, the biggest recent sellers, or the highest days since last order x `gmv_90` (added in the review fixes).

## Added in the second run
- **Sales weights:** weight = `gmv_90`, capped at the 99th percentile of the training rows, floored at R$1 so no weight is zero, then divided by its mean so the average weight is 1. Weights use training rows only.
- **Expected money lost:** the score used to rank sellers is churn probability x `gmv_90`.
- **AUC and average precision** are always computed on the churn probability (or the rule's own score), never on probability x sales. So `plain` and `x_sales` share the same AUC.
- **Big sellers:** the top 10% of active sellers by `gmv_90` on each test date. The cutoff is recomputed each month from the sellers active on that date. AUC is computed separately for big sellers and for the rest (`outputs/auc_by_seller_size.csv`).
- **Version 1** results (before these changes) are kept in `outputs/v1/`.

## Final choice (run 3)
- **Headline model:** logistic regression, ranking sellers by churn probability x `gmv_90` (`logistic_x_sales`). Gradient boosting with the same ranking is a comparison only.
- **The final choice was fixed here and no further variants will be tried.**
- **Sales weights (decision 8) are not used.** They did not help in run 2: weights alone reached 15.9% (logistic) and 12.3% (gradient boosting) of the sales at risk, below the 19.6% of the "biggest recent sellers" rule, and weights on top of x_sales gave 44.4% and 43.9%, no better than x_sales alone (44.2% and 46.6%). The run 2 outputs are in `outputs/v2/`.
- **Checks added in run 3:** spread over the test months (`spread_by_model.csv`), 50, 100 and 200 sellers contacted a month (`backtest_by_top_k.csv`), and a "what if" table that assumes outreach saves 10%, 20% or 30% of the sales at risk it reaches (`what_if_savings.csv`). The "what if" table is an assumption, not a result.

## Review fixes (after run 3)
A review before publishing found these problems. Run 3 is kept in `outputs/v3/`. The percentages quoted above for runs 1 to 3 come from before these fixes.
- **No future information in features.** A late flag or review counts only if the delivery or review had already happened on the cutoff date. An order that was overdue but not yet delivered counts as unknown.
- **Rare categories and states** are grouped using training rows only, recomputed for each test month.
- **Last test month is May 2018, so there are 9 test months, not 10.** Daily orders fade from August 22, 2018 and stop on August 29. June 2018's 90-day outcome ran to August 30, so some June sellers could be wrongly marked as churned. The data is now treated as ending on August 21. Any end date from July 30 to August 29 gives the same results.
- **Reais totals count each order once.** Monthly shares are unchanged by this.
- **A third simple rule, days since last order x `gmv_90`, was added as a benchmark.** It is a rule, not a new model variant. It was added after seeing results because the two earlier rules did not combine silence with sales, which made the x_sales models look better than the evidence supports.
- **Still not fixable:** canceled orders are removed using their final status, because the data has no cancellation date. They are 1.24% of orders.
