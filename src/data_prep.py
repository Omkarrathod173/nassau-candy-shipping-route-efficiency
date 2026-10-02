"""
Data preparation pipeline for the Nassau Candy shipping-route analysis.

Run from the repository root:
    python -m src.data_prep

Steps
-----
1. Load raw CSV with Postal Code kept as text.
2. Parse dates (file uses DD-MM-YYYY) and validate Sales - Cost = Gross Profit.
3. Repair US ZIP codes that lost their leading zero (e.g. 2108 -> 02108).
4. Map each product to its manufacturing factory.
5. Geocode customers (US ZIP centroid, Canadian city centroid).
6. Compute great-circle (haversine) factory -> customer distance.
7. Engineer lead-time features:
       raw_lead_time_days  = Ship Date - Order Date
       date_shift_band     = which 365-day band the raw gap falls in
       lead_time_days      = processing days inside that band (used for KPIs)
       is_delayed          = lead_time_days > ship-mode SLA
8. Save the tidy, analysis-ready table plus reference tables.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import zipcodes

from src import config


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def haversine_miles(lat1, lon1, lat2, lon2):
    """Vectorised great-circle distance in miles between two sets of points."""
    r_earth_miles = 3958.8
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * r_earth_miles * np.arcsin(np.sqrt(a))


def _geocode_us_zip(zip5: str) -> tuple[float, float]:
    match = zipcodes.matching(zip5)
    if not match:
        return (np.nan, np.nan)
    return float(match[0]["lat"]), float(match[0]["long"])


def build_customer_geo(df: pd.DataFrame) -> pd.DataFrame:
    """One row per unique customer location with lat/lon."""
    locs = df[["Country/Region", "City", "State/Province", "Postal Code"]].drop_duplicates()
    lats, lons = [], []
    for _, row in locs.iterrows():
        if row["Country/Region"] == "United States":
            lat, lon = _geocode_us_zip(row["Postal Code"])
        else:
            lat, lon = config.CANADA_CITY_COORDS.get((row["City"], row["State/Province"]), (np.nan, np.nan))
        lats.append(lat)
        lons.append(lon)
    locs["customer_lat"], locs["customer_lon"] = lats, lons
    return locs


# --------------------------------------------------------------------------- #
# Main pipeline
# --------------------------------------------------------------------------- #
def load_raw() -> pd.DataFrame:
    return pd.read_csv(config.RAW_DATA, dtype={"Postal Code": str})


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    report: dict = {"rows_raw": len(df)}

    # 1. Dates ---------------------------------------------------------------
    df["Order Date"] = pd.to_datetime(df["Order Date"], format="%d-%m-%Y")
    df["Ship Date"] = pd.to_datetime(df["Ship Date"], format="%d-%m-%Y")

    # 2. Integrity checks ---------------------------------------------------
    report["missing_values"] = int(df.isna().sum().sum())
    report["duplicate_rows"] = int(df.duplicated().sum())
    report["max_profit_identity_error"] = float((df["Sales"] - df["Cost"] - df["Gross Profit"]).abs().max())
    report["ship_before_order"] = int((df["Ship Date"] < df["Order Date"]).sum())
    df = df.drop_duplicates()

    # 3. ZIP repair (US only; Canada uses 3-char FSA) ------------------------
    us = df["Country/Region"] == "United States"
    report["zip_codes_padded"] = int((us & (df["Postal Code"].str.len() == 4)).sum())
    df.loc[us, "Postal Code"] = df.loc[us, "Postal Code"].str.zfill(5)

    # 4. Factory mapping -----------------------------------------------------
    df["Factory"] = df["Product Name"].map(config.PRODUCT_FACTORY)
    report["unmapped_products"] = int(df["Factory"].isna().sum())
    fac = pd.DataFrame(config.FACTORIES).T.rename(columns={"lat": "factory_lat", "lon": "factory_lon", "state": "factory_state"})
    df = df.merge(fac, left_on="Factory", right_index=True, how="left")

    # 5. Geocoding -----------------------------------------------------------
    geo = build_customer_geo(df)
    df = df.merge(geo, on=["Country/Region", "City", "State/Province", "Postal Code"], how="left")
    report["ungeocoded_rows"] = int(df["customer_lat"].isna().sum())

    # 6. Distance ------------------------------------------------------------
    df["distance_miles"] = haversine_miles(
        df["factory_lat"].astype(float), df["factory_lon"].astype(float),
        df["customer_lat"], df["customer_lon"],
    ).round(1)

    # 7. Lead time -----------------------------------------------------------
    raw = (df["Ship Date"] - df["Order Date"]).dt.days
    shifted = raw - config.DATE_SHIFT_BASE_DAYS
    df["raw_lead_time_days"] = raw
    df["date_shift_band"] = shifted // config.DATE_SHIFT_PERIOD_DAYS
    df["lead_time_days"] = shifted % config.DATE_SHIFT_PERIOD_DAYS
    df["sla_days"] = df["Ship Mode"].map(config.SHIP_MODE_SLA_DAYS)
    df["is_delayed"] = df["lead_time_days"] > df["sla_days"]
    df["days_over_sla"] = (df["lead_time_days"] - df["sla_days"]).clip(lower=0)
    report["raw_lead_time_range"] = (int(raw.min()), int(raw.max()))
    report["adjusted_lead_time_range"] = (int(df["lead_time_days"].min()), int(df["lead_time_days"].max()))

    # 8. Convenience fields -------------------------------------------------
    df["Route (Factory→State)"] = df["Factory"] + " → " + df["State/Province"]
    df["Route (Factory→Region)"] = df["Factory"] + " → " + df["Region"]
    df["Order Month"] = df["Order Date"].dt.to_period("M").dt.to_timestamp()
    df["Order Quarter"] = df["Order Date"].dt.to_period("Q").astype(str)
    df["Gross Margin %"] = (df["Gross Profit"] / df["Sales"] * 100).round(2)
    df["Profit per 100 mi"] = (df["Gross Profit"] / df["distance_miles"].replace(0, np.nan) * 100).round(4)

    report["rows_clean"] = len(df)
    return df, report


def save(df: pd.DataFrame) -> None:
    config.PROCESSED_DATA.parent.mkdir(parents=True, exist_ok=True)
    config.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(config.PROCESSED_DATA, index=False)

    pd.DataFrame(config.FACTORIES).T.rename_axis("Factory").reset_index().to_csv(
        config.REFERENCE_DIR / "factories.csv", index=False)
    pd.Series(config.PRODUCT_FACTORY, name="Factory").rename_axis("Product Name").reset_index().to_csv(
        config.REFERENCE_DIR / "product_factory_map.csv", index=False)
    pd.Series(config.SHIP_MODE_SLA_DAYS, name="sla_days").rename_axis("Ship Mode").reset_index().to_csv(
        config.REFERENCE_DIR / "ship_mode_sla.csv", index=False)


def main() -> None:
    df, report = clean(load_raw())
    save(df)
    print("Data-quality report")
    for k, v in report.items():
        print(f"  {k:<28} {v}")
    print(f"Saved -> {config.PROCESSED_DATA.relative_to(config.ROOT)}")


if __name__ == "__main__":
    main()
