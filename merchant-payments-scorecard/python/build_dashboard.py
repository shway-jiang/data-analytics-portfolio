"""Draws the two dashboard pages (PNG) from the scorecard query results."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
MUTED = "#8a8984"
GRID = "#e6e5e0"
BLUE = "#2a78d6"      # series 1
ORANGE = "#eb6834"    # series 2
AQUA = "#1baf7a"      # series 3
HIGHLIGHT = "#f3e3da"  # highlighted period

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": GRID,
    "axes.labelcolor": TEXT_2,
    "axes.titlecolor": TEXT,
    "axes.titlesize": 11.5,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "axes.titlepad": 10,
    "xtick.color": TEXT_2,
    "ytick.color": TEXT_2,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.spines.left": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
})


def _month_labels(months):
    return [pd.Period(m, "M").strftime("%b\n%Y") if m.endswith("-01") or i == 0
            else pd.Period(m, "M").strftime("%b") for i, m in enumerate(months)]


def _tile(ax, label, value, change):
    ax.axis("off")
    ax.set_facecolor(SURFACE)
    ax.text(0.0, 0.78, label, fontsize=10, color=TEXT_2, transform=ax.transAxes)
    ax.text(0.0, 0.30, value, fontsize=21, fontweight="bold", color=TEXT, transform=ax.transAxes)
    ax.text(0.0, 0.02, change, fontsize=9.5, color=TEXT_2, transform=ax.transAxes)


def _header(fig, title, subtitle):
    fig.text(0.035, 0.955, title, fontsize=17, fontweight="bold", color=TEXT)
    fig.text(0.035, 0.925, subtitle, fontsize=10, color=TEXT_2)
    fig.text(0.965, 0.955, "Source: Olist public marketplace data (Brazil) · amounts in R$", fontsize=9,
             color=MUTED, ha="right")


def _pct(a, b):
    return f"{(a / b - 1) * 100:+.1f}%"


def page1(r: dict, path: Path):
    sc = r["monthly_scorecard"]
    pm = r["payment_methods"].sort_values("value_share_pct")
    inst = r["card_installments"]
    last, prev = sc.iloc[-1], sc.iloc[-2]
    yago = sc[sc["month"] == "2017-08"].iloc[0]

    fig = plt.figure(figsize=(16, 9))
    _header(fig, "Marketplace Payments Scorecard: Sales & Payments",
            f"January 2017 – August 2018 · latest month {pd.Period(last['month'], 'M').strftime('%B %Y')}")
    gs = fig.add_gridspec(3, 4, height_ratios=[0.55, 2, 2], top=0.88, bottom=0.07,
                          left=0.045, right=0.97, hspace=0.6, wspace=0.45)

    _tile(fig.add_subplot(gs[0, 0]), "Gross merchandise value (GMV)", f"R${last['gmv'] / 1e3:,.0f}K",
          f"{_pct(last['gmv'], prev['gmv'])} vs Jul · {_pct(last['gmv'], yago['gmv'])} vs Aug 2017")
    _tile(fig.add_subplot(gs[0, 1]), "Orders", f"{int(last['orders']):,}",
          f"Average order R${last['avg_order_value']:.0f} · {last['canceled_pct']:.1f}% canceled")
    _tile(fig.add_subplot(gs[0, 2]), "Active sellers", f"{int(last['active_sellers']):,}",
          f"{int(last['new_sellers'])} new · {last['seller_retention_pct']:.0f}% of July's sellers sold again")
    _tile(fig.add_subplot(gs[0, 3]), "Paid by credit card", f"{last['credit_card_share_pct']:.0f}%",
          f"of order value · avg {last['avg_card_installments']:.1f} installments")

    x = list(range(len(sc)))
    labels = _month_labels(sc["month"].tolist())

    ax = fig.add_subplot(gs[1, :2])
    ax.bar(x, sc["gmv"] / 1e3, color=BLUE, width=0.72)
    ax.set_title("GMV by month (R$K)")
    ax.set_xticks(x, labels, fontsize=8.5)
    ax.grid(axis="x", visible=False)
    i_bf = sc.index[sc["month"] == "2017-11"][0]
    ax.annotate("Black Friday", (i_bf, sc["gmv"].iloc[i_bf] / 1e3), xytext=(i_bf - 6.5, 1000),
                fontsize=9, color=TEXT_2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))

    ax = fig.add_subplot(gs[1, 2:])
    ax.plot(x, sc["gmv_per_active_seller"], color=BLUE, lw=2, marker="o", ms=4)
    ax.set_title("GMV per active seller (R$): sellers keep growing, sales per seller don't")
    ax.set_xticks(x, labels, fontsize=8.5)
    ax.set_ylim(0, sc["gmv_per_active_seller"].max() * 1.2)
    for i in (sc.index[sc["month"] == "2018-01"][0], len(sc) - 1):
        ax.annotate(f"R${sc['gmv_per_active_seller'].iloc[i]:.0f}\n{int(sc['active_sellers'].iloc[i]):,} sellers",
                    (i, sc["gmv_per_active_seller"].iloc[i]), xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=8.5, color=TEXT)

    ax = fig.add_subplot(gs[2, :2])
    pos = ax.get_position()   # leave room for the method names
    ax.set_position([pos.x0 + 0.04, pos.y0, pos.width - 0.04, pos.height])
    names = [n.replace("_", " ").capitalize() for n in pm["payment_method"]]
    ax.barh(names, pm["value_share_pct"], color=BLUE, height=0.55)
    ax.set_title("Share of order value by payment method", x=-0.09)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlim(0, 110)
    ax.grid(axis="y", visible=False)
    for i, (v, h) in enumerate(zip(pm["value_share_pct"], pm["median_hours_to_approve"])):
        ax.text(v + 1.2, i, f"{v:.0f}% · approved in {h:.1f}h (median)", va="center", fontsize=9, color=TEXT_2)

    ax = fig.add_subplot(gs[2, 2:])
    plans = [s.split(") ")[1] for s in inst["installment_plan"]]
    xi = list(range(len(plans)))
    w = 0.38
    ax.bar([i - w / 2 for i in xi], inst["order_share_pct"], width=w, color=BLUE, label="Share of card orders")
    ax.bar([i + w / 2 for i in xi], inst["value_share_pct"], width=w, color=ORANGE, label="Share of card value")
    ax.set_title("Credit card orders by installment plan")
    ax.set_xticks(xi, plans, fontsize=9)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylim(0, 42)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9, loc="upper right", ncol=2)

    fig.savefig(path, dpi=110)
    plt.close(fig)


def page2(r: dict, path: Path):
    fn = r["seller_funnel_by_channel"]
    fn = fn[fn["leads"] >= 280].sort_values("leads", ascending=False)
    conc = r["seller_concentration"]
    sc = r["monthly_scorecard"]
    dr = r["delivery_vs_review"]

    fig = plt.figure(figsize=(16, 9))
    _header(fig, "Marketplace Payments Scorecard: Sellers & Service",
            "Seller onboarding by marketing channel, sales concentration, and how delivery affects reviews")
    gs = fig.add_gridspec(2, 2, top=0.86, bottom=0.08, left=0.05, right=0.97, hspace=0.5, wspace=0.2)

    ax = fig.add_subplot(gs[0, 0])
    xi = list(range(len(fn)))
    w = 0.38
    ax.bar([i - w / 2 for i in xi], fn["lead_to_signed_pct"], width=w, color=BLUE, label="Leads that signed")
    ax.bar([i + w / 2 for i in xi], fn["signed_with_first_sale_pct"], width=w, color=ORANGE,
           label="Signed sellers who made a sale")
    ax.set_title("Seller onboarding by lead channel (channels with 280+ leads)")
    ax.set_xticks(xi, [c.replace("_", " ").capitalize() for c in fn["lead_channel"]], fontsize=9)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 80)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, fontsize=9, loc="upper right", ncol=2)
    for i, (a, b) in enumerate(zip(fn["lead_to_signed_pct"], fn["signed_with_first_sale_pct"])):
        ax.text(i - w / 2, a + 1.2, f"{a:.0f}%", ha="center", fontsize=8.5, color=TEXT)
        ax.text(i + w / 2, b + 1.2, f"{b:.0f}%", ha="center", fontsize=8.5, color=TEXT)

    ax = fig.add_subplot(gs[0, 1])
    ax.bar([f"Top {d * 10}%" if d == 1 else f"{d * 10 - 9}-{d * 10}%" for d in conc["seller_decile"]],
           conc["gmv_share_pct"], color=BLUE, width=0.6)
    ax.set_title("Share of GMV by seller group (sellers ranked by sales)")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 80)
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(axis="x", visible=False)
    for i, v in enumerate(conc["gmv_share_pct"][:3]):
        ax.text(i, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9.5, color=TEXT)

    ax = fig.add_subplot(gs[1, 0])
    x = list(range(len(sc)))
    for m, label in (("2017-11", "Black\nFriday"), ("2018-02", "Feb–Mar\n2018")):
        i0 = sc.index[sc["month"] == m][0]
        span = 1 if m == "2017-11" else 2
        ax.axvspan(i0 - 0.5, i0 + span - 0.5, color=HIGHLIGHT, lw=0)
        ax.text(i0 + (span - 1) / 2, 62, label, ha="center", fontsize=8.5, color=TEXT_2)
    ax.plot(x, sc["delivered_on_time_pct"], color=BLUE, lw=2, marker="o", ms=4)
    ax.set_title("Orders delivered by the promised date")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(50, 102)
    ax.set_xticks(x, _month_labels(sc["month"].tolist()), fontsize=8.5)

    ax = fig.add_subplot(gs[1, 1])
    labels = [s.split(") ")[1] for s in dr["delivery"]]
    ax.bar(labels, dr["avg_review_score"], color=BLUE, width=0.55)
    ax.set_title("Average customer review (1–5 stars) by delivery timing")
    ax.set_ylim(0, 5.2)
    ax.grid(axis="x", visible=False)
    for i, (v, s) in enumerate(zip(dr["avg_review_score"], dr["share_pct"])):
        ax.text(i, v + 0.08, f"{v:.1f}", ha="center", fontsize=10, color=TEXT)
        ax.text(i, 0.15, f"{s:.0f}% of orders", ha="center", fontsize=8.5, color=SURFACE)

    fig.savefig(path, dpi=110)
    plt.close(fig)


def build_dashboard(results: dict, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    page1(results, out_dir / "page1_sales_and_payments.png")
    page2(results, out_dir / "page2_sellers_and_service.png")
