# Data

This project uses two free public datasets from **Olist**, a Brazilian online marketplace. The data is real but anonymized (company and customer names replaced). They're too large to store on GitHub, so download them from Kaggle and unzip the CSV files into `data/raw/`:

1. [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce): about 100,000 orders from 2016 to 2018, with items, payments, reviews, sellers and products.
2. [Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist): 8,000 seller leads from 2017 to 2018 and the 842 that signed up to sell.

Files used (`olist_geolocation_dataset.csv` isn't needed):

| File | Rows | Used for |
|---|---|---|
| `olist_orders_dataset.csv` | 99,441 | order status and timestamps (purchase, payment approval, shipping, delivery) |
| `olist_order_items_dataset.csv` | 112,650 | items, prices, freight, seller and shipping deadline |
| `olist_order_payments_dataset.csv` | 103,886 | payment method, installments, amount paid |
| `olist_order_reviews_dataset.csv` | 99,224 | customer review score |
| `olist_customers_dataset.csv` | 99,441 | customer state |
| `olist_sellers_dataset.csv` | 3,095 | sellers |
| `olist_products_dataset.csv` | 32,951 | product category |
| `product_category_name_translation.csv` | 71 | English category names |
| `olist_marketing_qualified_leads_dataset.csv` | 8,000 | seller leads and their marketing channel |
| `olist_closed_deals_dataset.csv` | 842 | leads that became signed sellers |
