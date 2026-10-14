"""
Generate a simulated dataset for a fictional Canadian merchant acquirer
(a company that lets small businesses accept card payments).

Real merchant payment data is confidential, so this script builds a
realistic stand-in. Every rule used to create the data is written below,
and the random seed is fixed, so anyone can re-create the exact same files.

Output (in ../data/raw/):
  merchants.csv        one row per merchant application
  monthly_volume.csv   one row per merchant, month and card type
  support_tickets.csv  one row per support ticket

A few data-quality problems are added on purpose (duplicates, missing
values, inconsistent labels, impossible timestamps) so the SQL checks
have something real to catch. They are listed at the bottom of this file.

Run:  python generate_data.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 2026
rng = np.random.default_rng(SEED)

OUT = Path(__file__).resolve().parent.parent / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

PERIOD_START = pd.Timestamp("2025-01-01")
PERIOD_END = pd.Timestamp("2026-06-30")
MONTHS = pd.period_range(PERIOD_START, PERIOD_END, freq="M")

# ----------------------------------------------------------------------------
# Business assumptions (all simulated)
# ----------------------------------------------------------------------------
CHANNELS = {
    #                      share  approval  decision_days  never_activate  activate_days  monthly_churn
    "Online Self-Signup":  (0.35, 0.82,     (1, 3),        0.30,           9,             0.030),
    "Direct Sales":        (0.25, 0.93,     (3, 8),        0.08,           5,             0.012),
    "Bank Partner Referral": (0.25, 0.94,   (4, 10),       0.06,           6,             0.008),
    "ISO Partner":         (0.15, 0.90,     (5, 12),       0.12,           8,             0.018),
}

INDUSTRIES = {
    # share, median monthly card volume ($), average ticket ($)
    "Restaurants":           (0.22, 38_000, 42),
    "Retail":                (0.20, 30_000, 55),
    "Grocery & Convenience": (0.08, 70_000, 38),
    "Health & Beauty":       (0.12, 14_000, 75),
    "Professional Services": (0.12, 20_000, 180),
    "Automotive":            (0.07, 45_000, 260),
    "Hospitality":           (0.06, 55_000, 210),
    "E-commerce":            (0.13, 25_000, 85),
}

PROVINCES = {"ON": 0.40, "QC": 0.20, "BC": 0.14, "AB": 0.12, "MB": 0.04,
             "SK": 0.03, "NS": 0.03, "NB": 0.02, "NL": 0.01, "PE": 0.01}

CARD_MIX = {"Interac Debit": 0.40, "Visa": 0.30, "Mastercard": 0.22, "Amex": 0.08}
CARD_MIX_ONLINE = {"Interac Debit": 0.05, "Visa": 0.50, "Mastercard": 0.35, "Amex": 0.10}

SEASONALITY = {1: 0.85, 2: 0.88, 3: 0.97, 4: 0.98, 5: 1.02, 6: 1.04,
               7: 1.05, 8: 1.04, 9: 0.99, 10: 1.00, 11: 1.10, 12: 1.25}

TICKET_CATEGORIES = {
    # share, median hours to resolve
    "Terminal issue":   (0.30, 20),
    "Funding / deposit": (0.25, 16),
    "Chargeback":       (0.15, 30),
    "Account change":   (0.20, 10),
    "Onboarding help":  (0.10, 12),
}

# A terminal software update in March-April 2026 causes a spike of
# "Terminal issue" tickets for countertop terminals, and the support
# backlog slows every ticket down.
INCIDENT_MONTHS = {pd.Period("2026-03", "M"), pd.Period("2026-04", "M")}


def pick(options: dict, size=None, idx=0):
    keys = list(options)
    probs = np.array([v[idx] if isinstance(v, tuple) else v for v in options.values()], dtype=float)
    return rng.choice(keys, size=size, p=probs / probs.sum())


# ----------------------------------------------------------------------------
# 1. Merchant applications
# ----------------------------------------------------------------------------
n_existing, n_new = 650, 1_450
app_dates = np.concatenate([
    pd.to_datetime("2024-07-01") + pd.to_timedelta(rng.integers(0, 184, n_existing), unit="D"),
    # new applications grow slowly over the period
    PERIOD_START + pd.to_timedelta(
        (np.sqrt(rng.random(n_new)) * (PERIOD_END - PERIOD_START).days).astype(int), unit="D"),
])
app_dates = pd.to_datetime(app_dates)
n = len(app_dates)

m = pd.DataFrame({
    "merchant_id": [f"M{100000 + i}" for i in range(n)],
    "application_date": app_dates,
    "sales_channel": pick(CHANNELS, n),
    "industry": pick(INDUSTRIES, n),
    "province": pick(PROVINCES, n),
})

def product_for(industry):
    if industry == "E-commerce":
        return "Online Gateway"
    if industry in ("Restaurants", "Hospitality"):
        return rng.choice(["Countertop Terminal", "Mobile POS"], p=[0.55, 0.45])
    if industry == "Professional Services":
        return rng.choice(["Countertop Terminal", "Mobile POS", "Online Gateway"], p=[0.35, 0.40, 0.25])
    return rng.choice(["Countertop Terminal", "Mobile POS"], p=[0.75, 0.25])

m["product"] = m["industry"].map(product_for)
m["pricing_plan"] = [
    rng.choice(["Flat Rate", "Interchange Plus"], p=[0.85, 0.15] if ch == "Online Self-Signup" else [0.45, 0.55])
    for ch in m["sales_channel"]
]

approved, decision, activation = [], [], []
for ch, app in zip(m["sales_channel"], m["application_date"]):
    share, appr, (dmin, dmax), never, act_days, _ = CHANNELS[ch]
    d_date = app + pd.Timedelta(days=int(rng.integers(dmin, dmax + 1)))
    ok = rng.random() < appr
    approved.append(ok)
    decision.append(d_date)
    if ok and rng.random() > never:
        days = max(1, int(round(rng.lognormal(np.log(act_days), 0.7))))
        activation.append(d_date + pd.Timedelta(days=days))
    else:
        activation.append(pd.NaT)

m["application_status"] = np.where(approved, "Approved", "Declined")
m["decision_date"] = pd.to_datetime(decision)
m["first_transaction_date"] = pd.to_datetime(activation)
m.loc[m["first_transaction_date"] > PERIOD_END, "first_transaction_date"] = pd.NaT
m["closed_date"] = pd.NaT

# merchant size: fixed multiplier around the industry median
m["_size"] = [INDUSTRIES[i][1] * rng.lognormal(0, 0.8) for i in m["industry"]]

# ----------------------------------------------------------------------------
# 2. Month-by-month simulation: support tickets, churn, card volume
# ----------------------------------------------------------------------------
tickets, volume_rows = [], []
breach_until = {}  # merchant -> last month affected by a slow ticket
ticket_seq = 500000

for _, r in m[m["first_transaction_date"].notna()].iterrows():
    start = r["first_transaction_date"].to_period("M")
    churn_base = CHANNELS[r["sales_channel"]][5]
    days_to_activate = (r["first_transaction_date"] - r["decision_date"]).days
    if days_to_activate > 30:
        churn_base *= 2.6
    elif days_to_activate > 14:
        churn_base *= 2.0
    online = r["product"] == "Online Gateway"
    mix = CARD_MIX_ONLINE if online else CARD_MIX
    avg_ticket = INDUSTRIES[r["industry"]][2]
    for month in MONTHS:
        if month < start:
            continue
        # months since the merchant's first transaction (1 = first month)
        tenure = (month.year - start.year) * 12 + month.month - start.month + 1
        month_start, month_end = month.start_time, month.end_time.normalize()

        # --- support tickets this month
        rate = 0.12
        if month in INCIDENT_MONTHS and r["product"] == "Countertop Terminal":
            rate += 0.45
        for _ in range(rng.poisson(rate)):
            if month in INCIDENT_MONTHS and r["product"] == "Countertop Terminal" and rng.random() < 0.75:
                cat = "Terminal issue"
            elif tenure <= 2 and rng.random() < 0.4:
                cat = "Onboarding help"
            else:
                cat = pick(TICKET_CATEGORIES)
            opened = month_start + pd.Timedelta(minutes=int(rng.integers(0, 60 * 24 * month.days_in_month)))
            hours = rng.lognormal(np.log(TICKET_CATEGORIES[cat][1]), 0.8)
            if month in INCIDENT_MONTHS:
                hours *= 2.6
            resolved = opened + pd.Timedelta(hours=float(hours))
            if resolved > PERIOD_END + pd.Timedelta(days=1):
                resolved = pd.NaT
            csat = None
            if pd.notna(resolved) and rng.random() < 0.42:
                mean = 4.5 if hours <= 24 else 3.9 if hours <= 48 else 2.8
                csat = int(np.clip(round(rng.normal(mean, 0.7)), 1, 5))
            if hours > 48:
                breach_until[r["merchant_id"]] = month + 3
            ticket_seq += 1
            tickets.append({
                "ticket_id": f"T{ticket_seq}",
                "merchant_id": r["merchant_id"],
                "opened_at": opened,
                "resolved_at": resolved,
                "category": cat,
                "contact_channel": rng.choice(["Phone", "Chat", "Email"], p=[0.5, 0.3, 0.2]),
                "csat_score": csat,
            })

        # --- card volume this month
        partial = 1.0
        if tenure == 1:
            partial = (month_end - r["first_transaction_date"]).days / month.days_in_month
        ramp = {1: 0.6, 2: 0.8, 3: 0.92}.get(tenure, 1.0)
        season = SEASONALITY[month.month]
        if r["industry"] == "Hospitality" and month.month in (7, 8):
            season *= 1.25
        total = r["_size"] * partial * ramp * season * rng.normal(1, 0.10)

        for card, share in mix.items():
            vol = max(total * share * rng.normal(1, 0.08), 0)
            approved_txn = int(round(vol / (avg_ticket * rng.normal(1, 0.05))))
            if approved_txn == 0:
                continue
            decline = (0.025 if card == "Interac Debit" else 0.04) * (2.0 if online else 1.0)
            declined_txn = rng.binomial(approved_txn, decline / (1 - decline))
            cb_rate = 0.0 if card == "Interac Debit" else (0.004 if online else 0.0005)
            volume_rows.append({
                "merchant_id": r["merchant_id"],
                "month": month.strftime("%Y-%m"),
                "card_type": card,
                "attempted_txns": approved_txn + declined_txn,
                "approved_txns": approved_txn,
                "approved_volume": round(vol, 2),
                "refund_volume": round(vol * rng.uniform(0.005, 0.025), 2),
                "chargeback_count": int(rng.poisson(approved_txn * cb_rate)),
            })

        # --- did the merchant close its account at the end of this month?
        hazard = churn_base * (1.8 if breach_until.get(r["merchant_id"], month - 1) >= month else 1.0)
        if rng.random() < hazard:
            m.loc[m["merchant_id"] == r["merchant_id"], "closed_date"] = month_end
            break

vol = pd.DataFrame(volume_rows)
tix = pd.DataFrame(tickets)
m = m.drop(columns="_size")

# ----------------------------------------------------------------------------
# 3. Add realistic data-quality problems (caught by sql/01_data_quality.sql)
# ----------------------------------------------------------------------------
# a) 12 merchants loaded twice
m = pd.concat([m, m.sample(12, random_state=SEED)], ignore_index=True)
# b) 25 merchants with no province
m.loc[m.sample(25, random_state=SEED + 1).index, "province"] = None
# c) inconsistent industry labels from an old CRM
idx = m[m["industry"] == "Restaurants"].sample(15, random_state=SEED + 2).index
m.loc[idx, "industry"] = "Restaurant"
idx = m[m["industry"] == "E-commerce"].sample(10, random_state=SEED + 3).index
m.loc[idx, "industry"] = "e-commerce "
# d) 40 monthly rows loaded twice
vol = pd.concat([vol, vol.sample(40, random_state=SEED)], ignore_index=True)
# e) 8 tickets resolved before they were opened (system clock error)
bad = tix[tix["resolved_at"].notna()].sample(8, random_state=SEED).index
tix.loc[bad, "resolved_at"] = tix.loc[bad, "opened_at"] - pd.Timedelta(hours=3)

# ----------------------------------------------------------------------------
# 4. Save
# ----------------------------------------------------------------------------
for col in ["application_date", "decision_date", "first_transaction_date", "closed_date"]:
    m[col] = pd.to_datetime(m[col]).dt.strftime("%Y-%m-%d")
for col in ["opened_at", "resolved_at"]:
    tix[col] = pd.to_datetime(tix[col]).dt.strftime("%Y-%m-%d %H:%M")
tix["csat_score"] = tix["csat_score"].astype("Int64")

m.sample(frac=1, random_state=SEED).to_csv(OUT / "merchants.csv", index=False)
vol.sample(frac=1, random_state=SEED).to_csv(OUT / "monthly_volume.csv", index=False)
tix.sort_values("opened_at").to_csv(OUT / "support_tickets.csv", index=False)

print(f"merchants:       {len(m):>7,} rows")
print(f"monthly_volume:  {len(vol):>7,} rows")
print(f"support_tickets: {len(tix):>7,} rows")
