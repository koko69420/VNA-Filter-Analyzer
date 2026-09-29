"""Accurate interpolated bandwidth, cutoff frequencies, and Q factor calculations."""

from typing import Optional, Tuple
import numpy as np


def interpolate_crossing(
    f1: float,
    s1: float,
    f2: float,
    s2: float,
    target_s: float,
) -> float:
    """Linearly interpolate the frequency where the response crosses target_s.

    Args:
        f1, s1: Frequency and response at first point.
        f2, s2: Frequency and response at second point.
        target_s: Target dB level.

    Returns:
        Interpolated frequency in Hz.
    """
    if abs(s2 - s1) < 1e-12:
        return (f1 + f2) / 2.0
    # f = f1 + (target - s1) * (f2 - f1) / (s2 - s1)
    fraction = (target_s - s1) / (s2 - s1)
    fraction = max(0.0, min(1.0, fraction))
    return float(f1 + fraction * (f2 - f1))


def refine_peak_frequency(
    freq_hz: np.ndarray,
    s21_db: np.ndarray,
    peak_idx: int,
) -> Tuple[float, float]:
    """Refine center frequency and peak value using 3-point parabolic interpolation.

    Returns:
        (interpolated_fc_hz, interpolated_peak_db)
    """
    if peak_idx <= 0 or peak_idx >= len(freq_hz) - 1:
        return float(freq_hz[peak_idx]), float(s21_db[peak_idx])

    # Parabolic vertex interpolation
    y1 = s21_db[peak_idx - 1]
    y2 = s21_db[peak_idx]
    y3 = s21_db[peak_idx + 1]

    denom = 2.0 * (2.0 * y2 - y1 - y3)
    if abs(denom) < 1e-12:
        return float(freq_hz[peak_idx]), float(y2)

    delta = (y1 - y3) / denom
    delta = max(-0.5, min(0.5, delta))

    f1 = freq_hz[peak_idx - 1]
    f2 = freq_hz[peak_idx]
    f3 = freq_hz[peak_idx + 1]

    # Frequency delta
    df = (f3 - f1) / 2.0
    fc = float(f2 - delta * df)
    peak_val = float(y2 + 0.125 * denom * (delta ** 2))

    return fc, max(peak_val, float(y2))


def calculate_bandwidth(
    freq_hz: np.ndarray,
    s21_db: np.ndarray,
    center_freq_search_hz: Optional[float] = None,
    threshold_db: float = 3.0,
    manual_fc_hz: Optional[float] = None,
    manual_fl_hz: Optional[float] = None,
    manual_fh_hz: Optional[float] = None,
) -> Tuple[float, float, float, float, float, float, float, float]:
    """Calculate filter center frequency, cutoff frequencies, bandwidth, FBW, and loaded Q.

    Args:
        freq_hz: 1D array of frequency in Hz.
        s21_db: 1D array of S21 magnitude in dB.
        center_freq_search_hz: Optional frequency to guide peak search.
        threshold_db: Bandwidth threshold in dB relative to peak (default 3.0).
        manual_fc_hz: Optional manual center frequency override.
        manual_fl_hz: Optional manual lower cutoff override.
        manual_fh_hz: Optional manual upper cutoff override.

    Returns:
        Tuple of:
        (fc_hz, peak_s21_db, target_level_db, fl_hz, fh_hz, bw_hz, fbw, loaded_q)
    """
    n = len(freq_hz)
    if n < 3:
        raise ValueError("Insufficient points for bandwidth calculation (at least 3 points required).")

    # Determine peak index
    if center_freq_search_hz is not None:
        # Search peak within a window around center_freq_search_hz
        dist = np.abs(freq_hz - center_freq_search_hz)
        near_idx = int(np.argmin(dist))
        # Search locally (+/- 30 points)
        w_start = max(0, near_idx - 30)
        w_end = min(n, near_idx + 31)
        peak_idx = w_start + int(np.argmax(s21_db[w_start:w_end]))
    else:
        peak_idx = int(np.argmax(s21_db))

    discrete_fc = float(freq_hz[peak_idx])
    discrete_peak_s21 = float(s21_db[peak_idx])

    # Parabolic sub-sample refinement
    refined_fc, refined_peak = refine_peak_frequency(freq_hz, s21_db, peak_idx)

    # Use manual Fc if provided
    fc_hz = manual_fc_hz if manual_fc_hz is not None else refined_fc
    peak_s21_db = refined_peak if manual_fc_hz is None else float(np.interp(fc_hz, freq_hz, s21_db))

    target_level_db = peak_s21_db - abs(threshold_db)

    # Search outward for Lower Cutoff (fL)
    fl_hz = None
    if manual_fl_hz is not None:
        fl_hz = manual_fl_hz
    else:
        # Step backward from peak_idx
        for i in range(peak_idx, 0, -1):
            s_curr = s21_db[i]
            s_prev = s21_db[i - 1]
            # We are descending as we move left: s_curr > target and s_prev <= target
            if s_curr >= target_level_db and s_prev < target_level_db:
                fl_hz = interpolate_crossing(
                    freq_hz[i - 1], s_prev,
                    freq_hz[i], s_curr,
                    target_level_db,
                )
                break
        if fl_hz is None:
            # If not crossed, take edge
            fl_hz = float(freq_hz[0])

    # Search outward for Upper Cutoff (fH)
    fh_hz = None
    if manual_fh_hz is not None:
        fh_hz = manual_fh_hz
    else:
        # Step forward from peak_idx
        for i in range(peak_idx, n - 1):
            s_curr = s21_db[i]
            s_next = s21_db[i + 1]
            # We are descending as we move right: s_curr >= target and s_next < target
            if s_curr >= target_level_db and s_next < target_level_db:
                fh_hz = interpolate_crossing(
                    freq_hz[i], s_curr,
                    freq_hz[i + 1], s_next,
                    target_level_db,
                )
                break
        if fh_hz is None:
            fh_hz = float(freq_hz[-1])

    # Ensure fL < fH
    if fl_hz > fh_hz:
        fl_hz, fh_hz = fh_hz, fl_hz

    bw_hz = max(0.0, fh_hz - fl_hz)
    fbw = (bw_hz / fc_hz) if fc_hz > 0 else 0.0
    loaded_q = (fc_hz / bw_hz) if bw_hz > 0 else 0.0

    return fc_hz, peak_s21_db, target_level_db, fl_hz, fh_hz, bw_hz, fbw, loaded_q
