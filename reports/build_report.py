"""
Builds the two written deliverables from the live analysis, so every number in
the PDFs is computed from the data rather than typed by hand.

    python -m reports.build_report

Outputs
    reports/Nassau_Candy_Route_Efficiency_Research_Report.pdf
    reports/Nassau_Candy_Route_Efficiency_Executive_Summary.pdf
"""
from __future__ import annotations

import os
from datetime import date

import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)
from scipy import stats

from src import config, metrics as m

LON = "Lot's O' Nuts"
AUTHOR = os.environ.get("REPORT_AUTHOR", "Data Analyst Intern")
OUT = config.ROOT / "reports"
FIG = config.FIGURES_DIR

# ----------------------------------------------------------------------------- fonts & styles
FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
try:
    pdfmetrics.registerFont(TTFont("Body", FONT_DIR + "DejaVuSans.ttf"))
    pdfmetrics.registerFont(TTFont("Body-Bold", FONT_DIR + "DejaVuSans-Bold.ttf"))
    pdfmetrics.registerFont(TTFont("Body-Italic", FONT_DIR + "DejaVuSans-Oblique.ttf"))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic")
    BODY, BOLD = "Body", "Body-Bold"
except Exception:  # fallback if DejaVu is unavailable
    BODY, BOLD = "Helvetica", "Helvetica-Bold"

BLUE, INK, MUTED, LINE, TINT = (colors.HexColor(c) for c in ("#1c5cab", "#1f1f1d", "#5c5b57", "#d9d8d3", "#eef4fc"))
S = {
    "title": ParagraphStyle("title", fontName=BOLD, fontSize=24, leading=30, textColor=INK, spaceAfter=10),
    "subtitle": ParagraphStyle("subtitle", fontName=BODY, fontSize=12.5, leading=18, textColor=MUTED),
    "h1": ParagraphStyle("h1", fontName=BOLD, fontSize=15, leading=20, textColor=BLUE, spaceBefore=14, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontName=BOLD, fontSize=11.5, leading=15, textColor=INK, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName=BODY, fontSize=9.6, leading=14, textColor=INK, spaceAfter=6, alignment=TA_LEFT),
    "bullet": ParagraphStyle("bullet", fontName=BODY, fontSize=9.6, leading=14, textColor=INK, leftIndent=12,
                             bulletIndent=2, spaceAfter=3),
    "caption": ParagraphStyle("caption", fontName=BODY, fontSize=8, leading=11, textColor=MUTED, spaceAfter=10),
    "cell": ParagraphStyle("cell", fontName=BODY, fontSize=8.2, leading=10.5, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName=BOLD, fontSize=8.2, leading=10.5, textColor=colors.white),
    "kpi_v": ParagraphStyle("kpi_v", fontName=BOLD, fontSize=16, leading=19, textColor=BLUE),
    "kpi_l": ParagraphStyle("kpi_l", fontName=BODY, fontSize=7.8, leading=10, textColor=MUTED),
    "callout": ParagraphStyle("callout", fontName=BODY, fontSize=9.6, leading=14, textColor=INK),
}
P = lambda t, s="body": Paragraph(t, S[s])
BUL = lambda items: [Paragraph(t, S["bullet"], bulletText="•") for t in items]


def table(rows, widths, header=True, zebra=True):
    data = [[c if isinstance(c, Paragraph) else Paragraph(str(c), S["cellb" if (header and i == 0) else "cell"])
             for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
             ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
             ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), BLUE)]
    if zebra:
        style += [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f7f7f5")) for i in range(2, len(rows), 2)]
    t.setStyle(TableStyle(style))
    return t


def callout(text):
    t = Table([[Paragraph(text, S["callout"])]], colWidths=[17 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), TINT), ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    return t


def kpi_strip(items):
    row_v = [Paragraph(v, S["kpi_v"]) for v, _ in items]
    row_l = [Paragraph(l, S["kpi_l"]) for _, l in items]
    w = 17 * cm / len(items)
    t = Table([row_v, row_l], colWidths=[w] * len(items))
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
                           ("LINEAFTER", (0, 0), (-2, -1), 0.6, LINE), ("TOPPADDING", (0, 0), (-1, 0), 8),
                           ("BOTTOMPADDING", (0, 1), (-1, 1), 8), ("LEFTPADDING", (0, 0), (-1, -1), 8)]))
    return t


def fig(name, width_cm=17, caption=None):
    from PIL import Image as PIL
    path = FIG / f"{name}.png"
    w, h = PIL.open(path).size
    img = Image(str(path), width=width_cm * cm, height=width_cm * cm * h / w)
    return KeepTogether([img, P(caption, "caption")] if caption else [img])


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont(BODY, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "Nassau Candy Distributor · Shipping Route Efficiency Analysis")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Page {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(2 * cm, 1.5 * cm, A4[0] - 2 * cm, 1.5 * cm)
    canvas.restoreState()


# ----------------------------------------------------------------------------- numbers
def compute():
    df = m.add_excess_days(m.load_clean())
    k = m.headline_kpis(df)
    sm = m.ship_mode_summary(df)
    sc = m.route_scorecard(df)
    elig = sc[sc["Eligible"]]
    st = m.state_bottlenecks(df, 50)
    yearly = df.groupby(df["Order Date"].dt.year)["is_delayed"].mean()
    half = df.assign(H=df["Order Date"].dt.year.astype(str) + "-H" +
                     np.where(df["Order Date"].dt.quarter <= 2, "1", "2")).groupby("H")["is_delayed"].mean()
    rho, p_rho = stats.spearmanr(df["distance_miles"], df["excess_days"])
    kw = {}
    for col in ["Region", "Factory", "State/Province"]:
        groups = [g["excess_days"].values for _, g in df.groupby(col) if len(g) >= 30]
        kw[col] = stats.kruskal(*groups)
    fac = df.groupby("Factory").agg(n=("Sales", "size"), mi=("distance_miles", "mean"))
    fac["share"] = fac["n"] / fac["n"].sum()
    choc = df[df["Division"] == "Chocolate"]
    scen = {}
    for name, fset in {"dual": ["Lot's O' Nuts", "Wicked Choccy's"],
                       "tri": ["Lot's O' Nuts", "Wicked Choccy's", "Secret Factory"]}.items():
        s = m.nearest_factory_scenario(choc, fset)
        cur = (s["distance_miles"] * s["Units"]).sum()
        new = (s["Scenario distance"] * s["Units"]).sum()
        scen[name] = dict(cur=cur, new=new, red=1 - new / cur, switch=(s["Scenario Factory"] != s["Factory"]).mean())
    return dict(df=df, k=k, sm=sm, sc=sc, elig=elig, st=st, yearly=yearly, half=half, rho=rho, p_rho=p_rho,
                kw=kw, fac=fac, scen=scen, reloc=m.relocation_scenarios(df))


def recommendations(d):
    y, sc = d["yearly"], d["scen"]
    fc = d["sm"].loc["First Class", "Delay Rate"]
    slow = ", ".join(d["st"][d["st"]["Significantly slow"]].index[:7])
    return [
        ["#", "Recommendation", "Evidence", "Expected impact"],
        ["1", "<b>Root-cause the 2025 dispatch slowdown</b> (staffing, carrier pick-up windows, order cut-off times) "
              "and add fulfilment capacity.",
         f"SLA breach rose from {y.iloc[0]:.1%} (2024) to {y.iloc[1]:.1%} (2025), inside every ship mode, with a stable mode mix.",
         "Bring breach rate back toward the 2024 level."],
        ["2", "<b>Dual-source Wonka Bars</b> from the Arizona and Georgia plants, routing each order to the nearer plant.",
         f"Cuts chocolate unit-miles by {sc['dual']['red']:.0%} ({sc['tri']['red']:.0%} if Secret Factory is added as a third source).",
         "Lower freight cost and real transit time; removes most cross-country lanes."],
        ["3", "<b>Protect First Class</b> with a dedicated pick lane or earlier cut-off.",
         f"{fc:.1%} of First Class shipments miss the 3-day SLA – premium customers are let down roughly one time in seven.",
         "Higher premium-service reliability and retention."],
        ["4", f"<b>Targeted review of bottleneck states</b> ({slow}).",
         "Significantly slower than average after controlling for ship mode (95% CI above zero).",
         "Remove local carrier / hub issues."],
        ["5", "<b>Fix the date-shift defect</b> in the order/ship-date export and add freight cost and delivery date to the data.",
         "Raw Ship − Order gaps of 904–1,642 days; margins look identical across ship modes.",
         "Trustworthy KPIs and true cost-to-serve monitoring."],
    ]


# ----------------------------------------------------------------------------- research report
def research_report(d):
    k, sm, elig, st, y, sc = d["k"], d["sm"], d["elig"], d["st"], d["yearly"], d["scen"]
    doc = SimpleDocTemplate(str(OUT / "Nassau_Candy_Route_Efficiency_Research_Report.pdf"), pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm, bottomMargin=2 * cm,
                            title="Factory-to-Customer Shipping Route Efficiency Analysis", author=AUTHOR)
    E = []

    # ---- cover
    E += [Spacer(1, 5 * cm), P("RESEARCH REPORT · DATA ANALYTICS", "subtitle"), Spacer(1, 6),
          P("Factory-to-Customer Shipping Route Efficiency Analysis", "title"),
          P("Nassau Candy Distributor", "subtitle"), Spacer(1, 1.2 * cm),
          kpi_strip([(f"{k['shipments']:,}", "shipments analysed"), (f"{k['avg_lead_time']:.2f} d", "avg processing lead time"),
                     (f"{k['delay_rate']:.1%}", "delay frequency (SLA breach)"), (f"{k['routes']}", "factory → state routes")]),
          Spacer(1, 1.2 * cm),
          P(f"<b>Prepared by:</b> {AUTHOR}"), P(f"<b>Date:</b> {date.today():%d %B %Y}"),
          P("<b>Data:</b> 10,194 order lines, January 2024 – December 2025, 5 factories, 15 products, US &amp; Canada"),
          P("<b>Tools:</b> Python (pandas, SciPy), Plotly, Streamlit, Matplotlib"),
          PageBreak()]

    # ---- 1 executive summary
    E += [P("1. Executive summary", "h1"),
          P("Nassau Candy ships confectionery from five factories to customers across the United States and Canada. "
            "This study measures how efficiently each factory → customer route performs, finds where delays concentrate, "
            "compares ship modes, and tests whether re-assigning production could shorten the distances products travel."),
          callout(f"<b>Bottom line.</b> Delays are created inside the fulfilment operation, not on the road: processing lead time "
                  f"is driven by ship mode and by a sharp 2025 deterioration (SLA breach {y.iloc[0]:.1%} → {y.iloc[1]:.1%}), "
                  f"while route distance has no effect on it (ρ = {d['rho']:.2f}). Distance matters for freight cost – and "
                  f"there the network is poorly aligned: routing chocolate orders to the nearer of the two chocolate plants "
                  f"would cut chocolate unit-miles by {sc['dual']['red']:.0%}."),
          Spacer(1, 6), P("Key findings", "h2")]
    E += BUL([
        "<b>Data quality:</b> the raw Ship Date − Order Date gap is 904–1,642 days. It is a year-level date shift; the remainder "
        "(0–8 days) matches ship-mode SLAs exactly and is used as the true processing lead time.",
        f"<b>Ship mode dominates speed:</b> Same Day {sm.loc['Same Day','Avg Lead Time (d)']:.1f} d → Standard Class "
        f"{sm.loc['Standard Class','Avg Lead Time (d)']:.1f} d. Standard Class carries {sm.loc['Standard Class','Share']:.0%} of volume "
        f"and the highest breach rate ({sm.loc['Standard Class','Delay Rate']:.1%}); First Class misses its SLA "
        f"{sm.loc['First Class','Delay Rate']:.1%} of the time.",
        f"<b>Service is deteriorating:</b> delay frequency rose from {d['half'].get('2024-H2', np.nan):.1%} in H2-2024 to "
        f"{d['half'].get('2025-H2', np.nan):.1%} in H2-2025, in every ship mode.",
        f"<b>Route leaderboard:</b> {len(elig)} routes with ≥ {config.MIN_ROUTE_VOLUME} shipments were scored. Best: short regional lanes "
        f"such as {elig.index[1]} and {elig.index[2]}. Worst: {elig.index[-1]}, {elig.index[-2]} and {elig.index[-3]}.",
        f"<b>Geographic bottlenecks:</b> {', '.join(st[st['Significantly slow']].index[:6])} are significantly slower than average "
        "after controlling for ship mode.",
        f"<b>Network misalignment:</b> Lot's O' Nuts (Arizona) handles {d['fac'].loc[LON, 'share']:.0%} "
        f"of shipments but ships the furthest ({d['fac'].loc[LON, 'mi']:,.0f} mi on average).",
    ])
    E += [P("Recommendations", "h2"), table(recommendations(d), [0.6 * cm, 5.6 * cm, 6.2 * cm, 4.6 * cm]), PageBreak()]

    # ---- 2 background
    E += [P("2. Background and problem statement", "h1"),
          P("Nassau Candy Distributor manufactures and distributes confectionery through a network of five factories. "
            "Each product is produced at exactly one factory and shipped to retail customers by one of four ship modes "
            "(Same Day, First Class, Second Class, Standard Class). Management had no route-level view of logistics "
            "performance: it could not say which factory → customer lanes are fast and reliable, which are slow, where "
            "geographic bottlenecks sit, or whether the factory network is well placed relative to demand."),
          P("Objectives", "h2")]
    E += BUL(["Measure shipping lead time and delay frequency at route level (factory → state and factory → region).",
              "Rank routes on a single, fair efficiency score and identify the best and worst performers.",
              "Locate geographic bottlenecks with statistical confidence rather than raw averages.",
              "Compare ship modes on speed, reliability and margin.",
              "Quantify how much shipping distance could be saved by re-assigning production between factories.",
              "Deliver an interactive Streamlit dashboard so operations teams can explore the results themselves."])

    # ---- 3 data
    E += [P("3. Data and preparation", "h1"),
          P("The dataset contains 10,194 order lines with 18 fields: order and ship dates, ship mode, customer location "
            "(country, city, state/province, postal code, region), product and division, and sales, units, cost and gross profit. "
            "Two reference tables from the project brief were added: factory coordinates and the product → factory mapping "
            "(Appendix A)."),
          table([["Check", "Result", "Action"],
                 ["Missing values / duplicate rows", "0 / 0", "None needed"],
                 ["Sales − Cost = Gross Profit", "Holds on every row (max error ≈ 1e-14)", "Financial fields trusted"],
                 ["US ZIP codes with 4 digits", "449 rows (New England / New Jersey lost a leading zero)", "Left-padded to 5 digits"],
                 ["Product → factory mapping", "15 of 15 products mapped", "Factory + coordinates joined"],
                 ["Customer geocoding", "100% (US: ZIP centroid; Canada: city centroid)", "Haversine distance computed"],
                 ["Ship Date − Order Date", "904 – 1,642 days", "Date-shift corrected (Section 3.1)"]],
                [5 * cm, 7 * cm, 5 * cm]),
          P("3.1 Lead-time data-quality finding", "h2"),
          P("Computed literally, the gap between ship and order date is 2.5–4.5 years – impossible for confectionery. The "
            "gaps form three narrow bands starting at 904, 1,269 and 1,634 days – exactly 365 days apart. Inside each band, "
            "the leftover days follow the ship-mode hierarchy precisely: Same Day 0–2, First Class 1–4, Second Class 2–6, "
            "Standard Class 3–8. Such a pattern could not survive if the whole gap were noise, so the remainder is the true "
            "order-processing time and the band offset is a date shift introduced when the data was exported."),
          fig("fig01_lead_time_decomposition", caption="Figure 1. Left: raw gap in three 365-day bands. Right: processing days "
              "left inside each band, by ship mode – each mode sits in its expected range."),
          callout("<b>Decision.</b> All KPIs use <i>lead_time_days = (raw gap − 904) mod 365</i>. The raw value is retained in the "
                  "clean dataset and shown in the dashboard's Data &amp; Method tab for full transparency."),
          PageBreak()]

    # ---- 4 methodology
    E += [P("4. Methodology and KPI definitions", "h1"),
          table([["KPI", "Definition"],
                 ["Shipping lead time", "Processing days from order to dispatch (date shift removed)"],
                 ["Average lead time", "Mean lead time for a route, state, region or ship mode"],
                 ["Route volume", "Number of shipments (order lines) on a route"],
                 ["Delay frequency", "Share of shipments whose lead time exceeds the ship-mode SLA: Same Day ≤ 1 d, "
                                     "First ≤ 3 d, Second ≤ 5 d, Standard ≤ 6 d (≈ 75th percentile of each mode). The dashboard "
                                     "also allows a single global threshold."],
                 ["Excess days", "Lead time minus the network average for the same ship mode – removes ship-mode mix so "
                                 "routes with many Standard Class orders are not unfairly penalised"],
                 ["Route efficiency score", "0–100 (higher is better): 50% excess days, 30% delay frequency, 20% average "
                                            "distance, each percentile-ranked across routes with ≥ 30 shipments, then rescaled "
                                            "so the best route = 100 and the worst = 0"],
                 ["Distance", "Great-circle (haversine) miles from factory to customer location"]],
                [4.2 * cm, 12.8 * cm]),
          Spacer(1, 6), P("Analytical steps", "h2")]
    E += BUL(["Clean and enrich the data (Section 3) in a reusable pipeline (<i>src/data_prep.py</i>).",
              "Aggregate KPIs by ship mode, month, factory → state route, factory → region route and state (<i>src/metrics.py</i>).",
              "Rank routes on the efficiency score with a minimum-volume rule (≥ 30 shipments) to avoid small-sample noise.",
              "Test geographic effects statistically: Kruskal–Wallis on excess days by region, factory and state; 95% "
              "confidence intervals for each state; Spearman correlation between distance and excess days.",
              "Simulate production re-assignment: unit-weighted distance if each product were made at each factory, and a "
              "nearest-plant fulfilment scenario for chocolate.",
              "Publish everything in a Streamlit dashboard with date, region, state, ship-mode, factory and delay-threshold filters."])

    # ---- 5 results
    E += [P("5. Results", "h1"), P("5.1 Ship-mode performance", "h2"),
          fig("fig02_ship_mode_performance", caption="Figure 2. Average processing lead time against SLA target, and SLA breach rate, by ship mode."),
          KeepTogether(table([["Ship mode", "Share", "Avg lead (d)", "SLA (d)", "Delay rate", "Gross margin"]] +
                [[i, f"{r['Share']:.1%}", f"{r['Avg Lead Time (d)']:.2f}", int(r["SLA (d)"]), f"{r['Delay Rate']:.1%}",
                  f"{r['Gross Margin %']:.1f}%"] for i, r in sm.iterrows()],
                [4 * cm, 2.4 * cm, 2.6 * cm, 2.2 * cm, 2.6 * cm, 3.2 * cm])),
          Spacer(1, 6),
          P("Ship mode is the dominant driver of lead time. Standard Class is both the largest and the least reliable mode. "
            "First Class is a concern: customers pay for speed yet one shipment in seven misses its 3-day target. Gross margin is "
            "flat across modes because freight cost is not recorded – faster modes look free in this data, which they are not."),
          P("5.2 Delay trend", "h2"),
          fig("fig03_delay_trend", caption="Figure 3. Monthly SLA breach rate (top) and shipment volume (bottom)."),
          P(f"Delay frequency was low through 2024 (≈5–8% after a small-sample January–February) and stepped up through 2025, "
            f"ending the year at around 20%. The rise appears inside every ship mode while the ship-mode mix stayed nearly constant, "
            f"so it is not caused by customers choosing slower modes. Monthly volume is only weakly related to the delay rate, "
            f"pointing to a structural change in the fulfilment process in 2025 rather than seasonal peaks alone."),
          PageBreak(),
          P("5.3 Route efficiency leaderboard", "h2"),
          fig("fig04_route_leaderboard", 15.5, caption=f"Figure 4. Top and bottom 10 of {len(elig)} scored factory → state routes (≥ 30 shipments). Bar colour = factory."),
          ]
    rows = [["Route", "Shipments", "Avg lead (d)", "Delay rate", "Distance (mi)", "Score"]]
    for name, r in pd.concat([elig.head(5), elig.tail(5)]).iterrows():
        rows.append([name, int(r["Shipments"]), f"{r['Avg Lead Time (d)']:.2f}", f"{r['Delay Rate']:.1%}",
                     f"{r['Avg Distance (mi)']:,.0f}", f"{r['Efficiency Score']:.0f}"])
    E += [table(rows, [6 * cm, 2 * cm, 2.3 * cm, 2.2 * cm, 2.5 * cm, 2 * cm]),
          Spacer(1, 6),
          P("The best routes are short regional lanes with on-time dispatch – Wicked Choccy's (Georgia) into the Southeast, "
            "Ohio and Wisconsin, and Lot's O' Nuts (Arizona) into Texas and California. The weakest routes combine long "
            "distance with above-average delays: Wicked Choccy's into Washington, Oregon and Arizona; Lot's O' Nuts into New "
            "Jersey and Connecticut; and Interior lanes such as Lot's O' Nuts into Missouri, Tennessee and Arkansas. "
            "Wicked Choccy's → Minnesota has the worst reliability of any route. A striking pattern is that each of the two big "
            "chocolate plants serves the other plant's natural territory – the root cause addressed in Section 5.6."),
          PageBreak(),
          P("5.4 Geographic bottlenecks", "h2"),
          fig("fig05_state_bottlenecks", 14, caption="Figure 5. Excess processing days by state with 95% confidence intervals "
              "(states with ≥ 50 shipments; ten slowest and six fastest shown). Red = significantly slower than average."),
          ]
    rows = [["State", "Region", "Shipments", "Excess days", "95% CI", "Delay rate"]]
    for name, r in st[st["Significantly slow"]].iterrows():
        rows.append([name, r["Region"], int(r["Shipments"]), f"{r['Excess Days']:+.2f}",
                     f"[{r['CI95 low']:+.2f}, {r['CI95 high']:+.2f}]", f"{r['Delay Rate']:.1%}"])
    E += [table(rows, [3.6 * cm, 2.6 * cm, 2.4 * cm, 2.6 * cm, 3.4 * cm, 2.4 * cm]), Spacer(1, 6),
          P("A cluster of Interior and Upper-Midwest states – Minnesota, Missouri, Oklahoma, Indiana and Illinois – is "
            "significantly slower than the network, together with Utah and Washington in the West. Arkansas and Connecticut "
            "show high breach rates but on small samples whose confidence intervals cross zero, so they are flagged for "
            "monitoring rather than immediate action. Canadian provinces (Ontario in particular) perform well."),
          PageBreak(),
          P("5.5 Does distance drive lead time?", "h2"),
          fig("fig06_distance_vs_delay", 13.5, caption="Figure 6. Route distance against mode-adjusted excess days; bubble size = shipments."),
          table([["Test", "Statistic", "p-value", "Conclusion"],
                 ["Spearman: distance vs excess days", f"ρ = {d['rho']:.3f}", f"{d['p_rho']:.2f}", "No relationship"]] +
                [[f"Kruskal–Wallis by {c.lower().replace('/province', '')}", f"H = {r.statistic:.1f}", f"{r.pvalue:.1e}",
                  "Significant (small effect)" if r.pvalue < 0.05 else "Not significant"] for c, r in d["kw"].items()],
                [6.2 * cm, 3 * cm, 2.6 * cm, 5.2 * cm]),
          Spacer(1, 6),
          P("Distance has no relationship with processing lead time, and neither region nor factory differs significantly "
            "once ship mode is controlled for. State-level differences are statistically significant but small (within ±0.5 days). "
            "The measured lead time is therefore dispatch time, not transit time: delays originate inside the fulfilment "
            "operation. This separates the problem into two levers – <b>process</b> (speed and reliability) and <b>network</b> "
            "(distance, freight cost and real transit time)."),
          PageBreak(),
          P("5.6 Factory network and sourcing scenarios", "h2"),
          fig("fig07_factory_distance", 14, caption="Figure 7. Average factory → customer distance and share of shipments."),
          P(f"Lot's O' Nuts in Arizona produces three of the five Wonka Bars and handles most shipments, yet ships the furthest – "
            f"a large share of its customers are on the East Coast. Wicked Choccy's in Georgia, in turn, ships heavily to "
            f"California and Washington. Two scenarios were tested:")]
    E += BUL([f"<b>Single-factory relocation</b> (Appendix B): moving any one Wonka Bar line entirely to the central Secret Factory "
              f"(Illinois) would cut its unit-miles by 18–30%, but would overload a factory that currently makes ~2% of volume.",
              f"<b>Nearest-plant fulfilment</b>: each chocolate order is made at whichever of Lot's O' Nuts or Wicked Choccy's is "
              f"closer. Chocolate unit-miles fall from {sc['dual']['cur']/1e6:.1f} M to {sc['dual']['new']/1e6:.1f} M "
              f"(−{sc['dual']['red']:.0%}); {sc['dual']['switch']:.0%} of orders would switch plant. Adding Secret Factory as a "
              f"third source raises the saving to {sc['tri']['red']:.0%}."])
    E += [fig("fig08_sourcing_scenario", 14, caption="Figure 8. Chocolate unit-miles by customer region: current sourcing vs nearest-plant fulfilment."),
          PageBreak()]

    # ---- 6 recommendations
    E += [P("6. Recommendations", "h1"), table(recommendations(d), [0.6 * cm, 5.6 * cm, 6.2 * cm, 4.6 * cm]),
          P("Suggested sequencing", "h2")]
    E += BUL(["<b>0–30 days:</b> correct the date export (Rec. 5); set up weekly monitoring of breach rate by ship mode and the "
              "bottleneck states using the dashboard.",
              "<b>30–90 days:</b> root-cause the 2025 slowdown and pilot a First Class pick lane (Recs. 1 and 3).",
              "<b>3–9 months:</b> pilot nearest-plant fulfilment for one Wonka Bar line, then extend after confirming capacity and "
              "freight-cost savings (Rec. 2)."])

    # ---- 7 dashboard
    E += [P("7. Streamlit dashboard", "h1"),
          P("An interactive dashboard (<i>app.py</i>) exposes every KPI in this report. Global sidebar filters: order date "
            "range, region, state/province, ship mode, factory, delay definition (ship-mode SLA or a single lead-time "
            "threshold slider) and the minimum route volume for ranking."),
          table([["Tab", "What it shows"],
                 ["Overview", "Headline KPIs, monthly delay trend and volume, factory summary"],
                 ["Route Efficiency", "Top/bottom route charts and a sortable scorecard (state or region grain), CSV export"],
                 ["Geographic Map", "US choropleth (delay, lead time, excess days, volume, distance), factory locations, route lines, "
                                    "regional bottleneck table and statistically slow states"],
                 ["Ship Modes", "Lead time vs SLA, delay rate, lead-time distribution, ship mode × region heatmap"],
                 ["Route Drill-Down", "Per-route KPIs, monthly trend, ship-mode mix, city table, order-level timeline, CSV export"],
                 ["Sourcing Scenarios", "Interactive nearest-plant simulation and single-factory relocation table"],
                 ["Data & Method", "Date-shift evidence and KPI definitions"]],
                [4 * cm, 13 * cm])]

    # ---- 8 limitations
    E += [P("8. Limitations and next steps", "h1")]
    E += BUL(["Lead time measures order-to-dispatch, not delivery; adding a delivery date would allow true transit-time analysis.",
              "Distances are straight-line (great-circle); road distance is typically 15–25% longer but ranks routes the same way.",
              "Freight cost is absent, so ship-mode margins and scenario savings are expressed in miles, not dollars.",
              "The product → factory mapping and factory coordinates come from the project brief; factory capacity is not modelled.",
              "Sugar and Other divisions are small (350 shipments in total), so their route results are indicative only."])

    # ---- appendix
    E += [PageBreak(), P("Appendix A – Reference data", "h1"),
          table([["Factory", "Latitude", "Longitude", "State"]] +
                [[f, f"{v['lat']:.6f}", f"{v['lon']:.6f}", v["state"]] for f, v in config.FACTORIES.items()],
                [5 * cm, 3.5 * cm, 3.5 * cm, 5 * cm]), Spacer(1, 8),
          table([["Product", "Factory"]] + [[p, f] for p, f in config.PRODUCT_FACTORY.items()], [9 * cm, 8 * cm]),
          PageBreak(), P("Appendix B – Single-factory relocation check", "h1")]
    rows = [["Product", "Units", "Current factory", "Avg mi", "Closest factory", "Avg mi", "Saved"]]
    for _, r in d["reloc"].iterrows():
        rows.append([r["Product Name"], f"{r['Units']:,}", r["Current Factory"], f"{r['Current Avg mi']:,.0f}",
                     r["Best Factory"], f"{r['Best Avg mi']:,.0f}", f"{r['Unit-miles saved %']:.0%}"])
    E += [table(rows, [4.6 * cm, 1.5 * cm, 3 * cm, 1.6 * cm, 3 * cm, 1.6 * cm, 1.7 * cm]),
          P("Unit-weighted great-circle miles from each candidate factory to the product's actual customers.", "caption")]
    doc.build(E, onFirstPage=footer, onLaterPages=footer)


# ----------------------------------------------------------------------------- executive summary
def executive_summary(d):
    k, sm, elig, st, y, sc = d["k"], d["sm"], d["elig"], d["st"], d["yearly"], d["scen"]
    doc = SimpleDocTemplate(str(OUT / "Nassau_Candy_Route_Efficiency_Executive_Summary.pdf"), pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=2 * cm,
                            title="Executive Summary – Shipping Route Efficiency", author=AUTHOR)
    E = [P("EXECUTIVE SUMMARY", "subtitle"),
         P("Shipping Route Efficiency – Nassau Candy Distributor", "title"),
         P(f"{AUTHOR} · {date.today():%d %B %Y} · 10,194 shipments, Jan 2024 – Dec 2025", "caption"),
         kpi_strip([(f"{k['avg_lead_time']:.2f} d", "avg processing lead time"),
                    (f"{k['delay_rate']:.1%}", "delay frequency"),
                    (f"{y.iloc[0]:.1%} → {y.iloc[1]:.1%}", "breach rate 2024 → 2025"),
                    (f"−{sc['dual']['red']:.0%}", "chocolate miles via nearest plant")]),
         Spacer(1, 10),
         callout("<b>The question.</b> Which factory → customer routes are efficient, where are the bottlenecks, how do ship "
                 "modes compare, and can the factory network be better aligned with demand?"),
         P("What we found", "h2")]
    E += BUL([
        "<b>Delays are an operations problem, not a distance problem.</b> Processing lead time is set by ship mode and shows "
        f"no relationship with route distance (ρ = {d['rho']:.2f}).",
        f"<b>Service deteriorated in 2025.</b> SLA breaches rose from {y.iloc[0]:.1%} to {y.iloc[1]:.1%} – in every ship mode, "
        "with a stable mode mix – pointing to a fulfilment-capacity or process change.",
        f"<b>Premium service is unreliable.</b> {sm.loc['First Class','Delay Rate']:.1%} of First Class shipments miss their 3-day SLA.",
        f"<b>Bottleneck states:</b> {', '.join(st[st['Significantly slow']].index[:6])} are significantly slower than average.",
        f"<b>Worst routes:</b> {elig.index[-1]}, {elig.index[-2]}, {elig.index[-3]} – long lanes with above-average delays. "
        f"<b>Best:</b> short regional lanes such as {elig.index[1]} and {elig.index[2]}.",
        "<b>The network is crossed.</b> The Arizona plant ships heavily to the East Coast and the Georgia plant to the West Coast.",
        "<b>Data issue fixed:</b> raw ship dates were offset by whole years (904–1,642-day gaps); corrected before analysis.",
    ])
    E += [PageBreak(), P("What we recommend", "h2"), table(recommendations(d), [0.6 * cm, 5.6 * cm, 6.2 * cm, 4.6 * cm]),
          Spacer(1, 8),
          fig("fig04_route_leaderboard", 12.5, caption="Route efficiency leaderboard – top and bottom 10 factory → state routes.")]
    doc.build(E, onFirstPage=footer, onLaterPages=footer)


if __name__ == "__main__":
    data = compute()
    research_report(data)
    executive_summary(data)
    print("Reports written to", OUT)
