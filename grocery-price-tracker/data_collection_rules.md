# Data collection rules

These are the rules the tracker follows from **Oct 29 to Dec 1, 2026** (method v2). The first version (Oct 11–28) is in [`collection_instructions.md`](collection_instructions.md). The changes are explained at the bottom.

## What is collected
- **15 staple items:** 2% milk, large eggs, white bread, bananas, chicken breast, lean ground beef, white rice, spaghetti, salted butter, cheddar, gala apples, potatoes, carrots, canned diced tomatoes, smooth peanut butter
- **6 stores, all set to Toronto-area locations:**

| Store | Owner | Location used | Collected by |
|---|---|---|---|
| Loblaws | Loblaw | website default (Toronto area) | cloud agent |
| No Frills | Loblaw | website default (Toronto area) | cloud agent |
| Real Canadian Superstore | Loblaw | website default (Toronto area) | cloud agent |
| Voilà | Sobeys | website default (Toronto area) | cloud agent |
| Walmart | Walmart | Toronto Downsview (from Oct 29) | browser agent |
| Metro | Metro | Metro Downsview (from Oct 29) | browser agent |

- **Once a day:** the browser agent runs at 5:41 am and the cloud agent at 6:53 am (Toronto time). Each saves one CSV per day.

## Rule 1: one fixed product per store and item
- Each store tracks **the same product every day** (same brand, name and pack). The goal is to see how that exact product's price moves with and without sales, without mixing in prices from different products.
- The products are listed in [`product_list.md`](product_list.md). A product that wasn't chosen yet (Loblaws beef, all Walmart and Metro items) is picked once on the first run, as the cheapest product that meets the spec, and then stays fixed.
- **Sizes may differ between stores** (e.g. a 907 g vs 1.36 kg bag of carrots), as long as they're roughly the same. Stores are compared by **unit price** (per kg, per L, or per egg).
- If the product can't be found that day, the row is marked `not_found` with empty prices. **Another product is never substituted.**

## Rule 2: regular products only
- Only regular, conventional products are recorded, for every item. **Excluded:** organic, no-salt-added or reduced-sodium, gluten-free, keto, plant-based, grass-fed, free-range or free-run, omega-3, lactose-free, microfiltered milk, mini, baby, and other specialty or premium versions.
- Beef means **lean ground beef** only. Not extra lean, sirloin, steaks, roasts, stewing beef, patties, burgers or meatballs.

## Rule 3: the price must be valid on the date recorded
- Prices come only from each store's **search results and product pages**, which show today's shelf price. Never from flyers or next-week previews.
- A sale that says it **starts later** is skipped. Today's regular price is recorded instead, and the note says `future sale skipped`.
- A sale's **end date** is recorded in the notes when the site shows one (e.g. `sale ends 2026-11-04`). An expired sale is skipped.
- If a sale shows no dates, it's recorded and the note says `sale dates not shown`.

## Rule 4: record sales and regular prices
- On sale = a sale, rollback or clearance label, or a "was" price above the current price.
- On-sale rows record `price` = the sale price, `regular_price` = the "was" price, and `on_sale` = TRUE. Otherwise both prices are the same and `on_sale` = FALSE.
- Multi-buy-only prices (e.g. "2 for $6") are recorded and flagged `multi-buy`.

## Rule 5: no guessing
- Exactly what the page shows is recorded. Nothing is estimated, and no price is reused from another day.
- A failed page is retried once, then marked `failed`. If the agent calculates a unit price itself, it says so in the notes.
- If a robot check or CAPTCHA appears, the agent does not try to get past it. The rows are marked `failed`.
- The browser agent only reads pages. It never adds to cart, checks out or changes account details.

## Output
- **Columns:** `date, store, owner, item_id, product_name, size, price, regular_price, on_sale, unit_price, unit, status, notes`
- **Files:** `grocery_YYYY-MM-DD.csv` (cloud agent, 60 rows) and `grocery_wm-metro_YYYY-MM-DD.csv` (browser agent, 30 rows)
- **Run log:** every run adds a one-line summary: rows ok, not found and failed, sales, skipped future sales, and any problems.

## What changed from v1 (Oct 11–28)
| v1 (Oct 11–28) | v2 (from Oct 29) | Why |
|---|---|---|
| Cheapest matching product each day | One fixed product per store | The cheapest product changed from day to day, which mixed different products into one price series |
| Organic excluded for some items only | Regular products only, for every item | Organic, mini and grass-fed rows appeared in v1 |
| No sale-date checks | Today's price only; sale dates recorded | To make sure no future sale prices are included |
| 4 stores | 6 stores (Walmart and Metro added) | Walmart and Metro work through a signed-in browser |
| Ended Nov 9 | Ends Dec 1 | So every day of the month (1–31) is covered |

**Cleaning v1 data:** 4 off-spec rows from Oct 11 (organic and mini carrots, lactose-free cheddar) and 37 grass-fed beef rows were removed. Then only rows for each store's fixed product were kept, leaving 876 rows.
