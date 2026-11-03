"""Seller churn prediction with a rolling backtest (Olist marketplace data).

Decisions (set by Xue, see docs/decisions.md):
  1. Churn      = an active seller places no orders in the next 90 days.
  2. Active     = at least 1 order in the 90 days before the cutoff date.
  3. Small sellers stay in; results are scored in money (sales at risk).
  4. Backtest   = monthly cutoffs; each model trains only on cutoffs whose 90-day
                  outcome was already known on the test date (no peeking).
  5. Features   = sales trend + service quality + reviews + seller profile.
  6. Goal       = sales at risk reached when outreach is limited to the top K sellers a month.

Usage:
    python churn_pipeline.py --data ../data/raw --out ../outputs
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# ---------------------------------------------------------------- settings
CHURN_DAYS = 90          # decision 1: churn window
ACTIVE_DAYS = 90         # decision 2: active = ordered in the last 90 days
DATA_END = pd.Timestamp("2018-08-31")   # the Olist data is complete to the end of Aug 2018
FIRST_CUTOFF = pd.Timestamp("2017-04-01")  # first cutoff with a full 90-day look-back
MIN_TRAIN_CUTOFFS = 3    # smallest number of past months a model needs before it is tested
TOP_K = 100              # decision 6: sellers contacted per month
SEED = 42

NUMERIC = [
    "orders_30", "orders_90", "orders_prev90", "orders_trend",
    "gmv_30", "gmv_90", "gmv_prev90", "gmv_trend",
    "days_since_last_order", "tenure_days", "orders_total", "avg_order_value_90",
    "late_rate_90", "review_avg_90", "low_review_share_90", "n_categories_90",
]
CATEGORICAL = ["seller_state", "top_category", "origin"]
FEATURES = NUMERIC + CATEGORICAL


# ---------------------------------------------------------------- loading
def load_seller_orders(data_dir: Path) -> pd.DataFrame:
    """One row per (order, seller): sales, dates, lateness, review and category."""
    d = Path(data_dir)
    orders = pd.read_csv(
        d / "olist_orders_dataset.csv",
        parse_dates=["order_purchase_timestamp", "order_delivered_customer_date",
                     "order_estimated_delivery_date"],
    )
    items = pd.read_csv(d / "olist_order_items_dataset.csv")
    reviews = pd.read_csv(d / "olist_order_reviews_dataset.csv")
    products = pd.read_csv(d / "olist_products_dataset.csv")
    trans = pd.read_csv(d / "product_category_name_translation.csv")

    # canceled / unavailable orders are not real sales
    orders = orders[~orders["order_status"].isin(["canceled", "unavailable"])]
    orders = orders[orders["order_purchase_timestamp"] <= DATA_END + pd.Timedelta(days=1)]

    # one review score per order (the latest one)
    reviews = (reviews.sort_values("review_answer_timestamp")
               .drop_duplicates("order_id", keep="last")[["order_id", "review_score"]])

    items = items.merge(products[["product_id", "product_category_name"]], on="product_id", how="left")
    items = items.merge(trans, on="product_category_name", how="left")
    items["category"] = items["product_category_name_english"].fillna(items["product_category_name"])
    items["category"] = items["category"].fillna("unknown")

    so = (items.groupby(["order_id", "seller_id"])
          .agg(gmv=("price", "sum"), category=("category", "first"))
          .reset_index())
    so = so.merge(orders[["order_id", "order_purchase_timestamp",
                          "order_delivered_customer_date", "order_estimated_delivery_date"]],
                  on="order_id", how="inner")
    so = so.merge(reviews, on="order_id", how="left")

    delivered = so["order_delivered_customer_date"].notna()
    so["late"] = np.where(delivered, (so["order_delivered_customer_date"]
                                      > so["order_estimated_delivery_date"]).astype(float), np.nan)
    so = so.rename(columns={"order_purchase_timestamp": "ts"})
    return so[["order_id", "seller_id", "ts", "gmv", "category", "late", "review_score"]]


def load_sellers(data_dir: Path) -> pd.DataFrame:
    """Seller state and sign-up channel (from the marketing funnel, when available)."""
    d = Path(data_dir)
    sellers = pd.read_csv(d / "olist_sellers_dataset.csv")[["seller_id", "seller_state"]]
    mql, deals = d / "olist_marketing_qualified_leads_dataset.csv", d / "olist_closed_deals_dataset.csv"
    if mql.exists() and deals.exists():
        leads = pd.read_csv(mql)[["mql_id", "origin"]]
        won = pd.read_csv(deals)[["mql_id", "seller_id"]].merge(leads, on="mql_id", how="left")
        sellers = sellers.merge(won[["seller_id", "origin"]], on="seller_id", how="left")
    else:
        sellers["origin"] = np.nan
    sellers["origin"] = sellers["origin"].fillna("not_in_funnel")
    return sellers


# ---------------------------------------------------------------- features
def _window(so: pd.DataFrame, cutoff: pd.Timestamp, start_days: int, end_days: int) -> pd.DataFrame:
    """Orders with  cutoff - start_days <= ts < cutoff - end_days  (only the past)."""
    lo = cutoff - pd.Timedelta(days=start_days)
    hi = cutoff - pd.Timedelta(days=end_days)
    return so[(so["ts"] >= lo) & (so["ts"] < hi)]


def build_snapshot(so: pd.DataFrame, sellers: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
    """Features and churn label for every active seller at one cutoff date.

    Features use only orders BEFORE the cutoff. The label looks at the 90 days AFTER it.
    """
    past = so[so["ts"] < cutoff]
    w30 = _window(so, cutoff, 30, 0)
    w90 = _window(so, cutoff, ACTIVE_DAYS, 0)
    wprev = _window(so, cutoff, 2 * ACTIVE_DAYS, ACTIVE_DAYS)

    active = w90["seller_id"].unique()               # decision 2: who is active
    if len(active) == 0:
        return pd.DataFrame()
    df = pd.DataFrame({"seller_id": active}).set_index("seller_id")

    def agg(frame, name_orders, name_gmv):
        g = frame.groupby("seller_id").agg(**{name_orders: ("order_id", "nunique"), name_gmv: ("gmv", "sum")})
        return g

    df = df.join(agg(w30, "orders_30", "gmv_30")).join(agg(w90, "orders_90", "gmv_90"))
    df = df.join(agg(wprev, "orders_prev90", "gmv_prev90"))
    for c in ["orders_30", "gmv_30", "orders_prev90", "gmv_prev90"]:
        df[c] = df[c].fillna(0.0)
    # trend: recent 90 days vs the 90 days before (+1 keeps it defined when the earlier period is empty)
    df["orders_trend"] = (df["orders_90"] + 1) / (df["orders_prev90"] + 1)
    df["gmv_trend"] = (df["gmv_90"] + 1) / (df["gmv_prev90"] + 1)

    last = past.groupby("seller_id")["ts"].max()
    first = past.groupby("seller_id")["ts"].min()
    df["days_since_last_order"] = (cutoff - last.reindex(df.index)).dt.days
    df["tenure_days"] = (cutoff - first.reindex(df.index)).dt.days
    df["orders_total"] = past.groupby("seller_id")["order_id"].nunique().reindex(df.index)
    df["avg_order_value_90"] = df["gmv_90"] / df["orders_90"]

    # service quality and reviews over the last 90 days
    df["late_rate_90"] = w90.groupby("seller_id")["late"].mean()
    df["review_avg_90"] = w90.groupby("seller_id")["review_score"].mean()
    df["low_review_share_90"] = (w90.assign(low=(w90["review_score"] <= 2).where(w90["review_score"].notna()))
                                 .groupby("seller_id")["low"].mean())
    df["n_categories_90"] = w90.groupby("seller_id")["category"].nunique()
    top_cat = (w90.groupby(["seller_id", "category"])["gmv"].sum().reset_index()
               .sort_values("gmv", ascending=False).drop_duplicates("seller_id").set_index("seller_id")["category"])
    df["top_category"] = top_cat

    df = df.join(sellers.set_index("seller_id")[["seller_state", "origin"]])
    df["seller_state"] = df["seller_state"].fillna("unknown")
    df["origin"] = df["origin"].fillna("not_in_funnel")

    # label: no orders in the next 90 days
    future = so[(so["ts"] >= cutoff) & (so["ts"] < cutoff + pd.Timedelta(days=CHURN_DAYS))]
    df["churned"] = (~df.index.isin(future["seller_id"].unique())).astype(int)
    df["cutoff"] = cutoff
    return df.reset_index()


def cutoff_dates() -> list[pd.Timestamp]:
    """Month starts from FIRST_CUTOFF while the 90-day outcome still fits inside the data."""
    last = DATA_END - pd.Timedelta(days=CHURN_DAYS)
    return list(pd.date_range(FIRST_CUTOFF, last, freq="MS"))


def build_panel(so: pd.DataFrame, sellers: pd.DataFrame) -> pd.DataFrame:
    snaps = [build_snapshot(so, sellers, c) for c in cutoff_dates()]
    panel = pd.concat([s for s in snaps if len(s)], ignore_index=True)
    # keep the most frequent categories / states, group the rest, so one-hot columns stay small
    for col, n in [("top_category", 12), ("seller_state", 8)]:
        keep = panel[col].value_counts().nlargest(n).index
        panel[col] = panel[col].where(panel[col].isin(keep), "other")
    return panel


# ---------------------------------------------------------------- models
def make_model(kind: str) -> Pipeline:
    cat = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    if kind == "logistic":
        pre = ColumnTransformer([
            ("num", Pipeline([("imp", SimpleImputer(strategy="median")),
                              ("sc", StandardScaler())]), NUMERIC),
            ("cat", cat, CATEGORICAL)])
        est = LogisticRegression(max_iter=2000, C=0.5)
    elif kind == "gradient_boosting":
        pre = ColumnTransformer([("num", "passthrough", NUMERIC), ("cat", cat, CATEGORICAL)])
        est = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=200,
                                             random_state=SEED)
    else:
        raise ValueError(kind)
    return Pipeline([("pre", pre), ("model", est)])


# ---------------------------------------------------------------- scoring in money
def sales_at_risk_reached(test: pd.DataFrame, score: np.ndarray, k: int) -> dict:
    """Contact the k highest-scored sellers. How much of the sales at risk do we reach?

    Sales at risk = a seller's sales in the 90 days before the cutoff, counted only for
    sellers who really did churn. 'Reached' = churners among the k contacted.
    """
    at_risk_total = float((test["gmv_90"] * test["churned"]).sum())
    k = min(k, len(test))
    top = test.assign(_s=score).nlargest(k, "_s")
    reached = float((top["gmv_90"] * top["churned"]).sum())
    return {
        "sales_at_risk_total": at_risk_total,
        "sales_at_risk_reached": reached,
        "share_reached": reached / at_risk_total if at_risk_total else np.nan,
        "churners_in_top_k": int(top["churned"].sum()),
    }


def rolling_backtest(panel: pd.DataFrame, top_k: int = TOP_K) -> pd.DataFrame:
    """Monthly rolling backtest. For each test cutoff T:
       train on cutoffs C with C + 90 days <= T (their outcome was known on date T),
       score the sellers active at T, compare with what really happened."""
    cuts = sorted(panel["cutoff"].unique())
    rows = []
    for t in cuts:
        train_cuts = [c for c in cuts if c + pd.Timedelta(days=CHURN_DAYS) <= t]
        if len(train_cuts) < MIN_TRAIN_CUTOFFS:
            continue
        train = panel[panel["cutoff"].isin(train_cuts)]
        test = panel[panel["cutoff"] == t]
        if train["churned"].nunique() < 2 or test["churned"].nunique() < 2:
            continue

        scores = {
            # simple rule most teams would start with: the longer a seller is silent, the riskier
            "rule_days_since_last_order": test["days_since_last_order"].to_numpy(dtype=float),
            # a second simple rule: biggest recent sellers first (what a sales team may do by default)
            "rule_biggest_sellers": test["gmv_90"].to_numpy(dtype=float),
        }
        for kind in ["logistic", "gradient_boosting"]:
            m = make_model(kind).fit(train[FEATURES], train["churned"])
            scores[kind] = m.predict_proba(test[FEATURES])[:, 1]

        for name, s in scores.items():
            money = sales_at_risk_reached(test, s, top_k)
            rows.append({
                "test_cutoff": t, "model": name,
                "n_train_rows": len(train), "n_test_sellers": len(test),
                "churn_rate": test["churned"].mean(),
                "auc": roc_auc_score(test["churned"], s),
                "avg_precision": average_precision_score(test["churned"], s),
                **money,
            })
    return pd.DataFrame(rows)


def summarize(bt: pd.DataFrame) -> pd.DataFrame:
    g = bt.groupby("model")
    out = g.agg(
        months_tested=("test_cutoff", "nunique"),
        mean_auc=("auc", "mean"),
        mean_avg_precision=("avg_precision", "mean"),
        sales_at_risk_total=("sales_at_risk_total", "sum"),
        sales_at_risk_reached=("sales_at_risk_reached", "sum"),
        churners_in_top_k=("churners_in_top_k", "sum"),
    )
    out["share_reached"] = out["sales_at_risk_reached"] / out["sales_at_risk_total"]
    return out.sort_values("share_reached", ascending=False).reset_index()


def feature_importance(panel: pd.DataFrame) -> pd.DataFrame:
    """Which features matter most? Permutation importance on the final test month."""
    cuts = sorted(panel["cutoff"].unique())
    t = cuts[-1]
    train = panel[panel["cutoff"] + pd.Timedelta(days=CHURN_DAYS) <= t]
    test = panel[panel["cutoff"] == t]
    m = make_model("gradient_boosting").fit(train[FEATURES], train["churned"])
    r = permutation_importance(m, test[FEATURES], test["churned"], scoring="roc_auc",
                               n_repeats=10, random_state=SEED)
    return (pd.DataFrame({"feature": FEATURES, "auc_drop": r.importances_mean, "std": r.importances_std})
            .sort_values("auc_drop", ascending=False).reset_index(drop=True))


# ---------------------------------------------------------------- charts
def make_charts(bt: pd.DataFrame, summary: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    palette = {"gradient_boosting": "#1f4e79", "logistic": "#5b9bd5",
               "rule_days_since_last_order": "#7f7f7f", "rule_biggest_sellers": "#bfbfbf"}
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for name, g in bt.groupby("model"):
        ax.plot(g["test_cutoff"], g["share_reached"] * 100, marker="o", label=name, color=palette.get(name))
    ax.set_ylabel(f"% of sales at risk reached (top {TOP_K} sellers)")
    ax.set_title("Backtest: share of at-risk sales reached each month")
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "backtest_sales_reached.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.5))
    s = summary.sort_values("share_reached")
    ax.barh(s["model"], s["share_reached"] * 100, color=[palette.get(m) for m in s["model"]])
    ax.set_xlabel("% of at-risk sales reached, all test months")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "model_comparison.png", dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- main
def run(data_dir: Path, out_dir: Path, top_k: int = TOP_K) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    so = load_seller_orders(data_dir)
    sellers = load_sellers(data_dir)
    panel = build_panel(so, sellers)
    bt = rolling_backtest(panel, top_k)
    summary = summarize(bt)
    imp = feature_importance(panel)

    bt.to_csv(out / "backtest_by_month.csv", index=False)
    summary.to_csv(out / "backtest_summary.csv", index=False)
    imp.to_csv(out / "feature_importance.csv", index=False)
    make_charts(bt, summary, out)
    return {"panel": panel, "backtest": bt, "summary": summary, "importance": imp}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/raw")
    ap.add_argument("--out", default="../outputs")
    ap.add_argument("--top-k", type=int, default=TOP_K)
    a = ap.parse_args()
    res = run(Path(a.data), Path(a.out), a.top_k)
    print(res["summary"].to_string(index=False))
