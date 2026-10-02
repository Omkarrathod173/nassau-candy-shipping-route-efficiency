"""
Project-wide constants: factory locations, product-to-factory mapping,
ship-mode service-level targets and file paths.

Keeping these in one module means the cleaning pipeline, the analysis
notebook and the Streamlit app all use exactly the same definitions.
"""
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #
ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = ROOT / "data" / "raw" / "Nassau_Candy_Distributor.csv"
PROCESSED_DATA = ROOT / "data" / "processed" / "shipments_clean.csv"
REFERENCE_DIR = ROOT / "data" / "reference"
FIGURES_DIR = ROOT / "reports" / "figures"

# --------------------------------------------------------------------------- #
# Factory master data (from the project brief: "Factories Co-ordinates")
# --------------------------------------------------------------------------- #
FACTORIES = {
    "Lot's O' Nuts":     {"lat": 32.881893, "lon": -111.768036, "state": "Arizona"},
    "Wicked Choccy's":   {"lat": 32.076176, "lon": -81.088371,  "state": "Georgia"},
    "Sugar Shack":       {"lat": 48.119140, "lon": -96.181150,  "state": "Minnesota"},
    "Secret Factory":    {"lat": 41.446333, "lon": -90.565487,  "state": "Illinois"},
    "The Other Factory": {"lat": 35.117500, "lon": -89.971107,  "state": "Tennessee"},
}

# --------------------------------------------------------------------------- #
# Product -> manufacturing factory (from "Products and Factories Correlation")
# --------------------------------------------------------------------------- #
PRODUCT_FACTORY = {
    "Wonka Bar - Nutty Crunch Surprise": "Lot's O' Nuts",
    "Wonka Bar - Fudge Mallows":         "Lot's O' Nuts",
    "Wonka Bar -Scrumdiddlyumptious":    "Lot's O' Nuts",
    "Wonka Bar - Milk Chocolate":        "Wicked Choccy's",
    "Wonka Bar - Triple Dazzle Caramel": "Wicked Choccy's",
    "Laffy Taffy":                       "Sugar Shack",
    "SweeTARTS":                         "Sugar Shack",
    "Nerds":                             "Sugar Shack",
    "Fun Dip":                           "Sugar Shack",
    "Fizzy Lifting Drinks":              "Sugar Shack",
    "Everlasting Gobstopper":            "Secret Factory",
    "Lickable Wallpaper":                "Secret Factory",
    "Wonka Gum":                         "Secret Factory",
    "Hair Toffee":                       "The Other Factory",
    "Kazookles":                         "The Other Factory",
}

# --------------------------------------------------------------------------- #
# Canadian customer cities (postal codes in the file are 3-char FSAs, so we
# geocode at city level)
# --------------------------------------------------------------------------- #
CANADA_CITY_COORDS = {
    ("Toronto", "Ontario"):                      (43.6532, -79.3832),
    ("Calgary", "Alberta"):                      (51.0447, -114.0719),
    ("Edmonton", "Alberta"):                     (53.5461, -113.4938),
    ("Vancouver", "British Columbia"):           (49.2827, -123.1207),
    ("Montreal", "Quebec"):                      (45.5017, -73.5673),
    ("Quebec City", "Quebec"):                   (46.8139, -71.2080),
    ("Halifax", "Nova Scotia"):                  (44.6488, -63.5752),
    ("St. John's", "Newfoundland and Labrador"): (47.5615, -52.7126),
    ("Moncton", "New Brunswick"):                (46.0878, -64.7782),
    ("Charlottetown", "Prince Edward Island"):   (46.2382, -63.1311),
    ("Winnipeg", "Manitoba"):                    (49.8951, -97.1384),
    ("Regina", "Saskatchewan"):                  (50.4452, -104.6189),
}

# --------------------------------------------------------------------------- #
# Lead-time rules
# --------------------------------------------------------------------------- #
# Raw (Ship Date - Order Date) gaps fall in bands that start at 904 days and
# repeat every 365 days. The remainder inside each band is the real
# order-processing time (see README, "Data quality finding").
DATE_SHIFT_BASE_DAYS = 904
DATE_SHIFT_PERIOD_DAYS = 365

# Service-level target (max acceptable processing days) per ship mode.
# Set at roughly the 75th percentile of each mode's observed processing time.
SHIP_MODE_SLA_DAYS = {
    "Same Day": 1,
    "First Class": 3,
    "Second Class": 5,
    "Standard Class": 6,
}
SHIP_MODE_ORDER = ["Same Day", "First Class", "Second Class", "Standard Class"]

# Routes with fewer shipments than this are excluded from rankings so that a
# handful of orders cannot dominate the leaderboard.
MIN_ROUTE_VOLUME = 30
