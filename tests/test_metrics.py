"""Tests for filter metrics (IL, RL, VSWR, Loaded Q, Ripple, Stopband)."""

import numpy as np
import pytest

from vna_filter_analyzer.filter_metrics import (
    calculate_filter_metrics,
    calculate_vswr,
)


def test_vswr_calculation():
    # S11 = -20 dB -> |Γ| = 0.1 -> VSWR = 1.1 / 0.9 = 1.2222
    s11 = np.array([-20.0, -10.0, 0.0])
    vswr = calculate_vswr(s11)

    assert vswr[0] == pytest.approx(1.2222, rel=1e-3)
    # S11 = -10 dB -> |Γ| = 0.3162 -> VSWR = 1.3162 / 0.6838 = 1.9248
    assert vswr[1] == pytest.approx(1.9248, rel=1e-3)


def test_filter_metrics_dgs():
    freq = np.linspace(1.0e9, 6.0e9, 1601)
    fc0 = 3.52e9
    bw0 = 420e6

    # Parabolic bandpass
    s21 = -1.42 - 3.0 * ((freq - fc0) / (bw0 / 2))**2
    s21 = np.clip(s21, -60.0, -1.42)

    s11 = -22.4 * np.ones_like(freq)
    s11[freq < 3.3e9] = -1.0
    s11[freq > 3.75e9] = -1.0

    metrics = calculate_filter_metrics(
        freq,
        s21,
        s11_db=s11,
        threshold_db=3.0,
        stopband_freqs_hz=[2.0e9, 2.5e9, 4.5e9, 5.0e9],
    )

    assert metrics.center_freq_hz == pytest.approx(fc0, rel=1e-3)
    assert metrics.peak_s21_db == pytest.approx(-1.42, abs=0.05)
    assert metrics.insertion_loss_db == pytest.approx(1.42, abs=0.05)
    assert metrics.bandwidth_hz == pytest.approx(bw0, rel=1e-2)
    assert metrics.loaded_q == pytest.approx(fc0 / bw0, rel=1e-2)
    assert metrics.return_loss_db == pytest.approx(22.4, abs=0.5)
    assert metrics.vswr_at_fc == pytest.approx(1.164, rel=1e-2)
    assert len(metrics.stopband_rejections) == 4
    assert metrics.stopband_rejections[2.0e9] > 20.0
