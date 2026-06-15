"""
Basin context lookup.

Determines whether a given lat/lon falls inside a Bulletin 118 groundwater
basin polygon, and if so, returns basin metadata (SGMA priority, GSA, etc.)

REAL DATA: Bulletin 118 basin boundaries are published by DWR via the SGMA
Data Viewer / CNRA open data portal as GeoJSON/shapefile. Download and
replace data/real/basin_boundaries.geojson with the real file - the property
names used below (basin_id, basin_name, priority, sgma_managed, gsa_name)
should be mapped from whatever field names the real dataset uses.
"""

import geopandas as gpd
from shapely.geometry import Point


def load_basins(path: str) -> gpd.GeoDataFrame:
    return gpd.read_file(path)


def get_basin_context(lat: float, lon: float, basins: gpd.GeoDataFrame) -> dict:
    """
    Returns:
        {"in_basin": False}
        or
        {"in_basin": True, "basin_id": ..., "basin_name": ..., "priority": ...,
         "sgma_managed": ..., "gsa_name": ...}
    """
    point = Point(lon, lat)  # NOTE: shapely Point is (x=lon, y=lat)

    matches = basins[basins.geometry.contains(point)]

    if matches.empty:
        return {"in_basin": False}

    row = matches.iloc[0]
    # Real DWR B118 GeoJSON field names (CNRA open data)
    basin_id = row.get("Basin_Subbasin_Number") or row.get("basin_id")
    basin_name = row.get("Basin_Subbasin_Name") or row.get("Basin_Name") or row.get("basin_name")
    priority = row.get("Priority") or row.get("priority")
    sgma_managed = row.get("SGMA_Managed") or row.get("sgma_managed") or False
    gsa_name = row.get("GSA_Name") or row.get("gsa_name")
    return {
        "in_basin": True,
        "basin_id": basin_id,
        "basin_name": basin_name,
        "priority": priority,
        "sgma_managed": bool(sgma_managed),
        "gsa_name": gsa_name,
    }


if __name__ == "__main__":
    basins = load_basins("data/sample/basin_boundaries.geojson")

    test_points = {
        "Inside synthetic basin (Escondido-area test point)": (33.090, -117.040),
        "Outside synthetic basin (Valley Center test point)": (33.220, -117.030),
    }

    for label, (lat, lon) in test_points.items():
        result = get_basin_context(lat, lon, basins)
        print(f"{label}: {result}")
