"""Tests for multi-filter comparison and DGS vs non-DGS analysis."""

import numpy as np
import pytest

from vna_filter_analyzer.data_model import MeasurementData
from vna_filter_analyzer.filter_metrics import calculate_filter_metrics
from vna_filter_analyzer.comparison import (
    compare_measurements,
    calculate_differences,
    generate_dgs_summary,
)


def create_mock_measurement(name: str, fc: float, peak: float, bw: float, s11_val: float) -> MeasurementData:
    freq = np.linspace(1.0e9, 6.0e9, 1001)
    s21 = peak - 3.0 * ((freq - fc) / (bw / 2))**2
    s21 = np.clip(s21, -60.0, peak)
    s11 = s11_val * np.ones_like(freq)
    s11[np.abs(freq - fc) > bw / 2] = -1.0

    m = MeasurementData(
        file_path=f"/{name}.csv",
        name=name,
        raw_freq_hz=freq,
        raw_s_params={"S21": s21, "S11": s11},
    )
    m.metrics = calculate_filter_metrics(freq, s21, s11_db=s11, threshold_db=3.0)
    return m


def test_comparison_table():
    m1 = create_mock_measurement("DGS", 3.52e9, -1.42, 420e6, -22.4)
    m2 = create_mock_measurement("Without DGS", 3.51e9, -2.01, 410e6, -18.2)

    rows, df = compare_measurements([m1, m2])
    assert len(rows) > 10
    assert "DGS" in df.columns
    assert "Without DGS" in df.columns


def test_dgs_vs_non_dgs_diff():
    m1 = create_mock_measurement("Without DGS", 3.51e9, -2.01, 410e6, -18.2)
    m2 = create_mock_measurement("DGS", 3.52e9, -1.42, 420e6, -22.4)

    diff = calculate_differences(baseline=m1, test=m2)
    assert diff is not None
    # IL improvement = baseline_IL (2.01) - test_IL (1.42) = 0.59 dB
    assert diff.delta_il_db == pytest.approx(0.59, abs=0.05)
    assert diff.delta_fc_hz == pytest.approx(10e6, abs=1e6)
    assert len(diff.narrative_summary) >= 3

    summary = generate_dgs_summary([m1, m2])
    assert summary is not None
    assert "DGS vs. Non-DGS" in summary
