# Canadian Grocery Price Tracker

**Status:** collecting data daily (Oct 11 – Nov 9, 2026); analysis to follow

A personal portfolio project on Canada's cost of living. It automatically records the price of the same 15-item grocery basket every day for 30 days at four online grocery stores, then compares the stores with each other and with Statistics Canada's official average prices.

## Questions
1. Is No Frills (Loblaw's discount banner) actually cheaper than Loblaws?
2. Who is cheaper: Loblaw's stores or Sobeys (Voilà)?
3. How often do items go on sale, and how deep are the discounts?
4. How does the basket's cost change over the month?
5. How do the stores compare with the Statistics Canada average for Ontario?

## How the data is collected
- **Stores:** Loblaws, No Frills and Real Canadian Superstore (all Loblaw), plus Voilà (Sobeys)
- **Basket:** 2% milk 4 L, large eggs ×12, white bread, bananas, chicken breast, lean ground beef, white rice 2 kg, spaghetti 900 g, salted butter 454 g, cheddar 400 g, gala apples, potatoes, carrots, canned tomatoes 796 mL, peanut butter 1 kg
- **Automation:** a scheduled AI agent runs every morning. It searches each store's website, picks the **cheapest product that matches the spec** (store brands included), and saves one CSV per day. If a page fails, it retries; anything still missing is marked `failed` or `no_match`, never guessed.
- **About 60 price points a day, roughly 1,800 over the project**

Columns: `date, store, owner, item_id, product_name, size, price, regular_price, on_sale, unit_price, unit, status, notes`

Full agent instructions: [`collection_instructions.md`](collection_instructions.md)

## Benchmark
Statistics Canada table [18-10-0245-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810024501), *Monthly average retail prices for selected products*. It's used as an industry average, not a control group.

## Design notes
- Stores that block automated access or don't show prices without a login were excluded: Metro, Food Basics, Walmart, Giant Tiger, FreshCo, Safeway, Save-On-Foods, Longo's, Costco, Farm Boy, Whole Foods and Instacart.
- Prices come from each website's default store location.
- After the first run, the search terms were simplified and fallback terms added, because Voilà returned no results for 5 items.

## Data
The daily CSVs will be added to [`data/`](data) when the collection period ends.
