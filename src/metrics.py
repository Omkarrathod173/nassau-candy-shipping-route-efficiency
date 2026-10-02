"""
Reusable KPI and route-scoring functions.

Both the analysis notebook and the Streamlit app import from here, so a KPI
is defined in exactly one place.

KPI definitions
---------------
Shipping Lead Time      lead_time_days  = processing days from order to dispatch
                                          (date-shift band removed, see data_prep.py)
Average Lead Time       mean(lead_time_days) over a group
Route Volume            number of shipments (order lines) on a route
Delay Frequency         share of shipments whose lead time exceeds the
                        delay threshold (ship-mode SLA by default)
Excess Days             lead_time_days minus the average for that ship mode.
                        Removes ship-mode mix so routes are compared fairly.
Route Efficiency Score  0-100, higher is better (see route_scorecard)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config

# Fixed colour per entity (validated categorical palette, never cycled)
FACTORY_COLORS = {
    "Lot's O' Nuts": "#2a78d6",
    "Wicked Choccy's": "#eb6834",
    "Secret Factory": "#1baf7a",
    "The Other Factory": "#eda100",
    "Sugar Shack": "#e87ba4",
}
SHIP_MODE_COLORS = {
    "Same Day": "#2a78d6",
    "First Class": "#eb6834",
    "Second Class": "#1baf7a",
    "Standard Class": "#eda100",
}
SCORE_WEIGHTS = {"excess_days": 0.5, "delay_rate": 0.3, "distance": 0.2}


def load_clean(path=config.PROCESSED_DATA) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["Order Date", "Ship Date", "Order Month"],
                     dtype={"Postal Code": str})
    return df


def apply_delay_threshold(df: pd.DataFrame, threshold_days: int | None = None) -> pd.DataFrame:
    """Recompute the delay flag.

    threshold_days=None -> use each ship mode's SLA (default definition).
    threshold_days=int  -> a single global threshold, e.g. "late if > 5 days".
    """
    out = df.copy()
    limit = out["sla_days"] if threshold_days is None else threshold_days
    out["is_delayed"] = out["lead_time_days"] > limit
    return out


def add_excess_days(df: pd.DataFrame, baseline: pd.DataFrame | None = None) -> pd.DataFrame:
    """Excess days = lead time minus the ship-mode average (computed on `baseline`)."""
    base = df if baseline is None else baseline
    mode_mean = base.groupby("Ship Mode")["lead_time_days"].mean()
    out = df.copy()
    out["excess_days"] = out["lead_time_days"] - out["Ship Mode"].map(mode_mean)
    return out


def headline_kpis(df: pd.DataFrame) -> dict:
    return {
        "shipments": len(df),
        "orders": df["Order ID"].nunique(),
        "avg_lead_time": df["lead_time_days"].mean(),
        "delay_rate": df["is_delayed"].mean(),
        "avg_distance": df["distance_miles"].mean(),
        "sales": df["Sales"].sum(),
        "gross_profit": df["Gross Profit"].sum(),
        "routes": df["Route (Factory→State)"].nunique(),
    }


def _pct_rank(s: pd.Series) -> pd.Series:
    """Percentile rank in [0, 1]. Used instead of min-max so a single outlier
    route cannot compress everyone else's score into a narrow band."""
    return s.rank(pct=True, method="average")


def route_scorecard(df: pd.DataFrame, route_col: str = "Route (Factory→State)",
                    min_volume: int = config.MIN_ROUTE_VOLUME) -> pd.DataFrame:
    """Aggregate KPIs per route and compute the Route Efficiency Score.

    Penalty = weighted sum of each component's percentile rank across eligible
    routes; the score rescales the penalty so best route = 100, worst = 0:
        50%  mode-adjusted excess days   (speed after removing ship-mode mix)
        30%  delay frequency             (reliability)
        20%  average distance            (cost-to-serve proxy)
    Routes below `min_volume` shipments are returned but not scored.
    """
    if "excess_days" not in df:
        df = add_excess_days(df)
    g = df.groupby(route_col)
    sc = pd.DataFrame({
        "Factory": g["Factory"].first(),
        "Shipments": g.size(),
        "Avg Lead Time (d)": g["lead_time_days"].mean(),
        "Excess Days": g["excess_days"].mean(),
        "Delay Rate": g["is_delayed"].mean(),
        "Avg Distance (mi)": g["distance_miles"].mean(),
        "Sales": g["Sales"].sum(),
        "Gross Profit": g["Gross Profit"].sum(),
    })
    sc["Profit per 1,000 mi"] = sc["Gross Profit"] / (g["distance_miles"].sum() / 1000)
    eligible = sc["Shipments"] >= min_volume
    sc["Efficiency Score"] = np.nan
    e = sc[eligible]
    if len(e):
        penalty = (SCORE_WEIGHTS["excess_days"] * _pct_rank(e["Excess Days"])
                   + SCORE_WEIGHTS["delay_rate"] * _pct_rank(e["Delay Rate"])
                   + SCORE_WEIGHTS["distance"] * _pct_rank(e["Avg Distance (mi)"]))
        # rescale so the best eligible route = 100 and the worst = 0
        lo, hi = penalty.min(), penalty.max()
        score = 1 - (penalty - lo) / (hi - lo) if hi > lo else pd.Series(1.0, index=penalty.index)
        sc.loc[eligible, "Efficiency Score"] = (100 * score).round(1)
    sc["Eligible"] = eligible
    return sc.sort_values("Efficiency Score", ascending=False)


def state_bottlenecks(df: pd.DataFrame, min_volume: int = 50) -> pd.DataFrame:
    """Per-state lead-time performance with a 95% confidence interval on excess days."""
    if "excess_days" not in df:
        df = add_excess_days(df)
    g = df.groupby("State/Province")
    st = pd.DataFrame({
        "Region": g["Region"].first(),
        "Country": g["Country/Region"].first(),
        "Shipments": g.size(),
        "Avg Lead Time (d)": g["lead_time_days"].mean(),
        "Excess Days": g["excess_days"].mean(),
        "Delay Rate": g["is_delayed"].mean(),
        "Avg Distance (mi)": g["distance_miles"].mean(),
    })
    se = g["excess_days"].std() / np.sqrt(st["Shipments"])
    st["CI95 low"] = st["Excess Days"] - 1.96 * se
    st["CI95 high"] = st["Excess Days"] + 1.96 * se
    st["Significantly slow"] = st["CI95 low"] > 0
    st = st[st["Shipments"] >= min_volume]
    return st.sort_values("Excess Days", ascending=False)


def ship_mode_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("Ship Mode")
    out = pd.DataFrame({
        "Shipments": g.size(),
        "Share": g.size() / len(df),
        "Avg Lead Time (d)": g["lead_time_days"].mean(),
        "Median Lead Time (d)": g["lead_time_days"].median(),
        "SLA (d)": g["sla_days"].first(),
        "Delay Rate": g["is_delayed"].mean(),
        "Avg Distance (mi)": g["distance_miles"].mean(),
        "Gross Margin %": g["Gross Profit"].sum() / g["Sales"].sum() * 100,
    })
    return out.reindex([m for m in config.SHIP_MODE_ORDER if m in out.index])


def relocation_scenarios(df: pd.DataFrame) -> pd.DataFrame:
    """For each product, unit-weighted average shipping distance if it were made
    at each factory. Shows which products are produced far from their customers."""
    from src.data_prep import haversine_miles

    rows = []
    for product, g in df.groupby("Product Name"):
        current = config.PRODUCT_FACTORY[product]
        dist = {f: np.average(haversine_miles(c["lat"], c["lon"], g["customer_lat"], g["customer_lon"]),
                              weights=g["Units"]) for f, c in config.FACTORIES.items()}
        best = min(dist, key=dist.get)
        rows.append({
            "Product Name": product,
            "Division": g["Division"].iloc[0],
            "Shipments": len(g),
            "Units": int(g["Units"].sum()),
            "Current Factory": current,
            "Current Avg mi": dist[current],
            "Best Factory": best,
            "Best Avg mi": dist[best],
            "Unit-miles saved %": 1 - dist[best] / dist[current],
            "Unit-miles saved": (dist[current] - dist[best]) * g["Units"].sum(),
        })
    return pd.DataFrame(rows).sort_values("Unit-miles saved", ascending=False)


def nearest_factory_scenario(df: pd.DataFrame, candidate_factories: list[str]) -> pd.DataFrame:
    """Dual-sourcing scenario: each shipment is fulfilled from whichever of
    `candidate_factories` is closest to the customer."""
    from src.data_prep import haversine_miles

    d = pd.DataFrame({f: haversine_miles(config.FACTORIES[f]["lat"], config.FACTORIES[f]["lon"],
                                         df["customer_lat"], df["customer_lon"])
                      for f in candidate_factories}, index=df.index)
    out = df[["Product Name", "Region", "State/Province", "Units", "Factory", "distance_miles"]].copy()
    out["Scenario Factory"] = d.idxmin(axis=1)
    out["Scenario distance"] = d.min(axis=1)
    return out
