# Groundwater & Well Report - MVP

A pipeline that generates a per-parcel groundwater/well report from public
California data: is this parcel in a Bulletin 118 / SGMA-managed basin, and
what do nearby well completion records suggest about depth, water level, and
yield in the area.

## Status

The pipeline logic (basin point-in-polygon matching, nearby-well filtering
and stats, report assembly) is built and tested against **synthetic data**
in `data/sample/`. The synthetic data mimics the real datasets' structure
closely enough to validate the logic, but the actual basin shapes and well
records are made up.

**This sandbox cannot reach California's open data portals** (data.ca.gov,
water.ca.gov, gis.sandiegocounty.gov etc. all return `host_not_allowed`).
The next step is to run the data-download steps below somewhere with normal
internet access (your own machine, or Claude Code locally), drop the real
files into `data/real/`, and point `main.py` at them.

## Quick start (with synthetic data)

```bash
pip3 install --break-system-packages geopandas shapely pandas

# Regenerate synthetic test data (optional, already included)
python3 data/sample/generate_synthetic_wells.py

# Run the pipeline against the synthetic data
python3 main.py --label "Valley Center test" --apn "TEST-001" \
    --lat 33.220 --lon -117.030 --out output/test.md
```

## Plugging in real data

### 1. Bulletin 118 basin boundaries -> `data/real/basin_boundaries.geojson`

Source: DWR's SGMA Data Viewer / California Natural Resources Agency open
data portal. Search for "Bulletin 118 Groundwater Basin Boundaries" -
typically available as a downloadable GeoJSON or shapefile (515 basins
statewide).

The pipeline expects these properties per feature (rename/remap as needed in
`src/basin.py`):
- `basin_id`
- `basin_name`
- `priority` (High / Medium / Low / Very Low, from SGMA Basin Prioritization)
- `sgma_managed` (true for High/Medium priority basins)
- `gsa_name`

The SGMA Basin Prioritization dataset (separate from the boundary shapes) is
where `priority` comes from - you'll likely need to join two datasets on
`basin_id`.

**First thing to check for Valley Center specifically:** load the real basin
boundaries and test whether Valley Center-area coordinates fall inside ANY
basin polygon. If not, that confirms the "non-basin / hard-rock" framing for
that area, which the report already handles as a distinct case.

### 2. Well Completion Reports -> `data/real/well_completion_reports.csv`

Source: data.ca.gov / data.cnra.ca.gov, dataset "Well Completion Reports"
(OSWCR index), ~293k records statewide including San Diego County.

Expected columns (rename/remap in `src/wells.py` if the real download uses
different names):
- `WCRNumber`
- `County`
- `DecimalLatitude`, `DecimalLongitude`
- `PlannedUseFormerUse`
- `TotalCompletedDepth`
- `StaticWaterLevel`
- `WellYield` (often missing - that's expected and handled)
- `DateWorkEnded`

Recommended: filter to `County == "San Diego"` (or whatever counties you're
targeting) before saving to `data/real/`, since the full statewide file is
large.

**Known data quality issue to validate immediately:** real OSWCR coordinates
are often only accurate to the center of the 1x1 mile PLSS section. Once you
load real data for the Valley Center area, check how many distinct
lat/lon pairs actually exist nearby - if many wells share identical
coordinates (because they're all snapped to the same section center), the
"nearby wells" radius search will behave more like "wells in this section"
than "wells within N miles", and the report copy should reflect that.

### 3. Groundwater level trends (not yet wired in)

Source: DWR Water Data Library / Enterprise Monitoring Well Network
(has a queryable API). Not yet implemented - lower priority for non-basin
parcels since monitoring wells are sparser outside basins. Worth adding once
the basin-side report (in-basin case) is the focus.

### 4. SGMA / GSP status detail (not yet wired in)

Source: SGMA Portal / SGMA Data Viewer, for in-basin parcels only. Currently
a TODO placeholder in the report output.

## Project structure

```
water-report-mvp/
├── main.py                  # CLI entry point
├── src/
│   ├── basin.py             # basin point-in-polygon lookup
│   ├── wells.py             # nearby well filtering + stats
│   └── report.py            # assembles report markdown
├── data/
│   ├── sample/               # synthetic test data (included)
│   └── real/                  # <- put real downloaded data here
└── output/                    # generated reports land here
```

## Next steps

1. Run the data-download steps above with real internet access.
2. Re-test `src/basin.py` and `src/wells.py` against real data for a known
   Valley Center APN - sanity-check against ground truth you already know.
3. Resolve the "is Valley Center in a basin or not" question definitively -
   this determines which report framing applies to your own land and to
   most of the immediate target area.
4. Once a real sample report looks right, that's the artifact to bring to
   an ag land broker conversation.
