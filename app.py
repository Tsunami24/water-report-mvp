"""
Flask web app for the groundwater/well report pipeline.

Startup loads both datasets once into memory (~2-3 s); subsequent requests
are fast (geopandas point-in-polygon + pandas distance calc only).

Usage:
    python3 app.py
    open http://localhost:5000
"""

import io
import json
import os
import urllib.parse
import urllib.request
from datetime import date

from flask import Flask, Response, abort, render_template, request

from src.basin import get_basin_context, load_basins
from src.wells import get_nearby_wells, load_wells
from src.charts import depth_histogram, drilling_timeline, use_breakdown_chart, well_map_data
from src.box_links import load_plss_folder_map, get_wcr_file_urls

BASINS_PATH = os.environ.get("BASINS_PATH", "data/real/basin_boundaries.geojson")
WELLS_PATH = os.environ.get("WELLS_PATH", "data/real/well_completion_reports.csv")
BOX_PLSS_PATH = os.environ.get("BOX_PLSS_PATH", "data/real/box_plss_folders.json")

app = Flask(__name__)

print(f"Loading basin boundaries from {BASINS_PATH} ...", flush=True)
BASINS = load_basins(BASINS_PATH)
print(f"Loading well completion reports from {WELLS_PATH} ...", flush=True)
WELLS = load_wells(WELLS_PATH)
print(f"Loading Box PLSS folder map from {BOX_PLSS_PATH} ...", flush=True)
BOX_PLSS_MAP = load_plss_folder_map(BOX_PLSS_PATH)
print(f"Ready — {len(BASINS)} basins, {len(WELLS):,} wells, {len(BOX_PLSS_MAP)} PLSS sections mapped.", flush=True)


# ---------------------------------------------------------------------------
# APN lookup (SANDAG parcel service → CA State Plane → WGS84)
# ---------------------------------------------------------------------------

def lookup_apn(apn: str):
    """
    Resolve an APN to (lat, lon, label) using the SANDAG parcel FeatureServer.
    APN may be formatted (128-112-04-00) or raw digits (1281120400) — we strip dashes.
    Returns (lat, lon, label) or raises ValueError if not found.
    """
    from pyproj import Transformer
    raw = apn.replace("-", "").replace(" ", "")
    params = urllib.parse.urlencode({
        "where": f"apn='{raw}'",
        "outFields": "apn,situs_address,situs_street,situs_suffix,situs_community,situs_zip,x_coord,y_coord,acreage",
        "returnGeometry": "false",
        "f": "json",
    })
    url = f"https://geo.sandag.org/server/rest/services/Hosted/Parcels/FeatureServer/0/query?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "water-report-mvp/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    feats = data.get("features", [])
    if not feats:
        raise ValueError(f"APN {apn} not found in San Diego County parcel data.")
    a = feats[0]["attributes"]
    # Convert CA State Plane Zone 6 (EPSG:2230, US survey feet) → WGS84
    t = Transformer.from_crs("EPSG:2230", "EPSG:4326", always_xy=True)
    lon, lat = t.transform(a["x_coord"], a["y_coord"])
    # Build a readable label from whatever address fields exist
    num = str(int(a["situs_address"])) if a.get("situs_address") else ""
    street = " ".join(filter(None, [num, a.get("situs_street"), a.get("situs_suffix")])).strip()
    community = (a.get("situs_community") or "").title()
    label = ", ".join(filter(None, [street, community])) or f"APN {apn}"
    return lat, lon, label


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

def geocode_address(street: str, city: str, state: str = "CA"):
    """US Census Geocoder — free, no API key, CA addresses only in practice."""
    params = urllib.parse.urlencode({
        "street": street,
        "city": city,
        "state": state,
        "benchmark": "Public_AR_Current",
        "format": "json",
    })
    url = f"https://geocoding.geo.census.gov/geocoder/locations/address?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "water-report-mvp/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    matches = data["result"]["addressMatches"]
    if not matches:
        return None, None
    coords = matches[0]["coordinates"]
    return float(coords["y"]), float(coords["x"])  # lat, lon


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_report(apn, label, lat, lon, radius):
    """Return basin_ctx + well_data dicts for a parcel."""
    basin_ctx = get_basin_context(lat, lon, BASINS)
    well_data = get_nearby_wells(lat, lon, WELLS, radius_miles=radius)
    return basin_ctx, well_data


def _template_ctx(apn, label, lat, lon, radius, basin_ctx, well_data, **extra):
    return dict(
        apn=apn,
        label=label,
        lat=lat,
        lon=lon,
        radius=radius,
        basin=basin_ctx,
        wells=well_data,
        report_date=date.today().isoformat(),
        **extra,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/report", methods=["POST"])
def report():
    apn = request.form.get("apn", "").strip()
    label = request.form.get("label", "").strip() or apn or "Unnamed Parcel"
    street = request.form.get("street", "").strip()
    city = request.form.get("city", "Valley Center").strip()
    state = request.form.get("state", "CA").strip()
    radius = float(request.form.get("radius", 1.5))
    lat_raw = request.form.get("lat", "").strip()
    lon_raw = request.form.get("lon", "").strip()

    # Resolution priority: lat/lon > APN lookup > address geocode
    if lat_raw and lon_raw:
        try:
            lat, lon = float(lat_raw), float(lon_raw)
        except ValueError:
            return render_template("index.html", error="Invalid lat/lon — must be decimal numbers.", form=request.form)
    elif apn:
        try:
            lat, lon, apn_label = lookup_apn(apn)
            if not label or label == apn:
                label = apn_label
        except Exception as e:
            return render_template(
                "index.html",
                error=f"Could not find APN {apn} in San Diego County parcel data. "
                      "Double-check the number, or enter an address / lat-lon instead.",
                form=request.form,
            )
    elif street:
        try:
            lat, lon = geocode_address(street, city, state)
        except Exception:
            lat, lon = None, None
        if lat is None:
            return render_template(
                "index.html",
                error=f"Could not geocode '{street}, {city}, {state}'. "
                      "Try a more specific address, or enter lat/lon directly.",
                form=request.form,
            )
    else:
        return render_template("index.html", error="Enter an APN, address, or lat/lon coordinates.", form=request.form)

    basin_ctx, well_data = _run_report(apn, label, lat, lon, radius)

    charts = {}
    map_wells = []
    wcr_urls = {}
    if well_data["count"] > 0:
        records = well_data["records"]
        s = well_data["summary"]
        charts["depth"]    = depth_histogram(records, s["median_depth_ft"])
        charts["timeline"] = drilling_timeline(records)
        charts["use"]      = use_breakdown_chart(s["use_breakdown"])
        map_wells          = well_map_data(records)
        if BOX_PLSS_MAP:
            wcr_urls = get_wcr_file_urls(BOX_PLSS_MAP, records)

    ctx = _template_ctx(apn, label, lat, lon, radius, basin_ctx, well_data,
                        charts=charts, map_wells=map_wells, wcr_urls=wcr_urls)
    return render_template("report.html", **ctx)


@app.route("/report/pdf", methods=["POST"])
def report_pdf():
    from src.pdf_report import generate_pdf

    apn = request.form.get("apn", "").strip()
    label = request.form.get("label", "Unnamed Parcel").strip()
    lat = float(request.form["lat"])
    lon = float(request.form["lon"])
    radius = float(request.form.get("radius", 1.5))

    basin_ctx, well_data = _run_report(apn, label, lat, lon, radius)
    pdf_bytes = generate_pdf(apn=apn, label=label, lat=lat, lon=lon,
                             radius=radius, basin_ctx=basin_ctx, well_data=well_data)

    filename = f"water_report_{apn or 'parcel'}.pdf".replace(" ", "_").replace("/", "-")
    return Response(
        bytes(pdf_bytes),
        mimetype="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


if __name__ == "__main__":
    app.run(debug=False, port=5002)
