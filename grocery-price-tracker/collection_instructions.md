# Collection instructions (AI agent prompt)

The tracker runs as a **daily scheduled AI agent** (Claude), every morning at 6:53 am Toronto time from Oct 11 to Nov 9, 2026. Each run starts fresh and follows the instructions below exactly. They're reproduced here so the method is transparent and repeatable.

**Design choices**
- **Fixed basket, fixed rules:** the same 15 items and the same matching rules every day, so prices are comparable over time.
- **Cheapest matching product by unit price**, store brands included. This reflects what a budget-conscious shopper would actually pay.
- **No guessing:** a failed page is retried once; anything still missing is recorded as `failed` or `no_match` with empty prices, never estimated.
- **Fallback search terms:** added after day 1, when Voilà returned no results for 5 of the original, more specific searches.

---

Daily grocery price collection (portfolio demo for Xue). Run unattended. Do not ask questions. Do the steps below, then stop.

GOAL
Record today's prices for a fixed basket of 15 grocery items at 4 Canadian online grocery stores. Save the results as one CSV file in Google Drive.

STORES (search URL; replace {q} with the URL-encoded search term)
- loblaws   | Loblaw | https://www.loblaws.ca/search?search-bar={q}
- nofrills  | Loblaw | https://www.nofrills.ca/search?search-bar={q}
- superstore| Loblaw | https://www.realcanadiansuperstore.ca/search?search-bar={q}
- voila     | Sobeys | https://voila.ca/search?q={q}

BASKET (item_id | search term | fallback term | what counts as a match)
Use the same search term at every store. If the first search returns no matching product, try the fallback term once before marking the row no_match.
1  milk        | 2% milk          | milk          | 2% cow's milk, 4 L (bag or jug). Not lactose-free, organic, microfiltered or flavoured.
2  eggs        | large eggs       | eggs          | Large white eggs, 12 count (a listing that doesn't state the colour counts as white). Not free-run, free-range, omega, organic or brown.
3  bread       | white bread      | bread         | White sliced sandwich bread, 570 to 675 g loaf
4  bananas     | bananas          | banana        | Regular fresh bananas (not organic, mini, baking or sliced). Use the per-kg price.
5  chicken     | chicken breast   | chicken       | Fresh boneless skinless chicken breast, any pack size. Use the per-kg price.
6  beef        | lean ground beef | ground beef   | Fresh lean ground beef (sirloin counts), any pack size. Use the per-kg price.
7  rice        | white rice       | rice          | Long grain white rice (not parboiled, jasmine, basmati or organic), 1.8 to 2 kg bag
8  pasta       | spaghetti        | pasta         | Dry spaghetti, 900 g
9  butter      | salted butter    | butter        | Salted butter, 454 g
10 cheese      | cheddar          | cheddar cheese| Cheddar BLOCK of any age (mild, medium, old), 400 g. Not slices, shredded or lactose-free.
11 apples      | gala apples      | apples        | Gala apples, loose or bagged. Use the per-kg price.
12 potatoes    | potatoes         | white potatoes| Fresh white, russet or yellow potatoes, a 2.27 to 4.54 kg (5 to 10 lb) bag. Not frozen, sweet, mini or organic. Use the per-kg price.
13 carrots     | carrots          | carrot        | Regular whole carrots, a 0.9 to 1.4 kg (2 to 3 lb) bag. Not organic, baby, mini, nantes or shredded. Use the per-kg price.
14 tomatoes    | diced tomatoes   | canned tomatoes| Canned diced or whole tomatoes, 796 mL (not fire-roasted or flavoured)
15 peanutbutter| peanut butter    | peanut        | Smooth peanut butter, 1 kg

RULES
- Use WebFetch for each store × item: about 60 fetches in total. Fetches are independent, so run several in parallel.
- Ask WebFetch to list every product on the page with its name, size, current price, regular/was price, unit price and any condition such as "min 2" or "multi-buy". Ignore sponsored products only if they don't match the spec.
- Pick the CHEAPEST product that matches the spec. Use the unit price to compare, and include store brands (No Name, PC, Compliments). Record exactly what the page shows. Never estimate, never guess, and never reuse an earlier day's price. If you calculate a unit price yourself from price ÷ size, say so in notes.
- If the cheapest price only applies when buying several (e.g. "2 for $6", "min 2"), still record it, but write "multi-buy" in notes.
- If a fetch fails, retry it once. If it still fails, or nothing matches after the fallback term, write the row with status = failed or no_match and leave the price fields empty.
- Prices come from each website's default store. Record the store location only if the page shows it.

OUTPUT
Create one CSV with a header row and 60 data rows, in this column order:
date,store,owner,item_id,product_name,size,price,regular_price,on_sale,unit_price,unit,status,notes
- date = today, YYYY-MM-DD, America/Toronto time
- price = the shelf price of the product or pack, a number with no $ sign. For items sold by weight, use the approximate pack price shown.
- regular_price = the was-price if the product is on sale, otherwise the same as price
- on_sale = TRUE or FALSE
- unit_price + unit = e.g. 1.96 and per_kg. Use per_kg for solids, per_L for liquids, per_each for eggs. Convert per-lb prices to per-kg (× 2.2046) and per-100g prices to per-kg (× 10).
- status = ok, no_match or failed
- Quote any field that contains a comma.

Save it as grocery_YYYY-MM-DD.csv in the project's Google Drive data folder. If a file with today's name already exists, add _2 rather than overwriting it.

FINISH
Reply with one line: the date, how many rows are ok, no_match and failed, and the total cost of the basket per store, counting ok rows only.
