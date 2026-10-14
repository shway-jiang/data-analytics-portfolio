"""Draws the two dashboard pages as PNG images from the scorecard query results."""

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
HIGHLIGHT = "#f3e3da"  # incident band

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
    fig.text(0.965, 0.955, "Simulated data · fictional merchant acquirer", fontsize=9,
             color=MUTED, ha="right")


def page1(r: dict, path: Path):
    sc = r["monthly_scorecard"]
    ind = r["industry_performance"].sort_values("net_revenue")
    last, prev = sc.iloc[-1], sc.iloc[-2]
    yago = sc[sc["month"] == "2025-06"].iloc[0]

    fig = plt.figure(figsize=(16, 9))
    _header(fig, "Merchant Payments Scorecard: Business Performance",
            f"January 2025 – June 2026 · latest month {pd.Period(last['month'], 'M').strftime('%B %Y')}")
    gs = fig.add_gridspec(3, 4, height_ratios=[0.55, 2, 2], top=0.88, bottom=0.07,
                          left=0.045, right=0.97, hspace=0.55, wspace=0.45)

    def pct(a, b):
        return f"{(a / b - 1) * 100:+.1f}%"

    _tile(fig.add_subplot(gs[0, 0]), "Approved card volume", f"${last['approved_volume'] / 1e6:.1f}M",
          f"{pct(last['approved_volume'], prev['approved_volume'])} vs May · {pct(last['approved_volume'], yago['approved_volume'])} vs Jun 2025")
    _tile(fig.add_subplot(gs[0, 1]), "Net revenue", f"${last['net_revenue'] / 1e3:.0f}K",
          f"{pct(last['net_revenue'], prev['net_revenue'])} vs May · {pct(last['net_revenue'], yago['net_revenue'])} vs Jun 2025")
    _tile(fig.add_subplot(gs[0, 2]), "Active merchants", f"{int(last['active_merchants']):,}",
          f"+{int(last['new_merchants'])} new, −{int(last['closed_merchants'])} closed this month")
    _tile(fig.add_subplot(gs[0, 3]), "Approval rate", f"{last['approval_rate_pct']:.1f}%",
          f"Chargeback rate {last['chargeback_rate_pct']:.2f}% of credit transactions")

    x = range(len(sc))
    labels = _month_labels(sc["month"].tolist())

    ax = fig.add_subplot(gs[1, :2])
    ax.bar(x, sc["approved_volume"] / 1e6, color=BLUE, width=0.72)
    ax.set_title("Approved card volume by month ($M)")
    ax.set_xticks(list(x), labels, fontsize=8.5)
    ax.grid(axis="x", visible=False)
    ax.annotate("Holiday peak", (11, sc["approved_volume"].iloc[11] / 1e6), xytext=(6.2, 52),
                fontsize=9, color=TEXT_2, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))

    ax = fig.add_subplot(gs[1, 2:])
    ax.plot(x, sc["net_revenue"] / 1e3, color=BLUE, lw=2, marker="o", ms=4)
    ax.set_title("Net revenue by month ($K)")
    ax.set_xticks(list(x), labels, fontsize=8.5)
    ax.set_ylim(0, None)
    ax.annotate(f"${last['net_revenue'] / 1e3:.0f}K", (len(sc) - 1, last["net_revenue"] / 1e3),
                xytext=(-8, 8), textcoords="offset points", ha="right", fontsize=9, color=TEXT)

    ax = fig.add_subplot(gs[2, :2])
    w = 0.38
    ax.bar([i - w / 2 for i in x], sc["new_merchants"], width=w, color=BLUE, label="New (first transaction)")
    ax.bar([i + w / 2 for i in x], sc["closed_merchants"], width=w, color=ORANGE, label="Closed")
    ax.set_title("Merchants gained and lost each month")
    ax.set_xticks(list(x), labels, fontsize=8.5)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, loc="upper left", fontsize=9)

    ax = fig.add_subplot(gs[2, 2:])
    pos = ax.get_position()   # leave room on the left for long industry names
    ax.set_position([pos.x0 + 0.075, pos.y0, pos.width - 0.075, pos.height])
    ax.barh(ind["industry"], ind["net_revenue"] / 1e3, color=BLUE, height=0.6)
    ax.set_title("Net revenue by industry, Jan–Jun 2026 ($K)", x=-0.2)
    ax.grid(axis="y", visible=False)
    for i, (v, s) in enumerate(zip(ind["net_revenue"], ind["revenue_share_pct"])):
        ax.text(v / 1e3 + 4, i, f"${v / 1e3:.0f}K · {s:.0f}%", va="center", fontsize=9, color=TEXT_2)
    ax.set_xlim(0, ind["net_revenue"].max() / 1e3 * 1.25)

    fig.savefig(path, dpi=110)
    plt.close(fig)


def page2(r: dict, path: Path):
    ch = r["onboarding_by_channel"].sort_values("activated_within_30d_pct")
    sp = r["activation_speed_vs_retention"]
    sc = r["monthly_scorecard"]
    st = r["slow_ticket_vs_churn"]

    fig = plt.figure(figsize=(16, 9))
    _header(fig, "Merchant Payments Scorecard: Onboarding & Service",
            "Where new merchants get stuck, and how support speed relates to account closures")
    gs = fig.add_gridspec(2, 2, top=0.86, bottom=0.08, left=0.1, right=0.97, hspace=0.5, wspace=0.25)

    ax = fig.add_subplot(gs[0, 0])
    ax.barh(ch["sales_channel"], ch["activated_within_30d_pct"], color=BLUE, height=0.55)
    ax.set_title("Approved merchants processing within 30 days, by sales channel")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_xlim(0, 110)
    ax.grid(axis="y", visible=False)
    for i, v in enumerate(ch["activated_within_30d_pct"]):
        ax.text(v + 1.2, i, f"{v:.0f}%", va="center", fontsize=9.5, color=TEXT)

    ax = fig.add_subplot(gs[0, 1])
    labels = [s.split(") ")[1] for s in sp["time_to_first_txn"]]
    ax.bar(labels, sp["retained_6m_pct"], color=BLUE, width=0.55)
    ax.set_title("Merchants still open after 6 months, by days from approval to first sale")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 105)
    ax.grid(axis="x", visible=False)
    for i, (v, n) in enumerate(zip(sp["retained_6m_pct"], sp["merchants"])):
        ax.text(i, v + 2, f"{v:.0f}%", ha="center", fontsize=9.5, color=TEXT)
        ax.text(i, 4, f"n={n}", ha="center", fontsize=8.5, color=SURFACE)

    ax = fig.add_subplot(gs[1, 0])
    x = list(range(len(sc)))
    i0 = sc.index[sc["month"] == "2026-03"][0]
    ax.axvspan(i0 - 0.5, i0 + 1.5, color=HIGHLIGHT, lw=0)
    ax.text(i0 + 0.5, 12, "Terminal\nupdate issue", ha="center", fontsize=8.5, color=TEXT_2)
    ax.plot(x, sc["pct_within_48h_sla"], color=BLUE, lw=2, marker="o", ms=4)
    ax.set_title("Support tickets resolved within the 48-hour target")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.set_ylim(0, 105)
    ax.set_xticks(x, _month_labels(sc["month"].tolist()), fontsize=8.5)

    ax = fig.add_subplot(gs[1, 1])
    st = st.sort_values("ticket_experience", ascending=False)
    ax.bar(st["ticket_experience"], st["closed_within_3_months_pct"], color=[BLUE, ORANGE], width=0.45)
    ax.set_title("Accounts closed within 3 months, by support experience that month")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.set_ylim(0, st["closed_within_3_months_pct"].max() * 1.3)
    ax.grid(axis="x", visible=False)
    for i, v in enumerate(st["closed_within_3_months_pct"]):
        ax.text(i, v + 0.3, f"{v:.1f}%", ha="center", fontsize=10, color=TEXT)

    fig.savefig(path, dpi=110)
    plt.close(fig)


def build_dashboard(results: dict, out_dir: Path):
    out_dir.mkdir(exist_ok=True)
    page1(results, out_dir / "page1_business_performance.png")
    page2(results, out_dir / "page2_onboarding_and_service.png")
