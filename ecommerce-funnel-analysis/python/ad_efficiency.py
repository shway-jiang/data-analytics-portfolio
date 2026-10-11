"""
Ad efficiency analysis: Facebook ad campaigns (Kaggle "Clicks conversion tracking").

Input : data/KAG_conversion_data.csv  (1,143 ads, 3 campaigns)
Output: data/ad_metrics_by_segment.csv

Metrics per campaign / age / gender / interest:
  CTR, CPC, CPM, click-to-sale rate, cost per approved conversion,
  and ROAS under an ASSUMED revenue per sale (the dataset has no revenue).

Run from the ecommerce-funnel-analysis folder:  python python/ad_efficiency.py
"""
import pandas as pd

ASSUMED_REVENUE_PER_SALE = 100  # assumption, stated in the report

df = pd.read_csv("data/KAG_conversion_data.csv")

# Data checks
assert df.isna().sum().sum() == 0, "unexpected missing values"
assert not df.duplicated().any(), "unexpected duplicate rows"

df["campaign"] = df["xyz_campaign_id"].map(
    {916: "Campaign A", 936: "Campaign B", 1178: "Campaign C"}
)

frames = []
for dim in ["campaign", "age", "gender", "interest"]:
    g = (
        df.groupby(dim)
        .agg(
            ads=("ad_id", "count"),
            impressions=("Impressions", "sum"),
            clicks=("Clicks", "sum"),
            spend=("Spent", "sum"),
            conversions=("Total_Conversion", "sum"),
            approved=("Approved_Conversion", "sum"),
        )
        .reset_index()
        .rename(columns={dim: "segment"})
    )
    g.insert(0, "dimension", dim)
    frames.append(g)

m = pd.concat(frames)
m["segment"] = m["segment"].astype(str)
m["ctr"] = m["clicks"] / m["impressions"]
m["cpc"] = m["spend"] / m["clicks"]
m["cpm"] = m["spend"] / m["impressions"] * 1000
m["click_to_approved_rate"] = m["approved"] / m["clicks"]
m["cost_per_approved"] = m["spend"] / m["approved"]
m["assumed_revenue"] = m["approved"] * ASSUMED_REVENUE_PER_SALE
m["assumed_roas"] = m["assumed_revenue"] / m["spend"]

m.round(4).to_csv("data/ad_metrics_by_segment.csv", index=False)
print(m[m["dimension"] != "interest"][
    ["dimension", "segment", "spend", "approved", "cost_per_approved", "assumed_roas"]
].round(2).to_string(index=False))
