# Canadian Retail Sales Forecast

**Status:** in progress

A forecasting project using Statistics Canada's official monthly retail trade data. It predicts retail sales by province and store type for the next 6 to 12 months, and checks the forecasts against months the model never saw (backtesting).

## Why it matters
Retail spending drives card payment volume. A business that can see a slowdown or a holiday spike coming can plan staffing, server capacity and cash flow ahead of time instead of reacting late.

## Planned questions
1. How much will retail sales grow over the next year, nationally and by province?
2. Which store types are slowing down, and which are growing?
3. How accurate are simple baselines (last year's value) compared with time series models?
4. How big are seasonal peaks like December, and how well can they be predicted?

## Planned approach
- **Data:** Statistics Canada monthly retail trade sales (real public data, no simulated values)
- **Methods:** seasonal baseline, exponential smoothing and SARIMA, compared on rolling backtests
- **Tools:** Python (pandas, statsmodels), SQL, Power BI or Excel for the final view

*This is a personal project and not financial advice.*
