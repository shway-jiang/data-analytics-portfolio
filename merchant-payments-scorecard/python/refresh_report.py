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


def load_raw(con: sqlite3.Connection) -> None:
    for name in ["merchants", "monthly_volume", "support_tickets"]:
        pd.read_csv(RAW / f"{name}.csv").to_sql(f"raw_{name}", con, index=False, if_exists="replace")


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
