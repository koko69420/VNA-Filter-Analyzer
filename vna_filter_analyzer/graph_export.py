"""Graph export utility producing high-resolution PNG, SVG, and vector PDF figures."""

from typing import List, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend for rendering
import matplotlib.pyplot as plt
import numpy as np

from .data_model import MeasurementData
from .units import format_frequency, format_bandwidth


def export_figure(
    measurements: List[MeasurementData],
    file_path: str,
    active_param: str = "S21",
    normalized: bool = False,
    show_markers: bool = True,
    primary_idx: int = 0,
    dpi: int = 300,
    title: Optional[str] = None,
) -> str:
    """Render and export publication-ready figure of VNA measurement responses.

    Args:
        measurements: List of MeasurementData to include.
        file_path: Output file path (.png, .svg, .pdf).
        active_param: S-parameter to plot ('S21', 'S11', etc.).
        normalized: Whether to shift curve peak to 0 dB.
        show_markers: Whether to render Fc, fL, fH and -3 dB markers.
        primary_idx: Index of primary filter to annotate markers for.
        dpi: DPI resolution for raster export.
        title: Custom title string.

    Returns:
        Absolute path to exported file.
    """
    valid = [m for m in measurements if m.visible and active_param in m.clean_s_params]
    if not valid:
        raise ValueError("No visible measurements with the requested S-parameter.")

    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, ax = plt.subplots(figsize=(10, 6), dpi=dpi)

    # Determine frequency scale (GHz or MHz)
    max_freq = max(float(m.clean_freq_hz[-1]) for m in valid)
    freq_scale = 1e9 if max_freq >= 1e8 else 1e6
    freq_unit_str = "GHz" if freq_scale == 1e9 else "MHz"

    primary_m = valid[primary_idx % len(valid)]

    for m in valid:
        x = m.clean_freq_hz / freq_scale
        y = np.copy(m.clean_s_params[active_param])
        if normalized:
            y -= np.max(y)

        label = m.name if not normalized else f"{m.name} (Norm 0 dB)"
        ax.plot(x, y, label=label, color=m.color, linewidth=1.8, linestyle="-" if m.line_style == "solid" else "--")

        # Also show smoothed trace if mode is 'Both'
        if m.display_mode == "Both" and active_param in m.smoothed_s_params:
            y_smooth = np.copy(m.smoothed_s_params[active_param])
            if normalized:
                y_smooth -= np.max(y_smooth)
            ax.plot(x, y_smooth, label=f"{m.name} (Smoothed)", color=m.color, linewidth=1.2, linestyle=":")

    # Annotate markers for primary filter
    if show_markers and primary_m.metrics is not None and active_param in ("S21", "S12"):
        met = primary_m.metrics
        fc = met.center_freq_hz / freq_scale
        fl = met.f_lower_hz / freq_scale
        fh = met.f_upper_hz / freq_scale
        peak_y = met.peak_s21_db if not normalized else 0.0
        ref_3db_y = peak_y - met.bw_threshold_db

        # Shaded bandwidth area
        ax.axvspan(fl, fh, color="#3498db", alpha=0.15, label=f"-{met.bw_threshold_db:g}dB BW ({format_bandwidth(met.bandwidth_hz)})")

        # Center frequency vertical line
        ax.axvline(fc, color="#e74c3c", linestyle="--", linewidth=1.3, label=f"Fc = {format_frequency(met.center_freq_hz)}")
        # Cutoff vertical lines
        ax.axvline(fl, color="#2ecc71", linestyle=":", linewidth=1.2, label=f"fL = {format_frequency(met.f_lower_hz)}")
        ax.axvline(fh, color="#9b59b6", linestyle=":", linewidth=1.2, label=f"fH = {format_frequency(met.f_upper_hz)}")

        # -3 dB reference horizontal line
        ax.axhline(ref_3db_y, color="#7f8c8d", linestyle="-.", linewidth=1.0, alpha=0.8)

        # Peak marker point
        ax.plot([fc], [peak_y], marker="o", markersize=6, color="#e74c3c")

    default_title = f"VNA Measurement - {active_param} Transmission Response"
    if normalized:
        default_title += " (Normalized)"
    ax.set_title(title or default_title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(f"Frequency ({freq_unit_str})", fontsize=11, labelpad=8)
    ax.set_ylabel(f"{active_param} Magnitude (dB)", fontsize=11, labelpad=8)

    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
    ax.legend(loc="best", frameon=True, framealpha=0.9, fontsize=9)

    plt.tight_layout()
    fig.savefig(file_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    return file_path
