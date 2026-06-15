"""
PDF report generator using fpdf2 (pure Python, no system libs required).
"""

from datetime import date as date_cls
from fpdf import FPDF


# Colour palette
BLUE    = (26, 107, 154)
DARK    = (30, 30, 30)
MID     = (80, 80, 80)
LIGHT   = (130, 130, 130)
BG_GRAY = (248, 249, 250)
BG_WARN = (255, 251, 235)
BORDER  = (224, 224, 224)
RED     = (185, 74, 44)
GREEN   = (22, 101, 52)


class ReportPDF(FPDF):
    def __init__(self, label, apn, lat, lon, report_date):
        super().__init__()
        self.label = label
        self.apn = apn
        self.lat = lat
        self.lon = lon
        self.report_date = report_date
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(auto=True, margin=18)

    def header(self):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*BLUE)
        self.cell(0, 8, "CA Groundwater & Well Report", ln=True)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*LIGHT)
        self.cell(0, 5, "Basin status (Bulletin 118) + OSWCR well records -- San Diego County", ln=True)
        self.ln(2)
        self.set_draw_color(*BLUE)
        self.set_line_width(0.5)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-14)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*LIGHT)
        self.cell(0, 5,
                  "Generated from DWR Bulletin 118 basin boundaries and OSWCR well completion reports. "
                  "Informational only -- not a substitute for a site-specific hydrogeological assessment.",
                  ln=True)
        self.cell(0, 5, f"Page {self.page_no()}", align="R")

    def section_title(self, text):
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*LIGHT)
        txt = text.upper()
        self.cell(0, 5, txt, ln=True)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def kv(self, key, value, indent=0):
        self.set_x(self.l_margin + indent)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*MID)
        self.cell(52, 6, key + ":", ln=False)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*DARK)
        self.multi_cell(0, 6, str(value) if value is not None else "--")

    def stat_box(self, value, label, x, y, w=40, h=20):
        """Draw a small stat card."""
        self.set_fill_color(*BG_GRAY)
        self.set_draw_color(*BORDER)
        self.set_line_width(0.2)
        self.rect(x, y, w, h, style="FD")
        self.set_xy(x, y + 3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*BLUE)
        self.cell(w, 6, str(value), align="C", ln=False)
        self.set_xy(x, y + 10)
        self.set_font("Helvetica", "", 6.5)
        self.set_text_color(*MID)
        self.multi_cell(w, 4, label, align="C")


def generate_pdf(label, apn, lat, lon, radius, basin_ctx, well_data) -> bytes:
    today = date_cls.today().isoformat()
    pdf = ReportPDF(label, apn, lat, lon, today)
    pdf.add_page()

    # --- Parcel header ---
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(*DARK)
    pdf.cell(0, 8, label, ln=True)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MID)
    meta_parts = []
    if apn:
        meta_parts.append(f"APN: {apn}")
    meta_parts.append(f"Location: {lat:.5f}, {lon:.5f}")
    meta_parts.append(f"Report date: {today}")
    pdf.cell(0, 5, "   |  ".join(meta_parts), ln=True)
    pdf.ln(6)

    # --- Basin status ---
    pdf.section_title("Groundwater Basin Status")

    if basin_ctx["in_basin"]:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 6, f"Within: {basin_ctx['basin_name']} (Basin {basin_ctx['basin_id']})", ln=True)
        pdf.ln(1)
        priority = basin_ctx.get("priority") or "--"
        priority_color = RED if priority == "High" else MID
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*priority_color)
        pdf.cell(0, 5, f"SGMA Priority: {priority}", ln=True)
        pdf.set_text_color(*DARK)
        sgma = "Yes" if basin_ctx.get("sgma_managed") else "No"
        pdf.cell(0, 5, f"SGMA Managed: {sgma}", ln=True)
        if basin_ctx.get("gsa_name"):
            pdf.cell(0, 5, f"GSA: {basin_ctx['gsa_name']}", ln=True)
    else:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*DARK)
        pdf.cell(0, 6, "Not within a Bulletin 118 groundwater basin boundary.", ln=True)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MID)
        pdf.multi_cell(
            0, 5,
            "Common for inland/foothill areas of San Diego County where groundwater occurs in "
            "fractured hard-rock formations. SGMA requirements generally do not apply. The relevant "
            "question is what nearby well records suggest about local depth, water level, and yield."
        )

    pdf.ln(6)

    # --- Nearby wells ---
    pdf.section_title(f"Nearby Well Records (within {radius} miles)")

    wcount = well_data["count"]
    if wcount == 0:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(*MID)
        pdf.multi_cell(
            0, 5,
            "No well completion records found within this radius. Consider widening the search."
        )
    else:
        s = well_data["summary"]

        # Stat boxes
        box_y = pdf.get_y()
        box_w = 42
        gap = 4
        boxes = [
            (str(wcount), f"Wells within\n{radius} mi"),
            (f"{int(s['median_depth_ft'])} ft", "Median\ncompleted depth"),
            (f"{int(s['median_static_water_level_ft'])} ft", "Median static\nwater level (BLS)"),
            (
                f"{s['median_yield_gpm']:.1f} gpm" if s['median_yield_gpm'] else "--",
                f"Median yield\n({s['yield_reported_count']}/{wcount} reported)"
            ),
        ]
        x = pdf.l_margin
        for val, lbl in boxes:
            pdf.stat_box(val, lbl, x, box_y, w=box_w, h=22)
            x += box_w + gap

        pdf.set_y(box_y + 26)

        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*MID)
        pdf.cell(0, 5, f"Depth range: {s['depth_range_ft'][0]}-{s['depth_range_ft'][1]} ft", ln=True)

        use_str = "  |  ".join(f"{k}: {v}" for k, v in list(s["use_breakdown"].items())[:6])
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4.5, f"Use types: {use_str}")
        pdf.set_font("Helvetica", "", 8)
        pdf.cell(0, 5, f"Record dates: {s['date_range'][0]} to {s['date_range'][1]}", ln=True)

        pdf.ln(3)
        pdf.set_fill_color(*BG_WARN)
        pdf.set_draw_color(245, 158, 11)
        pdf.set_line_width(0.3)
        pdf.rect(pdf.l_margin, pdf.get_y(), pdf.w - pdf.l_margin - pdf.r_margin, 10, style="FD")
        pdf.set_xy(pdf.l_margin + 2, pdf.get_y() + 1.5)
        pdf.set_font("Helvetica", "I", 7.5)
        pdf.set_text_color(*MID)
        pdf.multi_cell(
            pdf.w - pdf.l_margin - pdf.r_margin - 4, 3.5,
            "Well completion report locations are accurate to ~1 sq. mile (PLSS section), "
            "not an exact address. Figures describe wells in the general area, not necessarily on this parcel."
        )
        pdf.ln(12)

    # --- Summary ---
    pdf.section_title("Summary")
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*DARK)

    if basin_ctx["in_basin"]:
        sgma_txt = "SGMA-managed" if basin_ctx.get("sgma_managed") else "defined Bulletin 118"
        summary = (
            f"This parcel sits within an actively {sgma_txt} basin "
            f"({basin_ctx['basin_name']}, priority: {basin_ctx.get('priority') or '--'}). "
        )
        if basin_ctx.get("sgma_managed"):
            summary += (
                "Consult the SGMA Portal for the applicable Groundwater Sustainability Plan, "
                "allocation limits, and any probationary status for this basin."
            )
        else:
            summary += "This basin is below the SGMA management threshold -- no GSP is required."
    else:
        if wcount >= 8:
            summary = (
                "Multiple wells have been drilled in this general area with recorded depth and yield data, "
                "suggesting groundwater is locally accessible. This is not a guarantee for any specific spot "
                "-- fractured-rock yield is highly localized -- but provides useful context."
            )
        elif wcount > 0:
            summary = (
                f"Relatively few well records ({wcount}) exist within {radius} miles. "
                "This may reflect lower historical development density rather than poor water prospects, "
                "but less local data is available. Consider widening the search or consulting a local driller."
            )
        else:
            summary = (
                f"No well records found within {radius} miles. Consider widening the radius "
                "or consulting a local well driller for site-specific advice."
            )

    pdf.multi_cell(0, 5, summary)

    return pdf.output()
