# Canadian Grocery Price Tracker

**Status:** collecting data daily (Oct 11 – Dec 1, 2026); analysis to follow

A personal portfolio project on Canada's cost of living. It automatically records the price of the same 15-item grocery basket every day at six online grocery stores, tracking one fixed product per store and item, then compares the stores with each other and with Statistics Canada's official average prices.

## Questions
1. Is No Frills (Loblaw's discount banner) actually cheaper than Loblaws?
2. Who is cheaper: Loblaw's stores or Sobeys (Voilà)?
3. How often do items go on sale, and how deep are the discounts?
4. How does the basket's cost change over the month?
5. Are prices higher on certain days of the week or days of the month?
6. How do the stores compare with the Statistics Canada average for Ontario?

## How the data is collected
- **Stores:** Loblaws, No Frills and Real Canadian Superstore (all Loblaw), Voilà (Sobeys), plus Walmart and Metro from Oct 29. All are Toronto-area locations.
- **Basket:** 2% milk 4 L, large eggs ×12, white bread, bananas, chicken breast, lean ground beef, white rice 2 kg, spaghetti 900 g, salted butter 454 g, cheddar 400 g, gala apples, potatoes, carrots, canned tomatoes 796 mL, peanut butter 1 kg
- **One fixed product per store and item**, regular (non-organic, non-specialty) products only. The price recorded is the price on that day, never a future sale. Full rules: [`data_collection_rules.md`](data_collection_rules.md). Products: [`product_list.md`](product_list.md).
- **Automation:** two scheduled AI agents run every morning. A cloud agent reads Loblaws, No Frills, Superstore and Voilà; a browser agent reads Walmart and Metro. Each saves one CSV per day and writes a one-line run log. Nothing missing is ever guessed: it's marked `not_found` or `failed`.
- **About 90 price points a day from Oct 29**
- **When and where:** daily at 5:41 am (Walmart, Metro) and 6:53 am (the others), Toronto time. Store locations, file formats and a column dictionary are in [About the data](data_collection_rules.md#about-the-data).

### Why these 15 items?
It's a **staples basket**, not a weekly shopping list. Each item was chosen because it is:
- **An everyday essential** that most households buy, covering the main food groups: dairy (milk, butter, cheese, eggs), protein (chicken, ground beef, peanut butter), grains (bread, rice, pasta), produce (bananas, apples, potatoes, carrots) and pantry (canned tomatoes)
- **Sold at every store in a standard size** (e.g. 4 L milk, 900 g spaghetti), so prices compare like for like
- **Comparable with official data**: most of the items also appear in Statistics Canada's monthly retail price table, which is used as the benchmark

Fresh meat and produce are compared by **unit price** (per kg), because pack sizes vary.

Columns: `date, store, owner, item_id, product_name, size, price, regular_price, on_sale, unit_price, unit, status, notes`

Collection rules (v2, from Oct 29): [`data_collection_rules.md`](data_collection_rules.md). The original v1 agent instructions (Oct 11–28): [`collection_instructions.md`](collection_instructions.md)

## Benchmark
Statistics Canada table [18-10-0245-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810024501), *Monthly average retail prices for selected products*. It's used as an industry average, not a control group.

## Design notes
- Walmart blocks automated search, and Metro's publicly cached pages showed out-of-date sale dates, so both are read through a signed-in browser instead (from Oct 29). Food Basics, Giant Tiger, FreshCo, Safeway, Save-On-Foods, Longo's, Costco, Farm Boy, Whole Foods and Instacart were not included.
- Loblaws, No Frills, Superstore and Voilà use each website's default (Toronto-area) store; Walmart and Metro are set to their Toronto Downsview stores.
- After the first run, the search terms were simplified and fallback terms added, because Voilà returned no results for 5 items.
- On Oct 29 the method changed from "cheapest matching product each day" to "one fixed product per store", and the collection was extended to Dec 1 to cover every day of the month. The Oct 11–28 data was cleaned to match (see [`data_collection_rules.md`](data_collection_rules.md#what-changed-from-v1-oct-1128)).

## Data
The daily CSVs will be added to [`data/`](data) when the collection period ends.
