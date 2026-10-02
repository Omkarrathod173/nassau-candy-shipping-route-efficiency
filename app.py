"""
Nassau Candy Distributor — Shipping Route Efficiency Dashboard
Run:  streamlit run app.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src import config, metrics as m

st.set_page_config(page_title="Nassau Candy · Route Efficiency", page_icon="🚚", layout="wide")

# --------------------------------------------------------------------------- #
# Style
# --------------------------------------------------------------------------- #
INK, MUTED, GRID, RED = "#1f1f1d", "#6b6a66", "#e6e5e1", "#e34948"
st.markdown("""
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: #ffffff; border: 1px solid #e6e5e1; border-radius: 10px; padding: 12px 14px;}
[data-testid="stMetricLabel"] p {font-size: 0.82rem; color: #6b6a66;}
.app-sub {color: #6b6a66; margin-top: -0.6rem; margin-bottom: 1rem;}
.note {background:#f4f7fc; border-left:4px solid #2a78d6; padding:10px 14px; border-radius:6px; font-size:0.92rem;}
</style>
""", unsafe_allow_html=True)


def style_fig(fig: go.Figure, height: int = 380) -> go.Figure:
    fig.update_layout(template="plotly_white", height=height, margin=dict(l=10, r=10, t=50, b=10),
                      font=dict(color=INK, size=12), title_font=dict(size=15), title_x=0,
                      legend=dict(orientation="h", yanchor="top", y=-0.22, xanchor="left", x=0, title=None),
                      hoverlabel=dict(bgcolor="white"))
    fig.update_xaxes(gridcolor=GRID, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


US_ABBR = {"Alabama": "AL", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO",
           "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
           "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
           "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI",
           "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
           "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
           "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
           "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
           "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
           "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY"}


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #
@st.cache_data(show_spinner="Loading shipments…")
def load() -> pd.DataFrame:
    if not config.PROCESSED_DATA.exists():
        from src import data_prep
        df, _ = data_prep.clean(data_prep.load_raw())
        data_prep.save(df)
    return m.load_clean()


data = load()

# --------------------------------------------------------------------------- #
# Sidebar filters
# --------------------------------------------------------------------------- #
with st.sidebar:
    st.header("Filters")
    dmin, dmax = data["Order Date"].min().date(), data["Order Date"].max().date()
    date_range = st.date_input("Order date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    regions = st.multiselect("Region", sorted(data["Region"].unique()), placeholder="All regions")
    state_pool = data[data["Region"].isin(regions)] if regions else data
    states = st.multiselect("State / Province", sorted(state_pool["State/Province"].unique()), placeholder="All states")
    modes = st.multiselect("Ship mode", config.SHIP_MODE_ORDER, placeholder="All ship modes")
    factories = st.multiselect("Factory", list(config.FACTORIES), placeholder="All factories")

    st.divider()
    st.subheader("Delay definition")
    delay_basis = st.radio("Flag a shipment as delayed when…",
                           ["Lead time > ship-mode SLA", "Lead time > a single threshold"], index=0)
    threshold = None
    if delay_basis.endswith("threshold"):
        threshold = st.slider("Lead-time threshold (days)", 0, 10, 5)
    else:
        st.caption("SLA: " + " · ".join(f"{k} ≤ {v} d" for k, v in config.SHIP_MODE_SLA_DAYS.items()))
    min_vol = st.slider("Minimum shipments for a route to be ranked", 5, 200, config.MIN_ROUTE_VOLUME, step=5)

    st.divider()
    st.caption("Lead time = processing days from order to dispatch. See the *Data & Method* tab.")

# Apply filters
df = data.copy()
if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    df = df[(df["Order Date"].dt.date >= date_range[0]) & (df["Order Date"].dt.date <= date_range[1])]
if regions:
    df = df[df["Region"].isin(regions)]
if states:
    df = df[df["State/Province"].isin(states)]
if modes:
    df = df[df["Ship Mode"].isin(modes)]
if factories:
    df = df[df["Factory"].isin(factories)]
df = m.apply_delay_threshold(df, threshold)
df = m.add_excess_days(df, baseline=m.apply_delay_threshold(data, threshold))

# --------------------------------------------------------------------------- #
# Header + KPI strip
# --------------------------------------------------------------------------- #
st.title("Factory-to-Customer Shipping Route Efficiency")
st.markdown('<p class="app-sub">Nassau Candy Distributor · 5 factories → 4 regions · Jan 2024 – Dec 2025</p>',
            unsafe_allow_html=True)

if df.empty:
    st.warning("No shipments match the current filters. Widen the filters in the sidebar.")
    st.stop()

k = m.headline_kpis(df)
base = m.headline_kpis(m.apply_delay_threshold(data, threshold))
c = st.columns(6)
c[0].metric("Shipments", f"{k['shipments']:,}", help="Order lines shipped")
c[1].metric("Avg lead time", f"{k['avg_lead_time']:.2f} d",
            delta=(f"{k['avg_lead_time'] - base['avg_lead_time']:+.2f} d vs all"
                   if abs(k['avg_lead_time'] - base['avg_lead_time']) >= 0.005 else None), delta_color="inverse")
c[2].metric("Delay frequency", f"{k['delay_rate']:.1%}",
            delta=(f"{(k['delay_rate'] - base['delay_rate']) * 100:+.1f} pp vs all"
                   if abs(k['delay_rate'] - base['delay_rate']) >= 0.0005 else None), delta_color="inverse")
c[3].metric("Avg route distance", f"{k['avg_distance']:,.0f} mi")
c[4].metric("Active routes", f"{k['routes']:,}", help="Distinct factory → state routes")
c[5].metric("Gross profit", f"${k['gross_profit']:,.0f}")

tabs = st.tabs(["📊 Overview", "🏁 Route Efficiency", "🗺️ Geographic Map", "🚚 Ship Modes",
                "🔎 Route Drill-Down", "🏭 Sourcing Scenarios", "📘 Data & Method"])

# --------------------------------------------------------------------------- #
# 1. Overview
# --------------------------------------------------------------------------- #
with tabs[0]:
    left, right = st.columns([1.6, 1])
    mon = df.groupby("Order Month").agg(Shipments=("Sales", "size"), Delay=("is_delayed", "mean"),
                                        Lead=("lead_time_days", "mean")).reset_index()
    with left:
        fig = px.line(mon, x="Order Month", y="Delay", markers=True, title="Monthly delay frequency",
                      color_discrete_sequence=[RED], hover_data={"Shipments": True})
        fig.update_yaxes(tickformat=".0%", title=None); fig.update_xaxes(title=None)
        st.plotly_chart(style_fig(fig, 320), width="stretch")
        fig = px.bar(mon, x="Order Month", y="Shipments", title="Monthly shipment volume",
                     color_discrete_sequence=["#86b6ef"])
        fig.update_xaxes(title=None)
        st.plotly_chart(style_fig(fig, 240), width="stretch")
    with right:
        fac = df.groupby("Factory").agg(Shipments=("Sales", "size"), Avg_mi=("distance_miles", "mean"),
                                        Delay=("is_delayed", "mean"), Lead=("lead_time_days", "mean")).reset_index()
        fac = fac.sort_values("Shipments")
        fig = px.bar(fac, x="Shipments", y="Factory", orientation="h", color="Factory",
                     color_discrete_map=m.FACTORY_COLORS, title="Shipments by factory", text="Shipments")
        fig.update_layout(showlegend=False); fig.update_yaxes(title=None)
        st.plotly_chart(style_fig(fig, 280), width="stretch")
        st.dataframe(fac.sort_values("Shipments", ascending=False).set_index("Factory"),
                     column_config={"Avg_mi": st.column_config.NumberColumn("Avg distance (mi)", format="%.0f"),
                                    "Delay": st.column_config.NumberColumn("Delay rate", format="percent"),
                                    "Lead": st.column_config.NumberColumn("Avg lead (d)", format="%.2f")},
                     width="stretch")
    y = df.groupby(df["Order Date"].dt.year)["is_delayed"].mean()
    if len(y) == 2:
        st.markdown(f'<div class="note"><b>Headline:</b> delay frequency moved from <b>{y.iloc[0]:.1%}</b> in '
                    f'{y.index[0]} to <b>{y.iloc[1]:.1%}</b> in {y.index[1]} for the current selection – the rise '
                    f'happens inside every ship mode, so it is a fulfilment-process issue rather than a ship-mode mix effect.</div>',
                    unsafe_allow_html=True)

# --------------------------------------------------------------------------- #
# 2. Route efficiency
# --------------------------------------------------------------------------- #
with tabs[1]:
    grain = st.radio("Route grain", ["Factory → State", "Factory → Region"], horizontal=True)
    route_col = "Route (Factory→State)" if grain.endswith("State") else "Route (Factory→Region)"
    sc = m.route_scorecard(df, route_col, min_volume=min_vol)
    elig = sc[sc["Eligible"]]
    st.caption(f"{len(elig)} of {len(sc)} routes have ≥ {min_vol} shipments and are scored. "
               "Efficiency Score (0–100, higher = better) = 50% mode-adjusted excess days + 30% delay frequency + "
               "20% distance, each percentile-ranked across scored routes.")
    if len(elig) >= 2:
        n_show = min(10, len(elig) // 2) or 1
        a, b = st.columns(2)
        for col, part, title in [(a, elig.head(n_show), f"Top {n_show} most efficient"),
                                 (b, elig.tail(n_show), f"Bottom {n_show} least efficient")]:
            d = part.reset_index().rename(columns={route_col: "Route"})
            fig = px.bar(d, x="Efficiency Score", y="Route", orientation="h", color="Factory",
                         color_discrete_map=m.FACTORY_COLORS, title=title,
                         hover_data={"Shipments": True, "Delay Rate": ":.1%", "Avg Distance (mi)": ":.0f",
                                     "Excess Days": ":.2f", "Factory": False})
            fig.update_yaxes(categoryorder="total ascending" if "Top" in title else "total descending", title=None)
            fig.update_xaxes(range=[0, 105])
            col.plotly_chart(style_fig(fig, 40 * n_show + 120), width="stretch")

    st.subheader("Route scorecard")
    show = sc.reset_index().rename(columns={route_col: "Route"})
    st.dataframe(
        show, hide_index=True, width="stretch", height=420,
        column_config={
            "Efficiency Score": st.column_config.ProgressColumn("Efficiency Score", min_value=0, max_value=100, format="%.0f"),
            "Delay Rate": st.column_config.NumberColumn(format="percent"),
            "Avg Lead Time (d)": st.column_config.NumberColumn(format="%.2f"),
            "Excess Days": st.column_config.NumberColumn(format="%+.2f"),
            "Avg Distance (mi)": st.column_config.NumberColumn(format="%.0f"),
            "Sales": st.column_config.NumberColumn(format="$%.0f"),
            "Gross Profit": st.column_config.NumberColumn(format="$%.0f"),
            "Profit per 1,000 mi": st.column_config.NumberColumn(format="$%.2f"),
        })
    st.download_button("Download scorecard (CSV)", show.to_csv(index=False), "route_scorecard.csv", "text/csv")

# --------------------------------------------------------------------------- #
# 3. Geographic map
# --------------------------------------------------------------------------- #
with tabs[2]:
    metric_label = st.selectbox("Colour states by", ["Delay frequency", "Avg lead time (days)",
                                                     "Excess days vs mode average", "Shipments", "Avg distance (mi)"])
    agg = df.groupby("State/Province").agg(
        Shipments=("Sales", "size"), **{
            "Delay frequency": ("is_delayed", "mean"),
            "Avg lead time (days)": ("lead_time_days", "mean"),
            "Excess days vs mode average": ("excess_days", "mean"),
            "Avg distance (mi)": ("distance_miles", "mean")},
        Region=("Region", "first"), Country=("Country/Region", "first"),
        lat=("customer_lat", "mean"), lon=("customer_lon", "mean")).reset_index()
    us_agg = agg[agg["Country"] == "United States"].copy()
    us_agg["code"] = us_agg["State/Province"].map(US_ABBR)
    diverging = metric_label.startswith("Excess")
    scale = (["#2a78d6", "#f0efec", "#e34948"] if diverging else
             ["#f0efec", "#f3b7b6", "#e34948", "#9c1c1c"] if metric_label in ("Delay frequency", "Avg lead time (days)")
             else ["#cde2fb", "#6da7ec", "#2a78d6", "#104281"])
    fig = px.choropleth(us_agg, locations="code", locationmode="USA-states", color=metric_label, scope="usa",
                        color_continuous_scale=scale, hover_name="State/Province",
                        color_continuous_midpoint=0 if diverging else None,
                        hover_data={"code": False, "Shipments": True, "Region": True,
                                    "Delay frequency": ":.1%", "Avg lead time (days)": ":.2f",
                                    "Excess days vs mode average": ":+.2f", "Avg distance (mi)": ":.0f"})
    show_lines = st.toggle("Show factory → state route lines (top 40 by volume)", value=True)
    if show_lines:
        routes = (df.groupby(["Factory", "State/Province"]).agg(n=("Sales", "size"), d=("is_delayed", "mean"),
                                                                lat=("customer_lat", "mean"), lon=("customer_lon", "mean"))
                  .reset_index().nlargest(40, "n"))
        for _, r in routes.iterrows():
            f = config.FACTORIES[r["Factory"]]
            fig.add_trace(go.Scattergeo(lon=[f["lon"], r["lon"]], lat=[f["lat"], r["lat"]], mode="lines",
                                        line=dict(width=0.6 + 4 * r["n"] / routes["n"].max(), color=m.FACTORY_COLORS[r["Factory"]]),
                                        opacity=0.55, hoverinfo="text", showlegend=False,
                                        text=f"{r['Factory']} → {r['State/Province']}<br>{r['n']} shipments · {r['d']:.0%} delayed"))
    for name, f in config.FACTORIES.items():
        fig.add_trace(go.Scattergeo(lon=[f["lon"]], lat=[f["lat"]], mode="markers+text", text=[name],
                                    textposition="top center", name=name,
                                    marker=dict(size=13, symbol="square", color=m.FACTORY_COLORS[name],
                                                line=dict(color="white", width=2))))
    fig.update_layout(geo=dict(bgcolor="rgba(0,0,0,0)", lakecolor="white"),
                      title=f"{metric_label} by customer state · factories shown as squares")
    st.plotly_chart(style_fig(fig, 560), width="stretch")

    a, b = st.columns(2)
    with a:
        st.subheader("Regional bottlenecks")
        reg = df.groupby("Region").agg(Shipments=("Sales", "size"), Lead=("lead_time_days", "mean"),
                                       Excess=("excess_days", "mean"), Delay=("is_delayed", "mean"),
                                       Dist=("distance_miles", "mean")).sort_values("Excess", ascending=False)
        st.dataframe(reg, width="stretch", column_config={
            "Lead": st.column_config.NumberColumn("Avg lead (d)", format="%.2f"),
            "Excess": st.column_config.NumberColumn("Excess days", format="%+.2f"),
            "Delay": st.column_config.NumberColumn("Delay rate", format="percent"),
            "Dist": st.column_config.NumberColumn("Avg distance (mi)", format="%.0f")})
    with b:
        st.subheader("States significantly slower than average")
        sb = m.state_bottlenecks(df, min_volume=min(50, max(5, min_vol)))
        slow = sb[sb["Significantly slow"]][["Region", "Shipments", "Excess Days", "CI95 low", "CI95 high", "Delay Rate"]]
        if slow.empty:
            st.info("No state is significantly slower than average for this selection.")
        else:
            st.dataframe(slow, width="stretch", column_config={
                "Excess Days": st.column_config.NumberColumn(format="%+.2f"),
                "CI95 low": st.column_config.NumberColumn(format="%+.2f"),
                "CI95 high": st.column_config.NumberColumn(format="%+.2f"),
                "Delay Rate": st.column_config.NumberColumn(format="percent")})
        st.caption("Excess days = lead time minus the ship-mode average; a state is flagged when the lower bound "
                   "of its 95% confidence interval is above zero.")

# --------------------------------------------------------------------------- #
# 4. Ship modes
# --------------------------------------------------------------------------- #
with tabs[3]:
    sm = m.ship_mode_summary(df).reset_index()
    a, b = st.columns(2)
    fig = px.bar(sm, x="Ship Mode", y="Avg Lead Time (d)", color="Ship Mode", color_discrete_map=m.SHIP_MODE_COLORS,
                 title="Average lead time vs SLA target", text_auto=".2f")
    fig.add_trace(go.Scatter(x=sm["Ship Mode"], y=sm["SLA (d)"], mode="markers", name="SLA target",
                             marker=dict(symbol="line-ew-open", size=40, color=INK, line=dict(width=3))))
    fig.update_xaxes(title=None)
    a.plotly_chart(style_fig(fig, 360), width="stretch")
    fig = px.bar(sm, x="Ship Mode", y="Delay Rate", color="Ship Mode", color_discrete_map=m.SHIP_MODE_COLORS,
                 title="Delay frequency by ship mode", text_auto=".1%")
    fig.update_yaxes(tickformat=".0%"); fig.update_layout(showlegend=False); fig.update_xaxes(title=None)
    b.plotly_chart(style_fig(fig, 360), width="stretch")

    a, b = st.columns(2)
    dist = df.groupby(["Ship Mode", "lead_time_days"]).size().rename("n").reset_index()
    dist["Share"] = dist["n"] / dist.groupby("Ship Mode")["n"].transform("sum")
    fig = px.line(dist, x="lead_time_days", y="Share", color="Ship Mode", markers=True,
                  color_discrete_map=m.SHIP_MODE_COLORS, category_orders={"Ship Mode": config.SHIP_MODE_ORDER},
                  title="Lead-time distribution by ship mode", labels={"lead_time_days": "Lead time (days)"})
    fig.update_yaxes(tickformat=".0%")
    a.plotly_chart(style_fig(fig, 360), width="stretch")
    hm = df.pivot_table(index="Ship Mode", columns="Region", values="is_delayed", aggfunc="mean").reindex(
        [x for x in config.SHIP_MODE_ORDER if x in df["Ship Mode"].unique()])
    fig = px.imshow(hm, text_auto=".0%", color_continuous_scale=["#f0efec", "#f3b7b6", "#e34948"], aspect="auto",
                    title="Delay frequency: ship mode × region")
    fig.update_coloraxes(showscale=False)
    b.plotly_chart(style_fig(fig, 360), width="stretch")

    st.dataframe(sm.set_index("Ship Mode"), width="stretch", column_config={
        "Share": st.column_config.NumberColumn(format="percent"),
        "Avg Lead Time (d)": st.column_config.NumberColumn(format="%.2f"),
        "Delay Rate": st.column_config.NumberColumn(format="percent"),
        "Avg Distance (mi)": st.column_config.NumberColumn(format="%.0f"),
        "Gross Margin %": st.column_config.NumberColumn(format="%.1f%%")})
    st.caption("Gross margin is nearly identical across modes because the dataset does not record freight cost.")

# --------------------------------------------------------------------------- #
# 5. Route drill-down
# --------------------------------------------------------------------------- #
with tabs[4]:
    vol = df["Route (Factory→State)"].value_counts()
    route = st.selectbox("Choose a route (ordered by volume)", vol.index,
                         format_func=lambda r: f"{r}   ·   {vol[r]:,} shipments")
    r = df[df["Route (Factory→State)"] == route]
    c = st.columns(5)
    c[0].metric("Shipments", f"{len(r):,}")
    c[1].metric("Avg lead time", f"{r['lead_time_days'].mean():.2f} d")
    c[2].metric("Excess days vs mode avg", f"{r['excess_days'].mean():+.2f} d",
                help="Positive = slower than the network average for the same ship mode")
    c[3].metric("Delay frequency", f"{r['is_delayed'].mean():.1%}")
    c[4].metric("Distance", f"{r['distance_miles'].mean():,.0f} mi")

    a, b = st.columns([1.5, 1])
    rm = r.groupby("Order Month").agg(Shipments=("Sales", "size"), Delay=("is_delayed", "mean"),
                                      Lead=("lead_time_days", "mean")).reset_index()
    fig = px.line(rm, x="Order Month", y="Lead", markers=True, title="Average lead time by month",
                  color_discrete_sequence=["#2a78d6"], hover_data={"Shipments": True, "Delay": ":.0%"},
                  labels={"Lead": "Avg lead time (d)"})
    fig.update_xaxes(title=None)
    a.plotly_chart(style_fig(fig, 320), width="stretch")
    rmode = r.groupby("Ship Mode").agg(Shipments=("Sales", "size"), Delay=("is_delayed", "mean")).reset_index()
    fig = px.bar(rmode, x="Shipments", y="Ship Mode", orientation="h", color="Ship Mode",
                 color_discrete_map=m.SHIP_MODE_COLORS, title="Ship-mode mix on this route",
                 hover_data={"Delay": ":.0%"}, category_orders={"Ship Mode": config.SHIP_MODE_ORDER})
    fig.update_layout(showlegend=False); fig.update_yaxes(title=None)
    b.plotly_chart(style_fig(fig, 320), width="stretch")

    st.subheader("Cities on this route")
    city = r.groupby("City").agg(Shipments=("Sales", "size"), Lead=("lead_time_days", "mean"),
                                 Delay=("is_delayed", "mean"), Miles=("distance_miles", "mean"),
                                 Sales=("Sales", "sum")).sort_values("Shipments", ascending=False)
    st.dataframe(city, width="stretch", height=260, column_config={
        "Lead": st.column_config.NumberColumn("Avg lead (d)", format="%.2f"),
        "Delay": st.column_config.NumberColumn("Delay rate", format="percent"),
        "Miles": st.column_config.NumberColumn("Distance (mi)", format="%.0f"),
        "Sales": st.column_config.NumberColumn(format="$%.2f")})

    st.subheader("Order-level timeline")
    orders = r[["Order ID", "Order Date", "Ship Mode", "City", "Product Name", "Units", "Sales",
                "lead_time_days", "sla_days", "is_delayed"]].sort_values("Order Date", ascending=False)
    plot_orders = orders.assign(Status=np.where(orders["is_delayed"], "Delayed", "On time"))
    fig = px.scatter(plot_orders, x="Order Date", y="lead_time_days", color="Status",
                     color_discrete_map={"On time": "#86b6ef", "Delayed": RED},
                     hover_data=["Order ID", "Ship Mode", "City", "Product Name"],
                     labels={"lead_time_days": "Lead time (d)"}, title="Each shipment on this route")
    st.plotly_chart(style_fig(fig, 340), width="stretch")
    st.dataframe(orders, hide_index=True, width="stretch", height=300,
                 column_config={"Order Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                                "lead_time_days": "Lead time (d)", "sla_days": "SLA (d)", "is_delayed": "Delayed",
                                "Sales": st.column_config.NumberColumn(format="$%.2f")})
    st.download_button("Download route shipments (CSV)", orders.to_csv(index=False),
                       f"{route.replace(' → ', '_to_').replace(' ', '_')}.csv", "text/csv")

# --------------------------------------------------------------------------- #
# 6. Sourcing scenarios
# --------------------------------------------------------------------------- #
with tabs[5]:
    st.markdown("Lead time does **not** depend on distance (it measures order processing), but distance drives "
                "freight cost and real transit time. These scenarios ask: *how far could shipments travel if "
                "production were placed closer to customers?*")
    sources = st.multiselect("Allow chocolate orders to be fulfilled from the nearest of…",
                             list(config.FACTORIES), default=["Lot's O' Nuts", "Wicked Choccy's"])
    choc = df[df["Division"] == "Chocolate"]
    if sources and not choc.empty:
        s = m.nearest_factory_scenario(choc, sources)
        cur = (s["distance_miles"] * s["Units"]).sum()
        new = (s["Scenario distance"] * s["Units"]).sum()
        c = st.columns(3)
        c[0].metric("Current chocolate unit-miles", f"{cur / 1e6:,.2f} M")
        c[1].metric("Scenario unit-miles", f"{new / 1e6:,.2f} M", delta=f"{(new / cur - 1):.0%}", delta_color="inverse")
        c[2].metric("Orders that would switch factory", f"{(s['Scenario Factory'] != s['Factory']).mean():.0%}")
        byreg = s.assign(Current=s["distance_miles"] * s["Units"] / 1e6,
                         Scenario=s["Scenario distance"] * s["Units"] / 1e6).groupby("Region")[["Current", "Scenario"]].sum()
        fig = px.bar(byreg.reset_index().melt("Region", var_name="Sourcing", value_name="Million unit-miles"),
                     x="Million unit-miles", y="Region", color="Sourcing", barmode="group", orientation="h",
                     color_discrete_map={"Current": "#8a8984", "Scenario": "#2a78d6"},
                     title="Chocolate unit-miles by customer region")
        st.plotly_chart(style_fig(fig, 340), width="stretch")
    st.subheader("Single-factory relocation check (all products)")
    reloc = m.relocation_scenarios(df)
    st.dataframe(reloc, hide_index=True, width="stretch", column_config={
        "Current Avg mi": st.column_config.NumberColumn(format="%.0f"),
        "Best Avg mi": st.column_config.NumberColumn(format="%.0f"),
        "Unit-miles saved %": st.column_config.NumberColumn(format="percent"),
        "Unit-miles saved": st.column_config.NumberColumn(format="%.0f")})
    st.caption("Unit-weighted great-circle miles from each candidate factory to the product's actual customers. "
               "Capacity and production constraints are not modelled.")

# --------------------------------------------------------------------------- #
# 7. Data & method
# --------------------------------------------------------------------------- #
with tabs[6]:
    st.subheader("Lead-time data-quality finding")
    a, b = st.columns(2)
    vc = data["raw_lead_time_days"].value_counts().sort_index().reset_index()
    fig = px.bar(vc, x="raw_lead_time_days", y="count", title="Raw Ship Date − Order Date (days)",
                 color_discrete_sequence=["#2a78d6"], labels={"raw_lead_time_days": "Raw gap (days)", "count": "Shipments"})
    a.plotly_chart(style_fig(fig, 320), width="stretch")
    ct = pd.crosstab(data["Ship Mode"], data["lead_time_days"]).reindex(config.SHIP_MODE_ORDER)
    fig = px.imshow(ct, text_auto=True, aspect="auto", color_continuous_scale=["#ffffff", "#2a78d6"],
                    title="Processing days inside each band, by ship mode",
                    labels={"x": "Processing days", "y": "", "color": "Shipments"})
    fig.update_coloraxes(showscale=False)
    b.plotly_chart(style_fig(fig, 320), width="stretch")
    st.markdown("""
The raw gap between *Ship Date* and *Order Date* is **904–1,642 days** – impossible for confectionery. Every value equals
`904 + 365·k + d` with *k* ∈ {0, 1, 2}. The remainder *d* (0–8 days) follows the ship-mode hierarchy exactly
(Same Day 0–2 → First 1–4 → Second 2–6 → Standard 3–8), so *d* is the real order-processing time and the band offset is a
date-shift introduced in the data export. **All KPIs use `lead_time_days = (raw gap − 904) mod 365`.**

| KPI | Definition |
|---|---|
| Shipping lead time | processing days from order to dispatch (date-shift removed) |
| Average lead time | mean lead time for the selected group |
| Route volume | number of shipments (order lines) on a route |
| Delay frequency | share of shipments whose lead time exceeds the delay threshold (ship-mode SLA by default) |
| Excess days | lead time minus the ship-mode average – removes mode mix so routes compare fairly |
| Route efficiency score | 0–100; 50% excess days + 30% delay frequency + 20% distance, percentile-ranked |

**Other cleaning steps:** 449 US ZIP codes restored to 5 digits (leading zero lost); every product mapped to its factory;
customers geocoded to ZIP centroids (US) or city centroids (Canada); great-circle distance via the haversine formula.
""")
    st.dataframe(pd.DataFrame(config.FACTORIES).T.rename_axis("Factory"), width="stretch")

st.divider()
st.caption("Nassau Candy Distributor · Shipping Route Efficiency Analysis · Data: 10,194 order lines (2024–2025)")
