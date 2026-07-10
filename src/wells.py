"""
Nearby well completion report (WCR) analysis.

REAL DATA: download the OSWCR bulk dataset from data.ca.gov / CNRA open
data portal ("Well Completion Reports"), filter to your target county,
and replace data/real/well_completion_reports.csv. Column names in the
real dataset may differ slightly - check against FIELDNAMES expectations
below and adjust src/wells.py's column references if needed.

IMPORTANT CAVEAT (carry this into any report output): most OSWCR records
are geolocated to the center of the 1x1 mile PLSS section, not an exact
address point. "Nearby" therefore means "reported in this general area",
not "within N feet". Report copy should reflect this honestly.
"""

import numpy as np
import pandas as pd


COLUMN_MAP = {
    # Real OSWCR CSV uses all-caps; map to CamelCase names used throughout this codebase
    "WCRNUMBER": "WCRNumber",
    "COUNTYNAME": "County",
    "DECIMALLATITUDE": "DecimalLatitude",
    "DECIMALLONGITUDE": "DecimalLongitude",
    "PLANNEDUSEFORMERUSE": "PlannedUseFormerUse",
    "TOTALCOMPLETEDDEPTH": "TotalCompletedDepth",
    "STATICWATERLEVEL": "StaticWaterLevel",
    "WELLYIELD": "WellYield",
    "DATEWORKENDED": "DateWorkEnded",
    "TOWNSHIP": "Township",
    "RANGE": "Range",
    "SECTION": "Section",
    "DRILLERNAME": "DrillerName",
}


def load_wells(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False, dtype={"DRILLERLICENSENUMBER": str, "ELEVATIONACCURACY": str, "VERTICALDATUM": str, "DrillerlicenseNumber": str})
    # Normalize column names: real OSWCR data uses ALL_CAPS, synthetic uses CamelCase
    rename = {c: COLUMN_MAP[c] for c in df.columns if c in COLUMN_MAP}
    if rename:
        df = df.rename(columns=rename)
    df["WellYield"] = pd.to_numeric(df["WellYield"], errors="coerce")
    df["TotalCompletedDepth"] = pd.to_numeric(df["TotalCompletedDepth"], errors="coerce")
    df["StaticWaterLevel"] = pd.to_numeric(df["StaticWaterLevel"], errors="coerce")
    df["DecimalLatitude"] = pd.to_numeric(df["DecimalLatitude"], errors="coerce")
    df["DecimalLongitude"] = pd.to_numeric(df["DecimalLongitude"], errors="coerce")
    # Drop rows with no coordinates (can't compute distance)
    df = df.dropna(subset=["DecimalLatitude", "DecimalLongitude"])
    return df


def get_nearby_wells(lat: float, lon: float, wells: pd.DataFrame, radius_miles: float = 1.5) -> dict:
    R = 3958.8
    lat1 = np.radians(lat)
    lon1 = np.radians(lon)
    lat2 = np.radians(wells["DecimalLatitude"].values)
    lon2 = np.radians(wells["DecimalLongitude"].values)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    distances = 2 * R * np.arcsin(np.sqrt(a))

    df = wells.copy()
    df["distance_miles"] = distances
    nearby = df[df["distance_miles"] <= radius_miles].sort_values("distance_miles")

    if nearby.empty:
        return {
            "count": 0,
            "radius_miles": radius_miles,
            "summary": None,
            "records": [],
        }

    yields = nearby["WellYield"].dropna()

    summary = {
        "count": int(len(nearby)),
        "radius_miles": radius_miles,
        "median_depth_ft": float(nearby["TotalCompletedDepth"].median()),
        "depth_range_ft": (int(nearby["TotalCompletedDepth"].min()), int(nearby["TotalCompletedDepth"].max())),
        "median_static_water_level_ft": float(nearby["StaticWaterLevel"].median()),
        "yield_reported_count": int(len(yields)),
        "median_yield_gpm": float(yields.median()) if not yields.empty else None,
        "use_breakdown": nearby["PlannedUseFormerUse"].value_counts().to_dict(),
        "date_range": (str(nearby["DateWorkEnded"].min())[:10], str(nearby["DateWorkEnded"].max())[:10]),
    }

    records = nearby.to_dict(orient="records")
    # Normalize DateWorkEnded to a plain string (or None) so templates can safely slice it
    for r in records:
        d = r.get("DateWorkEnded")
        try:
            r["DateWorkEnded"] = str(d)[:10] if d and str(d) not in ("nan", "NaT") else None
        except Exception:
            r["DateWorkEnded"] = None

    return {
        "count": int(len(nearby)),
        "radius_miles": radius_miles,
        "summary": summary,
        "records": records,
    }


if __name__ == "__main__":
    wells = load_wells("data/sample/well_completion_reports.csv")

    test_points = {
        "Escondido-area test point (in-basin)": (33.090, -117.040),
        "Valley Center test point (non-basin)": (33.220, -117.030),
    }

    for label, (lat, lon) in test_points.items():
        result = get_nearby_wells(lat, lon, wells, radius_miles=1.5)
        print(f"\n{label}")
        print(f"  Wells within {result['radius_miles']} mi: {result['count']}")
        if result["summary"]:
            s = result["summary"]
            print(f"  Median depth: {s['median_depth_ft']} ft (range {s['depth_range_ft']})")
            print(f"  Median static water level: {s['median_static_water_level_ft']} ft")
            yield_note = f", median {s['median_yield_gpm']} gpm" if s['median_yield_gpm'] else ""
            print(f"  Yield reported on {s['yield_reported_count']}/{result['count']} wells{yield_note}")
            print(f"  Use breakdown: {s['use_breakdown']}")
            print(f"  Date range of records: {s['date_range']}")
