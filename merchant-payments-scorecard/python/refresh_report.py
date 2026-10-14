"""
Monthly scorecard refresh.

One command rebuilds everything from the raw files:
  1. loads the raw CSVs into a SQL database
  2. runs the data-quality checks   (sql/01_data_quality.sql)
  3. builds the clean tables        (sql/02_clean_tables.sql)
  4. runs the scorecard queries     (sql/03_scorecard_queries.sql) -> outputs/*.csv
  5. writes the Excel scorecard     -> outputs/merchant_scorecard.xlsx
  6. draws the dashboard pages      -> dashboard/*.png

SQLite is used so it runs anywhere with no setup. The SQL is standard and
moves to Snowflake with the small changes noted in the .sql files.

Run:  python refresh_report.py
"""

import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
SQL = ROOT / "sql"
OUT = ROOT / "outputs"
DASH = ROOT / "dashboard"


RAW_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "order_payments": "olist_order_payments_dataset.csv",
    "order_reviews": "olist_order_reviews_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
    "marketing_qualified_leads": "olist_marketing_qualified_leads_dataset.csv",
    "closed_deals": "olist_closed_deals_dataset.csv",
}


def load_raw(con: sqlite3.Connection) -> None:
    missing = [f for f in RAW_FILES.values() if not (RAW / f).exists()]
    if missing:
        raise FileNotFoundError(f"Download the Olist files into data/raw/ first (see data/README.md). Missing: {missing}")
    for table, file in RAW_FILES.items():
        df = pd.read_csv(RAW / file)
        if table == "order_reviews":   # free-text comments aren't used; skip them to save memory
            df = df.drop(columns=["review_comment_title", "review_comment_message"])
        df.to_sql(f"raw_{table}", con, index=False, if_exists="replace")
    # indexes on the join keys (Snowflake doesn't need these)
    con.executescript("""
        CREATE INDEX ix_items_order    ON raw_order_items(order_id);
        CREATE INDEX ix_items_seller   ON raw_order_items(seller_id);
        CREATE INDEX ix_items_product  ON raw_order_items(product_id);
        CREATE INDEX ix_pay_order      ON raw_order_payments(order_id);
        CREATE INDEX ix_rev_order      ON raw_order_reviews(order_id);
        CREATE INDEX ix_orders_id      ON raw_orders(order_id);
        CREATE INDEX ix_cust_id        ON raw_customers(customer_id);
        CREATE INDEX ix_prod_id        ON raw_products(product_id);
        CREATE INDEX ix_cat_name       ON raw_category_translation(product_category_name);
        CREATE INDEX ix_mql_id         ON raw_marketing_qualified_leads(mql_id);
        CREATE INDEX ix_deal_mql       ON raw_closed_deals(mql_id);
    """)


def named_queries(path: Path) -> dict:
    """Split a .sql file into {name: query} using the '-- name:' markers."""
    parts = re.split(r"^-- name:\s*(\w+)\s*$", path.read_text(), flags=re.M)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts), 2)}


def run(con: sqlite3.Connection) -> dict:
    results = {}
    results.update({k: pd.read_sql(q, con) for k, q in named_queries(SQL / "01_data_quality.sql").items()})
    con.executescript((SQL / "02_clean_tables.sql").read_text())
    results.update({k: pd.read_sql(q, con) for k, q in named_queries(SQL / "03_scorecard_queries.sql").items()})
    OUT.mkdir(exist_ok=True)
    for name, df in results.items():
        df.to_csv(OUT / f"{name}.csv", index=False)
    return results


def main() -> dict:
    con = sqlite3.connect(":memory:")
    load_raw(con)
    results = run(con)

    from build_excel import build_excel
    from build_dashboard import build_dashboard
    build_excel(results, OUT / "merchant_scorecard.xlsx")
    build_dashboard(results, DASH)
    return results


if __name__ == "__main__":
    res = main()
    for name, df in res.items():
        print(f"\n== {name} ==")
        print(df.to_string(index=False))
