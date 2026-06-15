"""
Generates matplotlib charts as base64-encoded PNGs for embedding in HTML/PDF.
"""

import base64
import io

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


# Colour palette matching the app's blue/orange scheme
BLUE   = "#1a6b9a"
ORANGE = "#f97316"
GRAY   = "#e5e7eb"
MID    = "#6b7280"
DARK   = "#1f2937"

DEPTH_COLORS = [
    (300,  "#22c55e", "< 300 ft"),
    (600,  "#eab308", "300–600 ft"),
    (1000, "#f97316", "600–1000 ft"),
    (float("inf"), "#ef4444", "> 1000 ft"),
]


def _to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def depth_color(depth):
    for threshold, color, _ in DEPTH_COLORS:
        if depth <= threshold:
            return color
    return "#ef4444"


def depth_histogram(records: list, median_depth: float) -> str:
    """Histogram of TotalCompletedDepth with median line."""
    depths = [r.get("TotalCompletedDepth") for r in records
              if r.get("TotalCompletedDepth") and r["TotalCompletedDepth"] > 0]
    if not depths:
        return ""

    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor="white")

    # Build bins, cap at 99th percentile to avoid long tail squishing
    cap = np.percentile(depths, 99)
    binned = [min(d, cap) for d in depths]
    n_bins = min(30, len(set(int(d // 50) for d in binned)))
    bins = np.linspace(0, cap, max(n_bins, 10) + 1)

    # Colour each bar by depth tier
    counts, edges = np.histogram(binned, bins=bins)
    for i, (count, left, right) in enumerate(zip(counts, edges[:-1], edges[1:])):
        mid = (left + right) / 2
        ax.bar(left, count, width=(right - left) * 0.9,
               color=depth_color(mid), alpha=0.85, align="edge")

    # Median line
    ax.axvline(median_depth, color=DARK, linewidth=1.5, linestyle="--")
    ax.text(median_depth + cap * 0.01, ax.get_ylim()[1] * 0.92,
            f"median\n{int(median_depth)} ft", fontsize=7.5, color=DARK,
            va="top", fontweight="bold")

    ax.set_xlabel("Completed depth (ft)", fontsize=8.5, color=MID)
    ax.set_ylabel("Number of wells", fontsize=8.5, color=MID)
    ax.set_title("Well Depth Distribution — Nearby Wells", fontsize=9.5,
                 color=DARK, fontweight="bold", pad=8)
    ax.tick_params(labelsize=8, colors=MID)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRAY)
    ax.set_facecolor("white")
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))

    # Legend
    patches = [mpatches.Patch(color=c, label=l) for _, c, l in DEPTH_COLORS]
    ax.legend(handles=patches, fontsize=7, loc="upper right",
              framealpha=0.8, edgecolor=GRAY)

    fig.tight_layout()
    return _to_b64(fig)


def drilling_timeline(records: list) -> str:
    """Bar chart of wells drilled per decade."""
    from collections import Counter
    import re

    decades = []
    for r in records:
        raw = str(r.get("DateWorkEnded") or "")
        m = re.match(r"(\d{4})", raw)
        if m:
            yr = int(m.group(1))
            if 1900 < yr <= 2030:
                decades.append((yr // 10) * 10)

    if not decades:
        return ""

    counts = Counter(decades)
    sorted_decades = sorted(counts)
    labels = [f"{d}s" for d in sorted_decades]
    values = [counts[d] for d in sorted_decades]

    fig, ax = plt.subplots(figsize=(6.5, 2.8), facecolor="white")
    bars = ax.bar(labels, values, color=BLUE, alpha=0.8, width=0.6)

    # Label bars
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                str(val), ha="center", va="bottom", fontsize=7.5, color=DARK)

    ax.set_xlabel("Decade", fontsize=8.5, color=MID)
    ax.set_ylabel("Wells drilled", fontsize=8.5, color=MID)
    ax.set_title("Drilling Activity by Decade — Nearby Wells", fontsize=9.5,
                 color=DARK, fontweight="bold", pad=8)
    ax.tick_params(labelsize=8, colors=MID)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRAY)
    ax.set_facecolor("white")
    ax.yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))
    ax.set_ylim(0, max(values) * 1.18)

    fig.tight_layout()
    return _to_b64(fig)


def use_breakdown_chart(use_breakdown: dict) -> str:
    """Horizontal bar chart of well use types."""
    if not use_breakdown:
        return ""

    # Shorten labels
    SHORT = {
        "Water Supply Irrigation - Agriculture": "Irrigation (Ag)",
        "Water Supply Irrigation - Landscape": "Irrigation (Landscape)",
        "Water Supply Domestic": "Domestic",
        "Water Supply Public": "Public Supply",
        "Water Supply Unknown": "Unknown",
        "Water Supply Stock or Animal Watering": "Stock/Animal",
        "Water Supply Industrial": "Industrial",
        "Monitoring": "Monitoring",
        "Test Well": "Test Well",
        "Other": "Other",
    }

    items = sorted(use_breakdown.items(), key=lambda x: x[1], reverse=True)[:8]
    labels = [SHORT.get(k, k[:30]) for k, _ in items]
    values = [v for _, v in items]

    fig, ax = plt.subplots(figsize=(6.5, max(2.2, len(labels) * 0.38)),
                           facecolor="white")
    colors = [BLUE if i == 0 else "#93c5fd" for i in range(len(labels))]
    bars = ax.barh(labels[::-1], values[::-1], color=colors[::-1], alpha=0.85)

    for bar, val in zip(bars, values[::-1]):
        ax.text(bar.get_width() + 0.15, bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=7.5, color=DARK)

    ax.set_xlabel("Number of wells", fontsize=8.5, color=MID)
    ax.set_title("Well Use Breakdown — Nearby Wells", fontsize=9.5,
                 color=DARK, fontweight="bold", pad=8)
    ax.tick_params(labelsize=8, colors=MID)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRAY)
    ax.set_facecolor("white")
    ax.set_xlim(0, max(values) * 1.2)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(integer=True))

    fig.tight_layout()
    return _to_b64(fig)


def well_map_data(records: list) -> list:
    """Slim well records for Leaflet map (lat, lon, depth, use, wcr)."""
    out = []
    for r in records:
        lat = r.get("DecimalLatitude")
        lon = r.get("DecimalLongitude")
        if not lat or not lon:
            continue
        depth = r.get("TotalCompletedDepth")
        out.append({
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "depth": int(depth) if depth and not isinstance(depth, float) or depth == depth else None,
            "use": r.get("PlannedUseFormerUse") or "Unknown",
            "wcr": r.get("WCRNumber") or "",
            "color": depth_color(float(depth)) if depth and str(depth) != "nan" else "#9ca3af",
        })
    return out
