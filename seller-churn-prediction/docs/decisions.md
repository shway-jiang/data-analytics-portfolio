# Analysis decisions

Set by the analyst before any model was built.

| # | Question | Decision | Why |
|---|---|---|---|
| 1 | What counts as churn? | An active seller places **no orders in the next 90 days** | A clear signal, and the data still leaves enough months to backtest |
| 2 | Who counts as active? | **1+ order in the 90 days before** the cutoff date | Only predicts churn for sellers who were recently selling |
| 3 | Small sellers | **Kept**; results are scored in money | The top 10% of sellers make 67% of sales, so a miss on a big seller matters more |
| 4 | Backtest | **Monthly cutoffs**; each model trains only on months whose outcome was already known on the test date | Matches how the model would run in real life, with no peeking at the future |
| 5 | Features | Sales trend, service quality (late deliveries), reviews, seller profile (state, main category, sign-up channel) | Signals a marketplace team already tracks |
| 6 | Business goal | **Sales at risk reached** if outreach is limited to the top 100 sellers a month | Shows the value in money, not just accuracy |

## Definitions
- **Sales (GMV):** item price, excluding freight. Canceled and unavailable orders are removed.
- **Sales at risk:** a churned seller's sales in the 90 days before the cutoff date.
- **Reached:** sales at risk that belong to the sellers the model puts in the top 100.
- **Benchmarks:** two simple rules scored the same way: contact the sellers who have been silent longest, or the biggest recent sellers.
