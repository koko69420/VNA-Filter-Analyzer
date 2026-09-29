"""Tests for bandwidth and cutoff interpolation."""

import numpy as np
import pytest

from vna_filter_analyzer.bandwidth import (
    calculate_bandwidth,
    interpolate_crossing,
    refine_peak_frequency,
)


def test_interpolate_crossing():
    f1, s1 = 3.30e9, -2.90
    f2, s2 = 3.31e9, -3.10
    target = -3.00

    f_cross = interpolate_crossing(f1, s1, f2, s2, target)
    assert f_cross == pytest.approx(3.305e9, abs=1e6)


def test_calculate_bandwidth_analytical_filter():
    # Construct an analytical bandpass response centered at 3.50 GHz with BW = 400 MHz (3.30 to 3.70 GHz)
    freq = np.linspace(2.5e9, 4.5e9, 2001)
    fc_expected = 3.50e9
    bw_expected = 400e6  # 3.30 to 3.70 GHz

    # Second-order Butterworth bandpass prototype: |S21|^2 = 1 / (1 + (2*(f-fc)/BW)^4)
    x = 2.0 * (freq - fc_expected) / bw_expected
    # At x = +/- 1, loss is 10*log10(1 + 1) = 3.0103 dB
    s21_db = -10.0 * np.log10(1.0 + x**4) - 1.50  # -1.50 dB peak IL

    fc, peak_s21, target_lvl, fl, fh, bw, fbw, loaded_q = calculate_bandwidth(
        freq, s21_db, threshold_db=3.0103
    )

    assert fc == pytest.approx(fc_expected, rel=1e-3)
    assert peak_s21 == pytest.approx(-1.50, abs=0.05)
    assert fl == pytest.approx(3.30e9, rel=1e-3)
    assert fh == pytest.approx(3.70e9, rel=1e-3)
    assert bw == pytest.approx(400e6, rel=1e-3)
    assert fbw == pytest.approx(400e6 / 3.5e9, rel=1e-3)
    assert loaded_q == pytest.approx(3.5e9 / 400e6, rel=1e-3)


def test_manual_override():
    freq = np.linspace(3.0e9, 4.0e9, 1001)
    s21 = -2.0 - 20.0 * ((freq - 3.5e9) / 200e6)**2

    # Override with manual Fc=3.45 GHz, fL=3.35 GHz, fH=3.55 GHz
    fc, peak_s21, target_lvl, fl, fh, bw, fbw, loaded_q = calculate_bandwidth(
        freq, s21, manual_fc_hz=3.45e9, manual_fl_hz=3.35e9, manual_fh_hz=3.55e9
    )

    assert fc == 3.45e9
    assert fl == 3.35e9
    assert fh == 3.55e9
    assert bw == pytest.approx(200e6)
    assert fbw == pytest.approx(200e6 / 3.45e9)
