"""Export metrics and comparison tables to CSV, Excel (.xlsx), and JSON."""

import json
from typing import List, Optional
import pandas as pd
import openpyxl

from .data_model import MeasurementData
from .comparison import compare_measurements, calculate_differences


def export_results_to_csv(
    measurements: List[MeasurementData],
    file_path: str,
) -> str:
    """Export comparison table and metrics to CSV."""
    _, df = compare_measurements(measurements)
    df.to_csv(file_path, index=False)
    return file_path


def export_results_to_excel(
    measurements: List[MeasurementData],
    file_path: str,
    include_raw_data: bool = True,
) -> str:
    """Export comparison table and raw data into a formatted multi-sheet Excel file."""
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        # Sheet 1: Filter Metrics Comparison
        _, comp_df = compare_measurements(measurements)
        if not comp_df.empty:
            comp_df.to_excel(writer, sheet_name="Filter Metrics", index=False)

        # Sheet 2: Differences (if >= 2 measurements)
        if len(measurements) >= 2 and measurements[0].metrics and measurements[1].metrics:
            diff = calculate_differences(measurements[0], measurements[1])
            if diff:
                diff_data = {
                    "Metric": [
                        "Baseline Filter",
                        "Test Filter",
                        "Center Frequency Shift",
                        "Bandwidth Difference",
                        "Bandwidth % Change",
                        "Insertion Loss Improvement",
                        "Return Loss Difference",
                        "Fractional Bandwidth Shift",
                        "Loaded Q Difference",
                    ],
                    "Value": [
                        diff.baseline_name,
                        diff.test_name,
                        f"{diff.delta_fc_hz / 1e6:+.2f} MHz",
                        f"{diff.delta_bw_hz / 1e6:+.2f} MHz",
                        f"{diff.bw_pct_change:+.2f} %",
                        f"{diff.delta_il_db:+.2f} dB",
                        f"{diff.delta_rl_db:+.2f} dB" if diff.delta_rl_db is not None else "N/A",
                        f"{diff.delta_fbw_pct:+.2f} %",
                        f"{diff.delta_q:+.2f}",
                    ]
                }
                pd.DataFrame(diff_data).to_excel(writer, sheet_name="Differences", index=False)

        # Sheet 3..N: Raw measurement data
        if include_raw_data:
            for idx, m in enumerate(measurements):
                sheet_title = f"Data_{m.name[:20]}"
                raw_dict = {"Frequency (Hz)": m.clean_freq_hz}
                for param, vals in m.clean_s_params.items():
                    raw_dict[f"{param} (dB)"] = vals
                pd.DataFrame(raw_dict).to_excel(writer, sheet_name=sheet_title, index=False)

    return file_path


def export_results_to_json(
    measurements: List[MeasurementData],
    file_path: str,
) -> str:
    """Export complete metrics analysis to JSON."""
    data = []
    for m in measurements:
        if m.metrics is None:
            continue
        met = m.metrics
        item = {
            "name": m.name,
            "file_path": m.file_path,
            "center_freq_hz": met.center_freq_hz,
            "peak_s21_db": met.peak_s21_db,
            "insertion_loss_db": met.insertion_loss_db,
            "f_lower_hz": met.f_lower_hz,
            "f_upper_hz": met.f_upper_hz,
            "bandwidth_hz": met.bandwidth_hz,
            "fractional_bw_pct": met.fractional_bw_pct,
            "loaded_q": met.loaded_q,
            "min_s11_db": met.min_s11_db,
            "return_loss_db": met.return_loss_db,
            "vswr_at_fc": met.vswr_at_fc,
            "min_vswr": met.min_vswr,
            "passband_ripple_db": met.passband_ripple_db,
            "lower_stopband_atten_db": met.lower_stopband_atten_db,
            "upper_stopband_atten_db": met.upper_stopband_atten_db,
            "stopband_rejections": {str(k): v for k, v in met.stopband_rejections.items()},
        }
        data.append(item)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({"measurements": data}, f, indent=2)

    return file_path
