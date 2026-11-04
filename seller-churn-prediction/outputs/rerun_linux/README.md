# Rerun on a second computer

A full rerun of `python/churn_pipeline.py` on the same Olist files, on a second computer, to check that the results reproduce.

- Environment: Linux, Python 3.13, pandas 3.0.5, numpy 2.5.3, scikit-learn 1.9.1, matplotlib 3.11.2
- Main run (`../`): Windows, Python 3.13, pandas 3.1.0, numpy 2.5.4, scikit-learn 1.9.1, matplotlib 3.11.2

Compared with the main outputs:
- The three simple rules match exactly.
- The models differ slightly. Across all 9 months, totals moved by up to 0.5 points at 100 sellers (gradient boosting x_sales 45.43% here vs 45.95%) and 0.9 points at 50 sellers. Counting each order once, they moved by up to 0.2 points at 100 sellers and 1.5 points at 50 sellers (gradient boosting x_sales 38.4% here vs 36.9%). A single month moved by up to 2.3 points at 100 sellers.
- One exception to the main conclusions: at 50 sellers across all 9 months, gradient boosting x_sales edged past the silent x sales rule (35.0% vs 34.7%). In the main run it was behind (34.1%). Counting each order once, the rule still leads at every size in both runs.
- The main conclusions otherwise hold: at 100 sellers, the silent x sales rule still reaches the most counting each order once (54.1%, against 51.4% and 49.1%), both models still beat the biggest-sellers rule in 9 of 9 months, and each still beats the silent x sales rule in 4 of 9 months.
- At 50 and 200 sellers, gradient boosting's month count against the silent x sales rule moves by one (4 of 9 at 50 and 3 of 9 at 200 here, against 3 and 4 in the main run).

Charts are not included; only the CSV tables.
