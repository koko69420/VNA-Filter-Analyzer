"""Comparison and difference analysis across multiple VNA filter measurements."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd

from .data_model import MeasurementData, FilterMetrics
from .units import format_frequency, format_bandwidth, format_db, format_percentage


@dataclass
class ComparisonRow:
    """A row in the comparison metrics table."""
    parameter: str
    unit: str
    values: Dict[str, str]  # filter_name -> formatted string


@dataclass
class DifferenceMetrics:
    """Quantitative differences between a test filter and a baseline filter."""
    baseline_name: str
    test_name: str
    delta_fc_hz: float
    delta_bw_hz: float
    bw_pct_change: float
    delta_il_db: float  # baseline_IL - test_IL (positive means test has LOWER insertion loss = improvement)
    delta_rl_db: Optional[float] = None
    delta_fbw_pct: float = 0.0
    delta_q: float = 0.0
    narrative_summary: List[str] = field(default_factory=list)


def compare_measurements(
    measurements: List[MeasurementData],
) -> Tuple[List[ComparisonRow], pd.DataFrame]:
    """Build a side-by-side comparison table of all filter metrics.

    Returns:
        Tuple of (List of ComparisonRow, pandas DataFrame of comparison)
    """
    valid_items = [m for m in measurements if m.metrics is not None]
    if not valid_items:
        return [], pd.DataFrame()

    headers = ["Parameter", "Unit"] + [m.name for m in valid_items]

    rows_def = [
        ("Center Frequency (Fc)", "GHz/MHz", lambda m: format_frequency(m.metrics.center_freq_hz)),
        ("Peak S21", "dB", lambda m: format_db(m.metrics.peak_s21_db)),
        ("Insertion Loss", "dB", lambda m: format_db(m.metrics.insertion_loss_db)),
        ("Lower Cutoff (fL)", "GHz/MHz", lambda m: format_frequency(m.metrics.f_lower_hz)),
        ("Upper Cutoff (fH)", "GHz/MHz", lambda m: format_frequency(m.metrics.f_upper_hz)),
        ("Bandwidth (BW)", "MHz/GHz", lambda m: format_bandwidth(m.metrics.bandwidth_hz)),
        ("Fractional Bandwidth (FBW)", "%", lambda m: format_percentage(m.metrics.fractional_bw_pct)),
        ("Loaded Q (Fc / BW)", "-", lambda m: f"{m.metrics.loaded_q:.2f}" if m.metrics.loaded_q else "N/A"),
        ("Passband Ripple", "dB", lambda m: format_db(m.metrics.passband_ripple_db) if m.metrics.passband_ripple_db is not None else "N/A"),
        ("Min In-Band S11", "dB", lambda m: format_db(m.metrics.min_s11_db) if m.metrics.min_s11_db is not None else "N/A"),
        ("Return Loss (RL)", "dB", lambda m: format_db(m.metrics.return_loss_db) if m.metrics.return_loss_db is not None else "N/A"),
        ("VSWR @ Fc", "-", lambda m: f"{m.metrics.vswr_at_fc:.2f}" if m.metrics.vswr_at_fc is not None else "N/A"),
        ("Min VSWR in Passband", "-", lambda m: f"{m.metrics.min_vswr:.2f}" if m.metrics.min_vswr is not None else "N/A"),
        ("Lower Stopband Atten.", "dB", lambda m: format_db(m.metrics.lower_stopband_atten_db) if m.metrics.lower_stopband_atten_db is not None else "N/A"),
        ("Upper Stopband Atten.", "dB", lambda m: format_db(m.metrics.upper_stopband_atten_db) if m.metrics.upper_stopband_atten_db is not None else "N/A"),
        ("Lower Skirt Roll-off", "dB/GHz", lambda m: f"{m.metrics.lower_transition_slope_db_per_ghz:.1f} dB/GHz" if m.metrics.lower_transition_slope_db_per_ghz is not None else "N/A"),
        ("Upper Skirt Roll-off", "dB/GHz", lambda m: f"{m.metrics.upper_transition_slope_db_per_ghz:.1f} dB/GHz" if m.metrics.upper_transition_slope_db_per_ghz is not None else "N/A"),
    ]

    comparison_rows: List[ComparisonRow] = []
    df_dict: Dict[str, List[str]] = {"Parameter": [], "Unit": []}
    for m in valid_items:
        df_dict[m.name] = []

    for param_name, unit_str, extractor in rows_def:
        val_map = {}
        df_dict["Parameter"].append(param_name)
        df_dict["Unit"].append(unit_str)

        for m in valid_items:
            val_str = extractor(m)
            val_map[m.name] = val_str
            df_dict[m.name].append(val_str)

        comparison_rows.append(ComparisonRow(parameter=param_name, unit=unit_str, values=val_map))

    df = pd.DataFrame(df_dict)
    return comparison_rows, df


def calculate_differences(
    baseline: MeasurementData,
    test: MeasurementData,
) -> Optional[DifferenceMetrics]:
    """Calculate measured performance differences between test filter and baseline filter."""
    if baseline.metrics is None or test.metrics is None:
        return None

    b = baseline.metrics
    t = test.metrics

    delta_fc = t.center_freq_hz - b.center_freq_hz
    delta_bw = t.bandwidth_hz - b.bandwidth_hz
    bw_pct_change = (delta_bw / b.bandwidth_hz * 100.0) if b.bandwidth_hz > 0 else 0.0

    # Insertion loss improvement: positive when test has lower IL than baseline
    delta_il = b.insertion_loss_db - t.insertion_loss_db

    delta_rl = None
    if b.return_loss_db is not None and t.return_loss_db is not None:
        delta_rl = t.return_loss_db - b.return_loss_db

    delta_fbw = t.fractional_bw_pct - b.fractional_bw_pct
    delta_q = t.loaded_q - b.loaded_q

    # Generate engineering narrative
    narratives = []

    # Frequency shift
    if abs(delta_fc) >= 1e6:
        shift_dir = "higher" if delta_fc > 0 else "lower"
        narratives.append(
            f"Measured center frequency shift: {format_frequency(abs(delta_fc))} {shift_dir} "
            f"({format_frequency(b.center_freq_hz)} → {format_frequency(t.center_freq_hz)})."
        )
    else:
        narratives.append(f"Measured center frequency is nearly identical (shift < 1 MHz).")

    # Insertion Loss
    if abs(delta_il) >= 0.05:
        if delta_il > 0:
            narratives.append(
                f"Measured insertion loss improvement: {delta_il:.2f} dB "
                f"({test.name} has {t.insertion_loss_db:.2f} dB vs. {baseline.name} {b.insertion_loss_db:.2f} dB)."
            )
        else:
            narratives.append(
                f"Measured insertion loss increase: {abs(delta_il):.2f} dB "
                f"({test.name} has {t.insertion_loss_db:.2f} dB vs. {baseline.name} {b.insertion_loss_db:.2f} dB)."
            )

    # Bandwidth
    if abs(delta_bw) >= 1e5:
        bw_dir = "wider" if delta_bw > 0 else "narrower"
        narratives.append(
            f"Measured bandwidth: {format_bandwidth(abs(delta_bw))} {bw_dir} "
            f"({bw_pct_change:+.1f}% change, {format_bandwidth(b.bandwidth_hz)} → {format_bandwidth(t.bandwidth_hz)})."
        )

    # Fractional Bandwidth
    if abs(delta_fbw) >= 0.1:
        narratives.append(
            f"Measured fractional bandwidth difference: {delta_fbw:+.2f}% "
            f"({b.fractional_bw_pct:.2f}% → {t.fractional_bw_pct:.2f}%)."
        )

    # Return Loss
    if delta_rl is not None and abs(delta_rl) >= 0.5:
        rl_dir = "improved" if delta_rl > 0 else "degraded"
        narratives.append(
            f"Measured return loss {rl_dir} by {abs(delta_rl):.2f} dB "
            f"({b.return_loss_db:.1f} dB → {t.return_loss_db:.1f} dB)."
        )

    # Loaded Q
    if abs(delta_q) >= 0.2:
        narratives.append(f"Loaded Q factor changed by {delta_q:+.2f} ({b.loaded_q:.2f} → {t.loaded_q:.2f}).")

    return DifferenceMetrics(
        baseline_name=baseline.name,
        test_name=test.name,
        delta_fc_hz=delta_fc,
        delta_bw_hz=delta_bw,
        bw_pct_change=bw_pct_change,
        delta_il_db=delta_il,
        delta_rl_db=delta_rl,
        delta_fbw_pct=delta_fbw,
        delta_q=delta_q,
        narrative_summary=narratives,
    )


def generate_dgs_summary(measurements: List[MeasurementData]) -> Optional[str]:
    """Automatically detect DGS vs Non-DGS pair and create an engineering report summary."""
    dgs_m = None
    wodgs_m = None

    for m in measurements:
        name_lower = m.name.lower()
        if "without" in name_lower or "no dgs" in name_lower or "wodgs" in name_lower or "non-dgs" in name_lower:
            wodgs_m = m
        elif "dgs" in name_lower:
            dgs_m = m

    # Fallback to first two measurements if not named with DGS
    if (dgs_m is None or wodgs_m is None) and len(measurements) >= 2:
        wodgs_m = measurements[0]
        dgs_m = measurements[1]

    if dgs_m is None or wodgs_m is None or dgs_m.metrics is None or wodgs_m.metrics is None:
        return None

    diff = calculate_differences(baseline=wodgs_m, test=dgs_m)
    if diff is None:
        return None

    lines = [
        f"### DGS vs. Non-DGS Measured Performance Analysis",
        f"**Baseline:** {wodgs_m.name} | **Test Filter:** {dgs_m.name}",
        "",
    ]
    for bullet in diff.narrative_summary:
        lines.append(f"- {bullet}")

    lines.append("")
    lines.append(
        "*Engineering Notice: Comparison is based directly on measured VNA S-parameter data. "
        "Reported values represent observed empirical differences rather than theoretical causation.*"
    )

    return "\n".join(lines)
