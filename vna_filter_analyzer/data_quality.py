"""Data quality checks and sanitation for VNA measurements."""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple
import numpy as np


@dataclass
class QualityReport:
    """Report of quality checks and warnings."""
    is_valid: bool = True
    warnings: List[str] = field(default_factory=list)
    total_points: int = 0
    nan_count: int = 0
    duplicate_count: int = 0
    is_monotonic: bool = True
    unphysical_points: int = 0


def check_data_quality(
    freq_hz: np.ndarray,
    s_params: Dict[str, np.ndarray],
    max_passive_gain_db: float = 15.0,
) -> Tuple[np.ndarray, Dict[str, np.ndarray], QualityReport]:
    """Inspect and sanitize VNA measurement arrays.

    Checks for:
    - Insufficient data points (< 10 points)
    - NaN or Inf values in frequency or S-parameters
    - Non-monotonic frequency order (sorts them)
    - Duplicate frequencies (averages duplicate points)
    - Unusually high S-parameter values (> +15 dB) indicating uncalibrated or corrupted data

    Returns:
        Tuple of (sanitized_freq_hz, sanitized_s_params, QualityReport)
    """
    report = QualityReport()
    freq = np.asarray(freq_hz, dtype=np.float64)
    total = len(freq)
    report.total_points = total

    if total < 10:
        report.is_valid = False
        report.warnings.append(f"Insufficient data points: File contains only {total} points (minimum 10 required).")
        return freq, s_params, report

    # Check for NaN / Inf in frequency
    valid_mask = np.isfinite(freq) & (freq > 0)
    nan_freq = total - np.count_nonzero(valid_mask)
    if nan_freq > 0:
        report.warnings.append(f"Warning: {nan_freq} invalid or negative frequency points were found and excluded.")
        report.nan_count += nan_freq

    # Check S-parameters for finite values
    for param_name, param_data in s_params.items():
        p_arr = np.asarray(param_data, dtype=np.float64)
        if len(p_arr) != total:
            report.warnings.append(f"Dimension mismatch: '{param_name}' has {len(p_arr)} points, expected {total}.")
            min_len = min(len(p_arr), len(valid_mask))
            valid_mask = valid_mask[:min_len]
            p_arr = p_arr[:min_len]
        
        param_nan = np.count_nonzero(~np.isfinite(p_arr[:len(valid_mask)]))
        if param_nan > 0:
            report.warnings.append(f"Warning: {param_nan} invalid {param_name} points were found and excluded from interpolation.")
            report.nan_count += param_nan
            valid_mask &= np.isfinite(p_arr[:len(valid_mask)])

        # Check for unphysical passive values (e.g. S21 >> 0 dB)
        unphysical = np.count_nonzero(p_arr[valid_mask[:len(p_arr)]] > max_passive_gain_db)
        if unphysical > 0:
            report.unphysical_points += unphysical
            report.warnings.append(f"Notice: {unphysical} points in '{param_name}' exceed +{max_passive_gain_db:.0f} dB (check calibration).")

    # Apply initial valid mask
    clean_freq = freq[valid_mask]
    clean_s = {k: np.asarray(v)[valid_mask] for k, v in s_params.items()}

    if len(clean_freq) < 10:
        report.is_valid = False
        report.warnings.append("Data quality error: Fewer than 10 valid measurement points remaining after filtering.")
        return clean_freq, clean_s, report

    # Check monotonicity
    diffs = np.diff(clean_freq)
    if np.any(diffs < 0):
        report.is_monotonic = False
        report.warnings.append("Notice: Frequency points were non-monotonic and have been automatically sorted.")
        sort_idx = np.argsort(clean_freq)
        clean_freq = clean_freq[sort_idx]
        clean_s = {k: v[sort_idx] for k, v in clean_s.items()}

    # Check duplicates
    unique_freq, unique_indices = np.unique(clean_freq, return_index=True)
    if len(unique_freq) < len(clean_freq):
        dup_count = len(clean_freq) - len(unique_freq)
        report.duplicate_count = dup_count
        report.warnings.append(f"Notice: {dup_count} duplicate frequency points were found and resolved.")
        # Group and average duplicates
        averaged_s = {k: [] for k in clean_s}
        unique_f_list = []
        
        # Fast binning using pandas or numpy unique inverse
        _, inverse_indices = np.unique(clean_freq, return_inverse=True)
        unique_count = len(unique_freq)
        clean_freq = unique_freq
        
        for k in clean_s:
            sums = np.bincount(inverse_indices, weights=clean_s[k])
            counts = np.bincount(inverse_indices)
            clean_s[k] = sums / counts

    return clean_freq, clean_s, report
