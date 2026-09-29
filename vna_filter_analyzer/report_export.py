"""Professional PDF engineering report generator using ReportLab."""

import os
import tempfile
from datetime import datetime
from typing import List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from .data_model import MeasurementData
from .comparison import compare_measurements, calculate_differences, generate_dgs_summary
from .units import format_frequency, format_bandwidth, format_db, format_percentage
from .graph_export import export_figure


def generate_pdf_report(
    measurements: List[MeasurementData],
    file_path: str,
    active_param: str = "S21",
    notes: str = "",
) -> str:
    """Generate a comprehensive multi-page engineering PDF measurement report."""
    valid = [m for m in measurements if m.metrics is not None]
    if not valid:
        raise ValueError("No analyzed measurements available to generate a report.")

    primary = valid[0]

    # Generate a temporary high-res PNG for embedding into the PDF
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
        temp_img_path = tmp_img.name

    try:
        export_figure(
            measurements=valid,
            file_path=temp_img_path,
            active_param=active_param,
            normalized=False,
            show_markers=True,
            primary_idx=0,
            dpi=220,
            title=f"Measured {active_param} Filter Response",
        )

        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#1a252f"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#7f8c8d"),
            spaceAfter=14,
        )
        h2_style = ParagraphStyle(
            "H2Style",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#2980b9"),
            spaceBefore=12,
            spaceAfter=6,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#2c3e50"),
        )
        note_style = ParagraphStyle(
            "Note",
            parent=styles["Italic"],
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#555555"),
        )

        elements = []

        # 1. Header Banner
        elements.append(Paragraph("Rohde & Schwarz VNA Filter Analysis Report", title_style))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elements.append(Paragraph(f"Generated on: {timestamp} | Primary File: {primary.name}", subtitle_style))

        # 2. Measurement Information Card
        elements.append(Paragraph("1. Measurement Information", h2_style))
        meta_rows = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Value</b>", body_style)],
            ["VNA Instrument", primary.metadata.get("VNA Model", "Rohde & Schwarz Vector Network Analyzer")],
            ["Active Sweep Points", str(primary.num_points)],
            ["Frequency Range", f"{format_frequency(primary.freq_range_hz[0])} to {format_frequency(primary.freq_range_hz[1])}"],
            ["Measured Parameter", active_param],
            ["Source File", os.path.basename(primary.file_path) if primary.file_path else primary.name],
        ]
        if "IFBW" in primary.metadata:
            meta_rows.append(["IF Bandwidth", primary.metadata["IFBW"]])
        if "Power" in primary.metadata:
            meta_rows.append(["Test Power Level", primary.metadata["Power"]])

        meta_table = Table(meta_rows, colWidths=[2.2 * inch, 4.8 * inch])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ecf0f1")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(meta_table)
        elements.append(Spacer(1, 10))

        # 3. Filter Response Graph
        elements.append(Paragraph("2. Interactive Frequency Response Plot", h2_style))
        elements.append(Image(temp_img_path, width=7.0 * inch, height=4.2 * inch))
        elements.append(Spacer(1, 10))

        # 4. Filter Characteristics Table
        elements.append(Paragraph("3. Primary Filter Characterization", h2_style))
        met = primary.metrics
        metrics_rows = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Calculated Value</b>", body_style), Paragraph("<b>Description / Formula</b>", body_style)],
            ["Center Frequency (Fc)", format_frequency(met.center_freq_hz), "Frequency at maximum transmission peak"],
            ["Peak S21", format_db(met.peak_s21_db), "Maximum transmission magnitude"],
            ["Insertion Loss (IL)", format_db(met.insertion_loss_db), "-Peak S21 (magnitude of attenuation)"],
            [f"Lower Cutoff (fL, -{met.bw_threshold_db:g}dB)", format_frequency(met.f_lower_hz), "Interpolated lower threshold crossing"],
            [f"Upper Cutoff (fH, -{met.bw_threshold_db:g}dB)", format_frequency(met.f_upper_hz), "Interpolated upper threshold crossing"],
            [f"Bandwidth (BW, -{met.bw_threshold_db:g}dB)", format_bandwidth(met.bandwidth_hz), "fH - fL"],
            ["Fractional Bandwidth (FBW)", format_percentage(met.fractional_bw_pct), "(BW / Fc) × 100%"],
            ["Loaded Q Factor", f"{met.loaded_q:.2f}", "Fc / BW (-3 dB bandwidth)"],
            ["Passband Ripple", format_db(met.passband_ripple_db) if met.passband_ripple_db is not None else "N/A", "Peak-to-peak variation inside passband"],
            ["Min In-Band S11", format_db(met.min_s11_db) if met.min_s11_db is not None else "N/A", "Best return loss reflection point"],
            ["Return Loss (RL)", format_db(met.return_loss_db) if met.return_loss_db is not None else "N/A", "-Min(S11) in positive dB convention"],
            ["VSWR @ Fc", f"{met.vswr_at_fc:.2f}" if met.vswr_at_fc is not None else "N/A", "(1 + |Γ|) / (1 - |Γ|) at center frequency"],
        ]
        met_table = Table(metrics_rows, colWidths=[2.2 * inch, 1.8 * inch, 3.0 * inch])
        met_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2980b9")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ]))
        elements.append(met_table)
        elements.append(Spacer(1, 10))

        # 5. Multi-Measurement Comparison (if >= 2 valid)
        if len(valid) >= 2:
            elements.append(Paragraph("4. Multi-Measurement Comparison", h2_style))
            comp_rows, comp_df = compare_measurements(valid)
            table_headers = [Paragraph("<b>Parameter</b>", body_style)] + [Paragraph(f"<b>{m.name}</b>", body_style) for m in valid]
            c_data = [table_headers]
            for row in comp_rows[:12]:  # Top 12 metrics
                c_data.append([row.parameter] + [row.values.get(m.name, "N/A") for m in valid])

            col_w = 7.0 / len(c_data[0]) * inch
            c_table = Table(c_data, colWidths=[col_w] * len(c_data[0]))
            c_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            elements.append(c_table)
            elements.append(Spacer(1, 10))

            # DGS summary section
            dgs_text = generate_dgs_summary(valid)
            if dgs_text:
                elements.append(Paragraph("<b>DGS Comparative Summary:</b>", body_style))
                for line in dgs_text.splitlines():
                    if line.startswith("- "):
                        elements.append(Paragraph(f"• {line[2:]}", body_style))
                elements.append(Spacer(1, 8))

        # 6. Engineering Notes
        if notes:
            elements.append(Paragraph("5. Engineering Notes & Observations", h2_style))
            elements.append(Paragraph(notes.replace("\n", "<br/>"), body_style))
            elements.append(Spacer(1, 10))

        # 7. Disclaimer
        elements.append(KeepTogether([
            Spacer(1, 12),
            Paragraph(
                "<b>Engineering Notice & Disclaimer:</b> Reported values are derived from imported VNA measurement "
                "data via linear/spline interpolation. S-parameter parameters, Loaded Q, and cutoff boundaries are "
                "calculated metrics and should be verified with calibrated laboratory reference standards.",
                note_style,
            )
        ]))

        doc.build(elements)
    finally:
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

    return file_path
