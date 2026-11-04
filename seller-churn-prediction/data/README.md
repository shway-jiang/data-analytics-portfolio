# Data

Real, anonymized data from Olist, a Brazilian online marketplace. It is too large to store on GitHub, so download it from Kaggle and unzip the CSV files into `data/raw/`:

1. [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
2. [Marketing Funnel by Olist](https://www.kaggle.com/datasets/olistbr/marketing-funnel-olist) (optional: adds each seller's sign-up channel)

Files used: `olist_orders_dataset.csv`, `olist_order_items_dataset.csv`, `olist_order_reviews_dataset.csv`, `olist_products_dataset.csv`, `product_category_name_translation.csv`, `olist_sellers_dataset.csv`, and (optional) `olist_marketing_qualified_leads_dataset.csv`, `olist_closed_deals_dataset.csv`.

The order data runs from 2017 to August 2018. Orders after Aug 21, 2018 are ignored because daily orders fade from Aug 22 and stop on Aug 29.
