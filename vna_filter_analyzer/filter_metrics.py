"""Comprehensive filter characterization metrics (IL, RL, VSWR, Q, Ripple, Stopbands)."""

from typing import Dict, List, Optional
import numpy as np

from .data_model import FilterMetrics
from .bandwidth import calculate_bandwidth, interpolate_crossing


def calculate_vswr(s11_db: np.ndarray) -> np.ndarray:
    """Calculate VSWR from S11 in dB: VSWR = (1 + |Γ|) / (1 - |Γ|)."""
    # |Γ| = 10^(S11_dB / 20)
    # Clip gamma to < 1.0 to avoid division by zero / negative VSWR
    gamma = 10.0 ** (s11_db / 20.0)
    gamma = np.clip(gamma, 0.0, 0.999999)
    vswr = (1.0 + gamma) / (1.0 - gamma)
    return np.maximum(vswr, 1.0)


def calculate_filter_metrics(
    freq_hz: np.ndarray,
    s21_db: np.ndarray,
    s11_db: Optional[np.ndarray] = None,
    threshold_db: float = 3.0,
    center_freq_search_hz: Optional[float] = None,
    manual_fc_hz: Optional[float] = None,
    manual_fl_hz: Optional[float] = None,
    manual_fh_hz: Optional[float] = None,
    stopband_freqs_hz: Optional[List[float]] = None,
) -> FilterMetrics:
    """Compute all standard microwave filter metrics from measured S-parameters.

    Args:
        freq_hz: Frequency vector in Hz.
        s21_db: S21 magnitude in dB.
        s11_db: Optional S11 magnitude in dB.
        threshold_db: Bandwidth reference delta (typically 3.0 dB, or 1.0, 6.0, 10.0).
        center_freq_search_hz: Target frequency to locate passband peak.
        manual_fc_hz: Manual center frequency override.
        manual_fl_hz: Manual lower cutoff override.
        manual_fh_hz: Manual upper cutoff override.
        stopband_freqs_hz: List of inspection frequencies in Hz for rejection.

    Returns:
        FilterMetrics dataclass instance.
    """
    is_manual = (manual_fc_hz is not None or manual_fl_hz is not None or manual_fh_hz is not None)

    # 1. Bandwidth, Cutoffs, Peak S21
    fc_hz, peak_s21_db, target_lvl, fl_hz, fh_hz, bw_hz, fbw, loaded_q = calculate_bandwidth(
        freq_hz,
        s21_db,
        center_freq_search_hz=center_freq_search_hz,
        threshold_db=threshold_db,
        manual_fc_hz=manual_fc_hz,
        manual_fl_hz=manual_fl_hz,
        manual_fh_hz=manual_fh_hz,
    )

    # Insertion Loss = -Peak S21 (positive dB convention)
    insertion_loss_db = -peak_s21_db

    # In-band mask [fL, fH]
    in_band_mask = (freq_hz >= fl_hz) & (freq_hz <= fh_hz)

    # Passband Ripple: max(S21) - min(S21) within passband
    passband_ripple_db = None
    if np.any(in_band_mask):
        pb_s21 = s21_db[in_band_mask]
        passband_ripple_db = float(np.max(pb_s21) - np.min(pb_s21))
    else:
        # Fallback to target_level
        passband_ripple_db = float(abs(threshold_db))

    # 2. Return Loss & VSWR (if S11 available)
    min_s11_db = None
    return_loss_db = None
    vswr_at_fc = None
    min_vswr = None

    if s11_db is not None and len(s11_db) == len(freq_hz):
        # In-band S11
        if np.any(in_band_mask):
            in_band_s11 = s11_db[in_band_mask]
            min_s11_db = float(np.min(in_band_s11))
            return_loss_db = -min_s11_db  # Positive return loss convention
            in_band_vswr = calculate_vswr(in_band_s11)
            min_vswr = float(np.min(in_band_vswr))
        else:
            min_s11_db = float(np.min(s11_db))
            return_loss_db = -min_s11_db

        # VSWR at center frequency
        s11_at_fc = float(np.interp(fc_hz, freq_hz, s11_db))
        gamma_fc = 10.0 ** (s11_at_fc / 20.0)
        gamma_fc = min(0.999999, max(0.0, gamma_fc))
        vswr_at_fc = float((1.0 + gamma_fc) / (1.0 - gamma_fc))
        if min_vswr is None:
            min_vswr = vswr_at_fc

    # 3. Stopband Analysis
    # Lower stopband: frequencies below fL
    lower_mask = freq_hz < fl_hz
    lower_stopband_atten_db = None
    if np.any(lower_mask):
        # Max S21 below fL represents the worst-case rejection (i.e. attenuation is -max(S21))
        worst_lower_s21 = float(np.max(s21_db[lower_mask]))
        lower_stopband_atten_db = -worst_lower_s21

    # Upper stopband: frequencies above fH
    upper_mask = freq_hz > fh_hz
    upper_stopband_atten_db = None
    if np.any(upper_mask):
        worst_upper_s21 = float(np.max(s21_db[upper_mask]))
        upper_stopband_atten_db = -worst_upper_s21

    # Rejection at user-specified frequencies
    # Default stopband test frequencies if not given: [2.0e9, 2.5e9, 4.5e9, 5.0e9]
    if stopband_freqs_hz is None:
        stopband_freqs_hz = [2.0e9, 2.5e9, 4.5e9, 5.0e9]

    rejections: Dict[float, float] = {}
    f_min, f_max = float(freq_hz[0]), float(freq_hz[-1])
    for f_target in stopband_freqs_hz:
        if f_min <= f_target <= f_max:
            s21_at_f = float(np.interp(f_target, freq_hz, s21_db))
            # Rejection relative to 0 dB or relative to peak
            # Standard RF definition: attenuation in positive dB = -S21(f)
            rejections[f_target] = -s21_at_f

    # 4. Selectivity / Roll-off Slopes (dB/GHz)
    # Lower skirt: slope from target_level down to target_level - 20 dB (or minimum below fL)
    lower_slope = None
    upper_slope = None

    stopband_threshold_db = target_lvl - 20.0  # -20 dB relative to cutoff

    # Find lower frequency crossing stopband_threshold
    f_lower_stop = None
    for i in range(len(freq_hz) - 1, -1, -1):
        if freq_hz[i] < fl_hz:
            if s21_db[i] <= stopband_threshold_db:
                f_lower_stop = float(freq_hz[i])
                break
    if f_lower_stop is not None and abs(fl_hz - f_lower_stop) > 1e6:
        delta_f_ghz = abs(fl_hz - f_lower_stop) / 1e9
        delta_db = abs(target_lvl - stopband_threshold_db)
        lower_slope = float(delta_db / delta_f_ghz)
    elif np.any(lower_mask):
        # Fallback: slope from fL to lowest frequency point
        f_start = float(freq_hz[0])
        delta_f_ghz = abs(fl_hz - f_start) / 1e9
        if delta_f_ghz > 0.001:
            delta_db = abs(target_lvl - float(s21_db[0]))
            lower_slope = float(delta_db / delta_f_ghz)

    # Upper skirt: slope from target_level down to stopband_threshold
    f_upper_stop = None
    for i in range(len(freq_hz)):
        if freq_hz[i] > fh_hz:
            if s21_db[i] <= stopband_threshold_db:
                f_upper_stop = float(freq_hz[i])
                break
    if f_upper_stop is not None and abs(f_upper_stop - fh_hz) > 1e6:
        delta_f_ghz = abs(f_upper_stop - fh_hz) / 1e9
        delta_db = abs(target_lvl - stopband_threshold_db)
        upper_slope = float(delta_db / delta_f_ghz)
    elif np.any(upper_mask):
        # Fallback: slope from fH to highest frequency point
        f_end = float(freq_hz[-1])
        delta_f_ghz = abs(f_end - fh_hz) / 1e9
        if delta_f_ghz > 0.001:
            delta_db = abs(target_lvl - float(s21_db[-1]))
            upper_slope = float(delta_db / delta_f_ghz)

    return FilterMetrics(
        center_freq_hz=fc_hz,
        peak_s21_db=peak_s21_db,
        insertion_loss_db=insertion_loss_db,
        f_lower_hz=fl_hz,
        f_upper_hz=fh_hz,
        bandwidth_hz=bw_hz,
        fractional_bw=fbw,
        fractional_bw_pct=fbw * 100.0,
        loaded_q=loaded_q,
        bw_threshold_db=threshold_db,
        is_manual_override=is_manual,
        min_s11_db=min_s11_db,
        return_loss_db=return_loss_db,
        vswr_at_fc=vswr_at_fc,
        min_vswr=min_vswr,
        passband_ripple_db=passband_ripple_db,
        lower_stopband_atten_db=lower_stopband_atten_db,
        upper_stopband_atten_db=upper_stopband_atten_db,
        stopband_rejections=rejections,
        lower_transition_slope_db_per_ghz=lower_slope,
        upper_transition_slope_db_per_ghz=upper_slope,
    )
