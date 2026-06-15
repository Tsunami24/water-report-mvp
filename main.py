"""
CLI entry point.

Usage:
    python3 main.py --label "My Parcel" --apn "188-040-12-00" \
        --lat 33.220 --lon -117.030 \
        --basins data/real/basin_boundaries.geojson \
        --wells data/real/well_completion_reports.csv \
        --out output/my_report.md

Defaults to the synthetic sample data in data/sample/ if --basins/--wells
are not provided, so you can sanity-check the pipeline before plugging in
real data.
"""

import argparse
import os

from src.report import generate_report


def main():
    parser = argparse.ArgumentParser(description="Generate a groundwater/well report for a parcel.")
    parser.add_argument("--label", required=True, help="Human-readable parcel label")
    parser.add_argument("--apn", required=True, help="Assessor's Parcel Number")
    parser.add_argument("--lat", required=True, type=float, help="Latitude")
    parser.add_argument("--lon", required=True, type=float, help="Longitude")
    parser.add_argument("--basins", default="data/sample/basin_boundaries.geojson",
                         help="Path to basin boundaries GeoJSON")
    parser.add_argument("--wells", default="data/sample/well_completion_reports.csv",
                         help="Path to well completion reports CSV")
    parser.add_argument("--radius", default=1.5, type=float, help="Search radius in miles for nearby wells")
    parser.add_argument("--out", default=None, help="Output markdown file path (prints to stdout if omitted)")

    args = parser.parse_args()

    report = generate_report(
        label=args.label,
        apn=args.apn,
        lat=args.lat,
        lon=args.lon,
        basins_path=args.basins,
        wells_path=args.wells,
        radius_miles=args.radius,
    )

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w") as f:
            f.write(report)
        print(f"Wrote report to {args.out}")
    else:
        print(report)


if __name__ == "__main__":
    main()
