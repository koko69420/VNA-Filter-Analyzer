"""Tests for CSV and Touchstone parsing."""

import os
import pytest
import numpy as np

from vna_filter_analyzer.csv_parser import (
    parse_vna_file,
    detect_columns,
    detect_delimiter,
    parse_touchstone,
)


def test_parse_dgs_csv():
    file_path = "sample_data/dgs_filter_5th_order.csv"
    assert os.path.exists(file_path)

    result = parse_vna_file(file_path)
    assert result.freq_hz is not None
    assert len(result.freq_hz) == 1601
    assert "S21" in result.s_params
    assert "S11" in result.s_params
    assert result.freq_hz[0] == pytest.approx(1.0e9, rel=1e-3)
    assert result.freq_hz[-1] == pytest.approx(6.0e9, rel=1e-3)
    assert result.metadata.get("Points") == "1601"
    assert "Rohde & Schwarz" in result.metadata.get("VNA Model", "")


def test_parse_semicolon_csv():
    file_path = "sample_data/rs_znb_measured_export.csv"
    assert os.path.exists(file_path)

    delim = detect_delimiter(file_path)
    assert delim == ";"

    result = parse_vna_file(file_path)
    assert len(result.freq_hz) == 1601
    assert "S21" in result.s_params
    assert "S11" in result.s_params


def test_parse_ghz_unit_csv():
    file_path = "sample_data/dual_passband_filter.csv"
    assert os.path.exists(file_path)

    result = parse_vna_file(file_path)
    # Ensure frequency was converted from GHz to Hz (~1e9 to 6e9)
    assert result.freq_hz[0] >= 0.9e9
    assert result.freq_hz[-1] <= 6.1e9


def test_parse_touchstone_s2p():
    file_path = "stage1_network.s2p"
    if os.path.exists(file_path):
        result = parse_touchstone(file_path)
        assert result is not None
        assert len(result.freq_hz) > 100
        assert "S21" in result.s_params
        assert "S11" in result.s_params


def test_parse_rvitm_single_file():
    rvitm_file = "RVITM/S21_with_DGS"
    if os.path.exists(rvitm_file):
        result = parse_vna_file(rvitm_file)
        assert result is not None
        assert result.measurement_name == "DGS"
        assert len(result.freq_hz) == 201
        assert result.freq_hz[0] == pytest.approx(0.700e9)
        assert result.freq_hz[-1] == pytest.approx(1.100e9)
        # Sibling merging should automatically pick up S11, S12, S22
        assert "S21" in result.s_params
        assert "S11" in result.s_params
        assert "S12" in result.s_params
        assert "S22" in result.s_params


def test_parse_rvitm_directory():
    rvitm_dir = "RVITM"
    if os.path.isdir(rvitm_dir):
        from vna_filter_analyzer.csv_parser import parse_rvitm_directory
        results = parse_rvitm_directory(rvitm_dir)
        assert len(results) == 2
        names = [r.measurement_name for r in results]
        assert "DGS" in names
        assert "Without DGS" in names
        for r in results:
            assert "S21" in r.s_params
            assert "S11" in r.s_params


def test_parse_cst_export():
    cst_file = "sample_data/cst_bandpass_export.txt"
    assert os.path.exists(cst_file)
    result = parse_vna_file(cst_file)
    assert result is not None
    assert len(result.freq_hz) == 11
    assert result.freq_hz[0] == pytest.approx(0.700e9)
    assert result.freq_hz[-1] == pytest.approx(1.100e9)
    assert "S21" in result.s_params
    assert "S11" in result.s_params

