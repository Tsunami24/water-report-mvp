"""
Assembles the basin context + nearby well summary into a markdown report.

This is the v1 report shape. Sections present themselves differently
depending on whether the parcel is inside a Bulletin 118/SGMA basin or not -
see the basin-vs-non-basin branch.
"""

from datetime import date
from src.basin import load_basins, get_basin_context
from src.wells import load_wells, get_nearby_wells


def generate_report(
    label: str,
    apn: str,
    lat: float,
    lon: float,
    basins_path: str,
    wells_path: str,
    radius_miles: float = 1.5,
) -> str:
    basins = load_basins(basins_path)
    wells = load_wells(wells_path)

    basin_ctx = get_basin_context(lat, lon, basins)
    well_data = get_nearby_wells(lat, lon, wells, radius_miles=radius_miles)

    lines = []
    lines.append(f"# Groundwater & Well Report")
    lines.append("")
    lines.append(f"**Parcel:** {label} (APN: {apn})")
    lines.append(f"**Location:** {lat}, {lon}")
    lines.append(f"**Report date:** {date.today().isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Basin / regulatory context -----------------------------------
    lines.append("## Groundwater Basin Status")
    lines.append("")
    if basin_ctx["in_basin"]:
        lines.append(f"This parcel is located within the **{basin_ctx['basin_name']}** "
                      f"(Basin ID: {basin_ctx['basin_id']}).")
        lines.append("")
        lines.append(f"- **SGMA Priority:** {basin_ctx['priority']}")
        lines.append(f"- **Managed under SGMA:** {'Yes' if basin_ctx['sgma_managed'] else 'No'}")
        lines.append(f"- **Groundwater Sustainability Agency (GSA):** {basin_ctx['gsa_name']}")
        lines.append("")
        lines.append("_TODO (real data): pull GSP status, allocation/pumping "
                      "restriction trends, and probationary status for this "
                      "basin from the SGMA Portal._")
    else:
        lines.append("This parcel does **not** fall within a defined Bulletin 118 "
                      "groundwater basin boundary.")
        lines.append("")
        lines.append("This is common for inland/foothill areas of San Diego County, "
                      "where groundwater occurs in fractured hard-rock formations "
                      "rather than alluvial basins. SGMA reporting and allocation "
                      "requirements generally do not apply here. The relevant "
                      "question for this kind of parcel is less about regulatory "
                      "compliance and more about **what nearby wells suggest about "
                      "drilling depth, water level, and yield in this area.**")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Nearby wells ----------------------------------------------------
    lines.append(f"## Nearby Well Records (within {well_data['radius_miles']} miles)")
    lines.append("")
    lines.append("_Note: well completion report locations are typically accurate to "
                  "the surrounding ~1 square mile (PLSS section), not an exact "
                  "address. The figures below describe wells reported in this "
                  "general area, not necessarily on this specific parcel._")
    lines.append("")

    if well_data["count"] == 0:
        lines.append("No well completion records were found within this radius. "
                      "This may mean genuinely sparse drilling history in this "
                      "area, or gaps in the historical OSWCR dataset (older "
                      "records are less complete). Consider widening the search "
                      "radius.")
    else:
        s = well_data["summary"]
        lines.append(f"- **Wells found:** {well_data['count']}")
        lines.append(f"- **Reported depth range:** {s['depth_range_ft'][0]}–{s['depth_range_ft'][1]} ft "
                      f"(median {s['median_depth_ft']:.0f} ft)")
        lines.append(f"- **Median static water level:** {s['median_static_water_level_ft']:.0f} ft below surface")
        if s["median_yield_gpm"] is not None:
            lines.append(f"- **Reported yield:** {s['yield_reported_count']} of {well_data['count']} wells "
                          f"report a yield figure; median {s['median_yield_gpm']:.1f} gpm")
        else:
            lines.append(f"- **Reported yield:** no yield figures reported for wells in this area "
                          f"(common in older records)")
        lines.append(f"- **Well use breakdown:** "
                      f"{', '.join(f'{k}: {v}' for k, v in s['use_breakdown'].items())}")
        lines.append(f"- **Record dates range from** {s['date_range'][0]} to {s['date_range'][1]}")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Summary")
    lines.append("")

    if basin_ctx["in_basin"]:
        lines.append("This parcel sits within an actively SGMA-managed basin. "
                      "_TODO (real data):_ a one-line flag here once GSP "
                      "allocation/trend data is wired in - e.g. 'stable', "
                      "'declining - allocation cuts phased through 2030', etc.")
    else:
        if well_data["count"] >= 8:
            lines.append("Multiple wells have been drilled in this general area "
                          "with reasonably consistent depth/yield characteristics, "
                          "suggesting groundwater is locally accessible. This is "
                          "**not a guarantee** for any specific spot on the "
                          "parcel - fractured-rock yield is highly localized - "
                          "but it provides useful context on what to expect.")
        else:
            lines.append("Relatively few well records exist in this immediate area. "
                          "This may simply reflect lower historical development "
                          "density rather than poor water prospects, but it means "
                          "less local data is available to inform expectations.")

    lines.append("")
    lines.append("_This report is generated from publicly available state "
                  "well-completion and groundwater basin data. It is "
                  "informational only and is not a substitute for a site-specific "
                  "hydrogeological assessment._")

    return "\n".join(lines)


if __name__ == "__main__":
    import os
    os.makedirs("output", exist_ok=True)

    test_cases = [
        ("Escondido-area test parcel (in-basin)", "TEST-APN-001", 33.090, -117.040, "output/report_inbasin.md"),
        ("Valley Center test parcel (non-basin)", "TEST-APN-002", 33.220, -117.030, "output/report_nonbasin.md"),
    ]

    for label, apn, lat, lon, outfile in test_cases:
        report = generate_report(
            label, apn, lat, lon,
            basins_path="data/sample/basin_boundaries.geojson",
            wells_path="data/sample/well_completion_reports.csv",
        )
        with open(outfile, "w") as f:
            f.write(report)
        print(f"Wrote {outfile}")
