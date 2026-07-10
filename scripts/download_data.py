"""
Downloads real datasets into data/real/ at Docker build time (or on demand).
Run with: python3 scripts/download_data.py
"""

import json
import os
import urllib.parse
import urllib.request

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "real")
os.makedirs(OUT_DIR, exist_ok=True)


def log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# 1. Bulletin 118 basin boundaries (CNRA ArcGIS Hub — GeoJSON)
# ---------------------------------------------------------------------------

BASINS_URL = (
    "https://gis.data.cnra.ca.gov/api/download/v1/items/"
    "49807a1fbc584631bdf88d9ca71dd083/geojson?layers=0"
)
SGMA_URL = (
    "https://gis.water.ca.gov/arcgis/rest/services/Geoscientific/"
    "i08_B118_SGMA_2019_Basin_Prioritization/MapServer/1/query"
    "?where=1%3D1"
    "&outFields=atlas_wmas.SDE.i08_SGMA_2019_Basin_Prioritization.Basin_Subbasin_Number"
    "%2Catlas_wmas.SDE.i08_SGMA_2019_Basin_Prioritization.Priority"
    "&returnGeometry=false&f=json&resultRecordCount=2000"
)

log("Downloading Bulletin 118 basin boundaries...")
req = urllib.request.Request(BASINS_URL, headers={"User-Agent": "water-report-mvp/1.0"})
with urllib.request.urlopen(req, timeout=120) as r:
    gj = json.load(r)
log(f"  {len(gj['features'])} basins loaded.")

log("Fetching SGMA 2019 basin prioritization...")
with urllib.request.urlopen(SGMA_URL, timeout=30) as r:
    sgma_data = json.load(r)

priority_lookup = {}
for feat in sgma_data.get("features", []):
    a = feat["attributes"]
    bsn = a.get("atlas_wmas.SDE.i08_SGMA_2019_Basin_Prioritization.Basin_Subbasin_Number")
    pri = a.get("atlas_wmas.SDE.i08_SGMA_2019_Basin_Prioritization.Priority")
    priority_lookup[bsn] = pri

for feat in gj["features"]:
    p = feat["properties"]
    pri = priority_lookup.get(p.get("Basin_Subbasin_Number"))
    p["Priority"] = pri
    p["SGMA_Managed"] = pri in ("High", "Medium")

basins_path = os.path.join(OUT_DIR, "basin_boundaries.geojson")
with open(basins_path, "w") as f:
    json.dump(gj, f)
log(f"  Saved {basins_path} ({os.path.getsize(basins_path) // 1024 // 1024} MB)")


# ---------------------------------------------------------------------------
# 2. OSWCR well completion reports — San Diego County (CKAN datastore API)
# ---------------------------------------------------------------------------

CKAN_RESOURCE_ID = "ee7438c2-d7d5-45bd-980e-786a59e7e92c"
BATCH = 10000

log("Downloading OSWCR well completion reports (statewide CA)...")

import csv

wells_path = os.path.join(OUT_DIR, "well_completion_reports.csv")
offset = 0
total_written = 0
writer = None

with open(wells_path, "w", newline="") as fout:
    while True:
        params = urllib.parse.urlencode({
            "resource_id": CKAN_RESOURCE_ID,
            "fields": "WCRNUMBER,COUNTYNAME,DECIMALLATITUDE,DECIMALLONGITUDE,PLANNEDUSEFORMERUSE,TOTALCOMPLETEDDEPTH,STATICWATERLEVEL,WELLYIELD,DATEWORKENDED,TOWNSHIP,RANGE,SECTION,DRILLERNAME",
            "limit": BATCH,
            "offset": offset,
        })
        url = f"https://data.ca.gov/api/3/action/datastore_search?{params}"
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.load(r)

        records = data["result"]["records"]
        if not records:
            break

        if writer is None:
            fieldnames = [f["id"] for f in data["result"]["fields"] if f["id"] != "_id"]
            writer = csv.DictWriter(fout, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

        writer.writerows(records)
        total_written += len(records)
        log(f"  {total_written} records...")

        if len(records) < BATCH:
            break
        offset += BATCH

log(f"  Saved {wells_path} ({os.path.getsize(wells_path) // 1024 // 1024} MB, {total_written} rows)")
log("Data download complete.")


# ---------------------------------------------------------------------------
# 3. Box PLSS folder ID mapping (CADWR shared folder — no API key needed)
# ---------------------------------------------------------------------------

import time

BOX_ROOT = "https://cadwr.app.box.com/v/WellCompletionReports"
SD_COUNTY_FOLDER_ID = "77346720611"

log("Building Box PLSS folder ID mapping for San Diego County...")

plss_map = {}
for page in range(1, 20):  # safety cap; SD County has 8 pages as of 2025
    url = f"{BOX_ROOT}/folder/{SD_COUNTY_FOLDER_ID}?page={page}"
    req = urllib.request.Request(url, headers={"User-Agent": "water-report-mvp/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode()
    except Exception as e:
        log(f"  Box page {page} fetch failed: {e}")
        break

    import re as _re
    match = _re.search(r"postStreamData\s*=\s*(\{.*?\});", html, _re.S)
    if not match:
        break
    data = json.loads(match.group(1))
    sf = data.get("/app-api/enduserapp/shared-folder", {})
    items = sf.get("items", [])
    page_count = int(sf.get("pageCount", 1))

    for item in items:
        if item.get("type") == "folder":
            plss_map[item["name"]] = item["id"]

    log(f"  Page {page}/{page_count}: {len(items)} items")
    if page >= page_count:
        break
    time.sleep(0.3)

box_path = os.path.join(OUT_DIR, "box_plss_folders.json")
with open(box_path, "w") as f:
    json.dump({"county_folder_id": int(SD_COUNTY_FOLDER_ID), "plss_folders": plss_map}, f, indent=2)
log(f"  Saved {box_path} ({len(plss_map)} PLSS sections)")
