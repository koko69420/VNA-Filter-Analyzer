"""Tests for data quality checks and sanitation."""

import numpy as np
import pytest

from vna_filter_analyzer.data_quality import check_data_quality


def test_data_quality_clean():
    freq = np.linspace(1e9, 2e9, 100)
    s21 = -2.0 * np.ones(100)
    clean_f, clean_s, report = check_data_quality(freq, {"S21": s21})

    assert report.is_valid
    assert len(clean_f) == 100
    assert len(report.warnings) == 0


def test_data_quality_with_nans():
    freq = np.linspace(1e9, 2e9, 100)
    s21 = -2.0 * np.ones(100)
    # Inject 4 NaNs
    s21[10] = np.nan
    s21[20] = np.nan
    freq[30] = np.nan
    freq[40] = -1.0

    clean_f, clean_s, report = check_data_quality(freq, {"S21": s21})
    assert report.is_valid
    assert len(clean_f) == 96
    assert any("invalid" in w.lower() for w in report.warnings)


def test_data_quality_insufficient_points():
    freq = np.linspace(1e9, 2e9, 5)
    s21 = -2.0 * np.ones(5)
    clean_f, clean_s, report = check_data_quality(freq, {"S21": s21})

    assert not report.is_valid
    assert "Insufficient data points" in report.warnings[0]


def test_data_quality_non_monotonic():
    freq = np.array([1.0e9, 1.2e9, 1.1e9, 1.3e9, 1.4e9, 1.5e9, 1.6e9, 1.7e9, 1.8e9, 1.9e9, 2.0e9])
    s21 = -2.0 * np.ones_like(freq)
    clean_f, clean_s, report = check_data_quality(freq, {"S21": s21})

    assert report.is_valid
    assert not report.is_monotonic
    # Must be sorted
    assert np.all(np.diff(clean_f) > 0)
