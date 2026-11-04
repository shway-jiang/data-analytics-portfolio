"""Seller churn prediction with a rolling backtest (Olist marketplace data).

Decisions (set by Xue, see docs/decisions.md):
  1. Churn      = an active seller places no orders in the next 90 days.
  2. Active     = at least 1 order in the 90 days before the cutoff date.
  3. Small sellers stay in; results are scored in money (sales at risk).
  4. Backtest   = monthly cutoffs; each model trains only on cutoffs whose 90-day
                  outcome was already known on the test date (no peeking).
  5. Features   = sales trend + service quality + reviews + seller profile.
  6. Goal       = sales at risk reached when outreach is limited to the top K sellers a month.

Final choice (run 3): the headline model is logistic regression ranked by churn probability x
gmv_90 ("x_sales"); gradient boosting x_sales is the comparison. Sales weights (run 2) did not help
and are not used. No further variants will be tried. AUC / average precision always use the churn
probability. auc_by_seller_size.csv compares the top 10% of sellers by gmv_90 with the rest;
spread_by_model.csv, backtest_by_top_k.csv and what_if_savings.csv are the run 3 checks.

Review fixes: features use only what was known on the cutoff date, rare categories are grouped using
training rows only, the data ends before its incomplete last days (so May 2018 is the last test
month), money_each_order_once.csv counts repeated sales once, and rule_silent_x_sales is a third
simple rule (days since last order x gmv_90).

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
# last day with normal order volume: daily orders fade from Aug 22 and stop on Aug 29, 2018.
# A 90-day outcome must fit before this date, so May 2018 is the last test month.
DATA_END = pd.Timestamp("2018-08-21")
FIRST_CUTOFF = pd.Timestamp("2017-04-01")  # first cutoff with a full 90-day look-back
MIN_TRAIN_CUTOFFS = 3    # smallest number of past months a model needs before it is tested
TOP_K = 100              # decision 6: sellers contacted per month
SEED = 42
WEIGHT_CLIP_Q = 0.99     # training weights: sales above this percentile of the TRAINING rows are capped
MIN_WEIGHT = 1.0         # training weights: floor in R$ so no row gets a zero weight
BIG_SELLER_Q = 0.90      # "big seller" = top 10% of the active sellers by gmv_90 on the test date
MODEL_KINDS = ["logistic", "gradient_boosting"]
# how a model's probability is turned into a contact list
#   plain: rank by churn probability        x_sales: rank by probability x gmv_90
#   weighted: trained with sales weights    weighted_x_sales: both
VARIANTS = ["plain", "x_sales"]   # run 2 also tried "weighted" and "weighted_x_sales" (not needed, see docs)
TOP_KS = [50, 100, 200]  # outreach sizes for the robustness check
MAIN_MODEL = "logistic_x_sales"            # headline model, fixed in run 3
COMPARISON_MODEL = "gradient_boosting_x_sales"
BENCHMARK = "rule_biggest_sellers"
SILENT_X_SALES = "rule_silent_x_sales"     # days since last order x gmv_90: money-aware rule, no model
APPROACHES = [MAIN_MODEL, COMPARISON_MODEL, SILENT_X_SALES, BENCHMARK, "rule_days_since_last_order"]
WHATIF_SAVED = [0.10, 0.20, 0.30]          # assumptions for the what-if table, not results
RARE_GROUPS = [("top_category", 12), ("seller_state", 8)]   # keep the n most frequent, group the rest

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
    reviews = pd.read_csv(d / "olist_order_reviews_dataset.csv", parse_dates=["review_answer_timestamp"])
    products = pd.read_csv(d / "olist_products_dataset.csv")
    trans = pd.read_csv(d / "product_category_name_translation.csv")

    # canceled / unavailable orders are not real sales
    orders = orders[~orders["order_status"].isin(["canceled", "unavailable"])]
    orders = orders[orders["order_purchase_timestamp"] <= DATA_END + pd.Timedelta(days=1)]

    # one review score per order (the latest one)
    reviews = (reviews.sort_values("review_answer_timestamp")
               .drop_duplicates("order_id", keep="last")[["order_id", "review_score", "review_answer_timestamp"]])

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
    so = so.rename(columns={"order_purchase_timestamp": "ts", "order_delivered_customer_date": "delivered_at",
                            "review_answer_timestamp": "review_at"})
    return so[["order_id", "seller_id", "ts", "gmv", "category", "late", "review_score", "delivered_at", "review_at"]]


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

    Features use only what was known BEFORE the cutoff: orders placed before it, and a late flag or
    review only if the delivery or review had already happened. The label looks at the 90 days AFTER it.
    """
    past = so[so["ts"] < cutoff]
    w30 = _window(so, cutoff, 30, 0)
    w90 = _window(so, cutoff, ACTIVE_DAYS, 0)
    # a delivery or review that happens after the cutoff was not known on the cutoff date
    w90 = w90.assign(late=w90["late"].where(w90["delivered_at"] < cutoff),
                     review_score=w90["review_score"].where(w90["review_at"] < cutoff))
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
    return pd.concat([s for s in snaps if len(s)], ignore_index=True)


def group_rare(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Keep the most frequent categories / states, group the rest, so one-hot columns stay small.
    Which ones to keep is decided from the training rows only."""
    train, test = train.copy(), test.copy()
    for col, n in RARE_GROUPS:
        keep = train[col].value_counts().nlargest(n).index
        train[col] = train[col].where(train[col].isin(keep), "other")
        test[col] = test[col].where(test[col].isin(keep), "other")
    return train, test


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
def top_sellers(test: pd.DataFrame, score: np.ndarray, k: int) -> pd.DataFrame:
    """The k highest-scored sellers."""
    return test.assign(_s=score).nlargest(min(k, len(test)), "_s")


def sales_at_risk_reached(test: pd.DataFrame, score: np.ndarray, k: int) -> dict:
    """Contact the k highest-scored sellers. How much of the sales at risk do we reach?

    Sales at risk = a seller's sales in the 90 days before the cutoff, counted only for
    sellers who really did churn. 'Reached' = churners among the k contacted.
    This is one month's view: summing it over months counts repeated sales again, because a
    seller who stops stays 'active' at later cutoffs. See count_each_order_once for reais totals.
    """
    at_risk_total = float((test["gmv_90"] * test["churned"]).sum())
    top = top_sellers(test, score, k)
    reached = float((top["gmv_90"] * top["churned"]).sum())
    return {
        "sales_at_risk_total": at_risk_total,
        "sales_at_risk_reached": reached,
        "share_reached": reached / at_risk_total if at_risk_total else np.nan,
        "churners_in_top_k": int(top["churned"].sum()),
    }


def training_weights(train: pd.DataFrame) -> np.ndarray:
    """Sales weights for training (run 2 only; NOT used in the final run, see docs/decisions.md).

    Uses ONLY the training rows. weight = gmv_90, capped at the 99th percentile of the training
    rows and floored at MIN_WEIGHT, then divided by its mean so the average weight is 1.
    """
    g = train["gmv_90"].to_numpy(dtype=float)
    cap = np.quantile(g, WEIGHT_CLIP_Q)
    w = np.clip(g, MIN_WEIGHT, max(cap, MIN_WEIGHT))
    return w / w.mean()


def _auc(y, s):
    return roc_auc_score(y, s) if len(np.unique(y)) == 2 else np.nan


def rolling_backtest(panel: pd.DataFrame, top_k: int = TOP_K, ks: list[int] = TOP_KS,
                     include_weighted: bool = False):
    """Monthly rolling backtest. For each test cutoff T:
       train on cutoffs C with C + 90 days <= T (their outcome was known on date T),
       score the sellers active at T, compare with what really happened.

    Returns (backtest by month at top_k, AUC for big vs small sellers by month,
             money reached by month at every size in ks, the sellers picked at every size).
    AUC and average precision always use the churn probability (or the rule's own score),
    never the probability x sales score. include_weighted=True re-creates the run 2 weighted
    variants (not needed, kept so run 2 can be reproduced).
    """
    ks = sorted(set(ks) | {top_k})
    cuts = sorted(panel["cutoff"].unique())
    rows, size_rows, k_rows, picks = [], [], [], []
    for t in cuts:
        train_cuts = [c for c in cuts if c + pd.Timedelta(days=CHURN_DAYS) <= t]
        if len(train_cuts) < MIN_TRAIN_CUTOFFS:
            continue
        train = panel[panel["cutoff"].isin(train_cuts)]
        test = panel[panel["cutoff"] == t]
        if train["churned"].nunique() < 2 or test["churned"].nunique() < 2:
            continue
        train, test = group_rare(train, test)
        gmv = test["gmv_90"].to_numpy(dtype=float)
        silent = test["days_since_last_order"].to_numpy(dtype=float)

        # name -> (probability or rule score used for AUC / AP, score used to rank the top K)
        entries = {
            # simple rule most teams would start with: the longer a seller is silent, the riskier
            "rule_days_since_last_order": (silent, silent),
            # a second simple rule: biggest recent sellers first (what a sales team may do by default)
            "rule_biggest_sellers": (gmv, gmv),
            # a third simple rule, same money-aware idea as x_sales but with no model
            SILENT_X_SALES: (silent * gmv, silent * gmv),
        }
        w = training_weights(train) if include_weighted else None
        for kind in MODEL_KINDS:
            plain = make_model(kind).fit(train[FEATURES], train["churned"])
            p_plain = plain.predict_proba(test[FEATURES])[:, 1]
            entries[f"{kind}_plain"] = (p_plain, p_plain)
            entries[f"{kind}_x_sales"] = (p_plain, p_plain * gmv)   # expected money lost
            if include_weighted:
                weighted = make_model(kind).fit(train[FEATURES], train["churned"], model__sample_weight=w)
                p_wtd = weighted.predict_proba(test[FEATURES])[:, 1]
                entries[f"{kind}_weighted"] = (p_wtd, p_wtd)
                entries[f"{kind}_weighted_x_sales"] = (p_wtd, p_wtd * gmv)

        # big sellers = top 10% by gmv_90 among the sellers active on the test date (uses only
        # information available at the cutoff)
        big = gmv >= np.quantile(gmv, BIG_SELLER_Q)
        y = test["churned"].to_numpy()
        for name, (prob, rank_score) in entries.items():
            for k in ks:
                money = sales_at_risk_reached(test, rank_score, k)
                k_rows.append({"test_cutoff": t, "model": name, "top_k": k, **money})
                picks.append(top_sellers(test, rank_score, k)[["seller_id", "cutoff", "churned"]]
                             .assign(model=name, top_k=k))
                if k == top_k:
                    rows.append({
                        "test_cutoff": t, "model": name,
                        "n_train_rows": len(train), "n_test_sellers": len(test),
                        "churn_rate": test["churned"].mean(),
                        "auc": roc_auc_score(y, prob),
                        "avg_precision": average_precision_score(y, prob),
                        **money,
                    })
            for group, mask in [("top10pct_sellers", big), ("other_sellers", ~big)]:
                size_rows.append({
                    "test_cutoff": t, "model": name, "group": group,
                    "n_sellers": int(mask.sum()), "n_churners": int(y[mask].sum()),
                    "churn_rate": float(y[mask].mean()),
                    "gmv_90_cutoff_top10pct": float(np.quantile(gmv, BIG_SELLER_Q)),
                    "auc": _auc(y[mask], prob[mask]),
                })
    return pd.DataFrame(rows), pd.DataFrame(size_rows), pd.DataFrame(k_rows), pd.concat(picks, ignore_index=True)


def summarize(bt: pd.DataFrame, size: pd.DataFrame | None = None) -> pd.DataFrame:
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
    if size is not None:
        a = size.pivot_table(index="model", columns="group", values="auc", aggfunc="mean")
        out["mean_auc_top10pct_sellers"] = a["top10pct_sellers"]
        out["mean_auc_other_sellers"] = a["other_sellers"]
    return out.sort_values("share_reached", ascending=False).reset_index()


def _months_beating(share: pd.DataFrame, model: str, rule: str) -> float:
    return np.nan if model == rule else int((share[model] > share[rule]).sum())


def _as_counts(out: pd.DataFrame) -> pd.DataFrame:
    for c in ["months_beating_biggest_sellers_rule", "months_beating_silent_x_sales_rule"]:
        out[c] = out[c].astype("Int64")
    return out


def spread_by_model(bt: pd.DataFrame, models: list[str] = APPROACHES) -> pd.DataFrame:
    """Total share reached plus how it moves from month to month, and how often each approach
    beats the 'biggest recent sellers' and 'silent x sales' rules in the same month."""
    share = bt.pivot(index="test_cutoff", columns="model", values="share_reached")
    rows = []
    for m in models:
        g = bt[bt["model"] == m]
        rows.append({
            "model": m,
            "months_tested": share[m].notna().sum(),
            "share_reached_all_months": g["sales_at_risk_reached"].sum() / g["sales_at_risk_total"].sum(),
            "median_month": share[m].median(),
            "lowest_month": share[m].min(),
            "highest_month": share[m].max(),
            "months_beating_biggest_sellers_rule": _months_beating(share, m, BENCHMARK),
            "months_beating_silent_x_sales_rule": _months_beating(share, m, SILENT_X_SALES),
        })
    return _as_counts(pd.DataFrame(rows))


def by_top_k(bt_k: pd.DataFrame, models: list[str] = APPROACHES) -> pd.DataFrame:
    """Same backtest with 50, 100 and 200 sellers contacted a month."""
    rows = []
    for k, gk in bt_k.groupby("top_k"):
        share = gk.pivot(index="test_cutoff", columns="model", values="share_reached")
        for m in models:
            g = gk[gk["model"] == m]
            rows.append({
                "model": m, "top_k": int(k),
                "share_reached": g["sales_at_risk_reached"].sum() / g["sales_at_risk_total"].sum(),
                "months_beating_biggest_sellers_rule": _months_beating(share, m, BENCHMARK),
                "months_beating_silent_x_sales_rule": _months_beating(share, m, SILENT_X_SALES),
            })
    return _as_counts(pd.DataFrame(rows))


def _sales_once(so: pd.DataFrame, rows: pd.DataFrame) -> float:
    """Sales in the 90 days before each (seller, cutoff) in rows, counting each order only once."""
    m = rows[["seller_id", "cutoff"]].merge(so[["order_id", "seller_id", "ts", "gmv"]], on="seller_id")
    m = m[(m["ts"] >= m["cutoff"] - pd.Timedelta(days=ACTIVE_DAYS)) & (m["ts"] < m["cutoff"])]
    return float(m.drop_duplicates(["order_id", "seller_id"])["gmv"].sum())


def count_each_order_once(so: pd.DataFrame, panel: pd.DataFrame, picks: pd.DataFrame,
                          models: list[str] = APPROACHES) -> pd.DataFrame:
    """Reais totals over all test months with no repeats. A seller who stops selling stays 'active'
    at up to three monthly cutoffs, so adding up the months counts the same orders several times."""
    months = picks["cutoff"].unique()
    at_risk = panel[panel["cutoff"].isin(months) & (panel["churned"] == 1)]
    total = _sales_once(so, at_risk)
    rows = []
    for (m, k), g in picks[picks["model"].isin(models)].groupby(["model", "top_k"]):
        churners = g[g["churned"] == 1]
        reached = _sales_once(so, churners)
        rows.append({
            "model": m, "top_k": int(k),
            "sales_at_risk_total_once": total,
            "sales_at_risk_reached_once": reached,
            "share_reached_once": reached / total,
            "picks": len(g), "distinct_sellers_picked": g["seller_id"].nunique(),
            "churner_picks": len(churners), "distinct_churners_reached": churners["seller_id"].nunique(),
        })
    return pd.DataFrame(rows)


def what_if(money: pd.DataFrame, model: str = MAIN_MODEL, top_k: int = TOP_K) -> pd.DataFrame:
    """ASSUMPTION, not a result: if outreach saved a share of the sales at risk it reaches."""
    reached = money.loc[(money["model"] == model) & (money["top_k"] == top_k), "sales_at_risk_reached_once"].iloc[0]
    return pd.DataFrame({
        "model": model,
        "sales_at_risk_reached_once": reached,
        "assumed_share_saved": WHATIF_SAVED,
        "assumed_reais_saved": [reached * s for s in WHATIF_SAVED],
        "note": "assumption, not a result",
    })


def feature_importance(panel: pd.DataFrame) -> pd.DataFrame:
    """Which features matter most? Permutation importance on the final test month."""
    cuts = sorted(panel["cutoff"].unique())
    t = cuts[-1]
    train, test = group_rare(panel[panel["cutoff"] + pd.Timedelta(days=CHURN_DAYS) <= t], panel[panel["cutoff"] == t])
    m = make_model("gradient_boosting").fit(train[FEATURES], train["churned"])
    r = permutation_importance(m, test[FEATURES], test["churned"], scoring="roc_auc",
                               n_repeats=10, random_state=SEED)
    return (pd.DataFrame({"feature": FEATURES, "auc_drop": r.importances_mean, "std": r.importances_std})
            .sort_values("auc_drop", ascending=False).reset_index(drop=True))


# ---------------------------------------------------------------- charts
COLORS = {"logistic_x_sales": "#1f4e79", "gradient_boosting_x_sales": "#ed7d31",
          "logistic_plain": "#9dc3e6", "gradient_boosting_plain": "#f4b183",
          "rule_biggest_sellers": "#bfbfbf", "rule_days_since_last_order": "#7f7f7f",
          "rule_silent_x_sales": "#7030a0"}
LINE_ORDER = [BENCHMARK, "rule_days_since_last_order", SILENT_X_SALES, COMPARISON_MODEL, MAIN_MODEL]


def make_charts(bt: pd.DataFrame, summary: pd.DataFrame, size: pd.DataFrame,
                topk: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def finish(fig, ax, name):
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        fig.savefig(out / name, dpi=150)
        plt.close(fig)

    # 1) month by month: main model, comparison model and the three rules
    fig, ax = plt.subplots(figsize=(9, 4.5))
    for name in LINE_ORDER:
        g = bt[bt["model"] == name]
        ax.plot(g["test_cutoff"], g["share_reached"] * 100, marker="o", label=name, color=COLORS[name],
                lw=2.5 if name == MAIN_MODEL else 1.5)
    ax.set_ylabel(f"% of sales at risk reached (top {TOP_K} sellers)")
    ax.set_title("Backtest: share of at-risk sales reached each month")
    ax.legend(fontsize=8)
    finish(fig, ax, "backtest_sales_reached.png")

    # 2) all approaches, all months together
    fig, ax = plt.subplots(figsize=(8, 4))
    s = summary.sort_values("share_reached")
    ax.barh(s["model"], s["share_reached"] * 100, color=[COLORS[m] for m in s["model"]])
    ax.set_xlabel("% of at-risk sales reached, all test months")
    finish(fig, ax, "model_comparison.png")

    # 3) AUC for the biggest 10% of sellers vs the rest
    show = ["rule_days_since_last_order", "logistic_plain", "gradient_boosting_plain"]
    a = size[size["model"].isin(show)].groupby(["model", "group"])["auc"].mean().unstack().reindex(show)
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(len(show))
    ax.bar(x - 0.2, a["top10pct_sellers"], 0.4, label="top 10% of sellers by sales", color="#1f4e79")
    ax.bar(x + 0.2, a["other_sellers"], 0.4, label="all other sellers", color="#9dc3e6")
    ax.set_xticks(x)
    ax.set_xticklabels([m.replace("_", chr(10), 1) for m in show], fontsize=8)
    ax.set_ylabel("average AUC over the test months")
    ax.set_ylim(0.5, 1.0)
    ax.legend(fontsize=8)
    finish(fig, ax, "auc_by_seller_size.png")

    # 4) share reached vs number of sellers contacted
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for name in LINE_ORDER:
        g = topk[topk["model"] == name].sort_values("top_k")
        ax.plot(g["top_k"], g["share_reached"] * 100, marker="o", label=name, color=COLORS[name],
                lw=2.5 if name == MAIN_MODEL else 1.5)
    ax.set_xticks(sorted(topk["top_k"].unique()))
    ax.set_xlabel("sellers contacted a month")
    ax.set_ylabel("% of sales at risk reached")
    ax.legend(fontsize=8)
    finish(fig, ax, "share_by_top_k.png")


# ---------------------------------------------------------------- main
def run(data_dir: Path, out_dir: Path, top_k: int = TOP_K) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    so = load_seller_orders(data_dir)
    sellers = load_sellers(data_dir)
    panel = build_panel(so, sellers)
    bt, size, bt_k, picks = rolling_backtest(panel, top_k)
    summary = summarize(bt, size)
    spread = spread_by_model(bt)
    topk = by_top_k(bt_k)
    money = count_each_order_once(so, panel, picks)
    whatif = what_if(money, top_k=top_k)
    imp = feature_importance(panel)

    bt.to_csv(out / "backtest_by_month.csv", index=False)
    size.to_csv(out / "auc_by_seller_size.csv", index=False)
    summary.to_csv(out / "backtest_summary.csv", index=False)
    spread.to_csv(out / "spread_by_model.csv", index=False)
    topk.to_csv(out / "backtest_by_top_k.csv", index=False)
    money.to_csv(out / "money_each_order_once.csv", index=False)
    whatif.to_csv(out / "what_if_savings.csv", index=False)
    imp.to_csv(out / "feature_importance.csv", index=False)
    make_charts(bt, summary, size, topk, out)
    return {"panel": panel, "backtest": bt, "summary": summary, "size": size, "spread": spread,
            "top_k": topk, "money_once": money, "what_if": whatif, "importance": imp}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../data/raw")
    ap.add_argument("--out", default="../outputs")
    ap.add_argument("--top-k", type=int, default=TOP_K)
    a = ap.parse_args()
    res = run(Path(a.data), Path(a.out), a.top_k)
    print(res["summary"].to_string(index=False))
    print(res["spread"].to_string(index=False))
    print(res["top_k"].to_string(index=False))
    print(res["money_once"].to_string(index=False))
