# Canadian Grocery Price Tracker

**Status:** collecting data daily (Oct 29 – Dec 1, 2026); analysis to follow

A personal portfolio project on Canada's cost of living. Every day it records the online price of the same 15-item grocery basket at five Thunder Bay, Ontario stores. It tracks one fixed product per store and item, then compares the stores with each other and with Statistics Canada's official average prices.

## Questions
1. Which store has the cheapest basket, and by how much?
2. Is No Frills (Loblaw's discount banner) cheaper than Real Canadian Superstore, Safeway, Metro and Walmart?
3. How often do items go on sale, and how deep are the discounts?
4. How does the basket's cost change over the month?
5. Are prices higher on certain days of the week or days of the month?
6. How do member prices compare with regular prices?
7. How do the stores compare with the Statistics Canada average for Ontario?

## How the data is collected
- **Stores (all in Thunder Bay):** Real Canadian Superstore (Carrick St), No Frills (Dawson Rd), Safeway (Dawson Rd), Metro (River St) and Walmart (Thunder Bay North). One location per store, fixed for the whole project.
- **Basket:** 2% milk 4 L, large eggs ×12, white bread, bananas, chicken breast, lean ground beef, white rice 2 kg, spaghetti 900 g, salted butter 454 g, cheddar 400 g, gala apples, potatoes, carrots, canned tomatoes 796 mL, peanut butter 1 kg
- **One fixed product per store and item.** Regular products only (no organic or specialty versions), and the same brand and pack every day, so a price change always means the same product got cheaper or dearer.
- **Same-day prices only.** The price recorded is the one shown that day. Future sales and flyer previews are skipped.
- **Regular and member prices** are recorded in separate columns, along with whether the item was on sale.
- **Daily, early morning, in a real browser.** All five stores are read in one signed-in Chrome browser so location and account are the same for every store. From Nov 4 a read-only browser extension opens the same 75 saved product pages (15 items × 5 stores) each day. It never searches, adds to cart or checks out.
- **75 price points a day, about 2,500 over the project.**
- **Nothing is guessed.** A product that can't be found is marked `not_found`, and a page that fails to load or shows a robot check is marked `failed`. No other product is substituted and no price is reused from another day.

### Why these 15 items?
It's a **staples basket**, not a weekly shopping list. Each item was chosen because it is:
- **An everyday essential** that most households buy, covering the main food groups: dairy (milk, butter, cheese, eggs), protein (chicken, ground beef, peanut butter), grains (bread, rice, pasta), produce (bananas, apples, potatoes, carrots) and pantry (canned tomatoes)
- **Sold at every store in a standard size** (e.g. 4 L milk, 900 g spaghetti), so prices compare like for like
- **Comparable with official data**: most of the items also appear in Statistics Canada's monthly retail price table, which is used as the benchmark

Pack sizes can differ slightly between stores (for example a 1.36 kg or a 2 kg bag of apples), so stores are compared by **unit price** (per kg, per L or per egg). Fresh meat and produce sold by weight are always compared per kg.

## Benchmark
Statistics Canada table [18-10-0245-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810024501), *Monthly average retail prices for selected products*. It's used as an industry average, not a control group.

## Design notes
- **Why Thunder Bay?** The stores are local, so prices can be checked in person. Reading all five through the same browser also removes differences in location or sign-in.
- **Online prices only.** In-store shelf prices can differ from what a website shows.
- **Stores that couldn't be read reliably** (for example Food Basics, Giant Tiger and FreshCo) were left out.
- **Two methods, two datasets.** A pilot ran from Oct 11 to Oct 28 at four Toronto-area online stores (Loblaws, No Frills, Superstore and Voilà), picking the cheapest matching product each day. That mixed different products into one price series, so on Oct 29 the method changed to one fixed product per store and moved to Thunder Bay. The pilot data was cleaned (off-spec rows removed, then only each store's fixed product kept) and is analysed separately, never mixed with the Thunder Bay data.
- **Collection runs to Dec 1** so that every day of the month (1–31) is covered at least once.

## Rules and method
- General collection rules (fixed product, regular products only, same-day prices, no guessing): [`data_collection_rules.md`](data_collection_rules.md)
- The original pilot agent instructions (Oct 11–28): [`collection_instructions.md`](collection_instructions.md)

## Data
The daily data files will be added to [`data/`](data) when the collection period ends.
