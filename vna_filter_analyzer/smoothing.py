"""Smoothing filters for visualization of VNA frequency response."""

from typing import Optional, Tuple
import numpy as np
from scipy.signal import savgol_filter


def apply_smoothing(
    y: np.ndarray,
    method: str = "savgol",
    window_len: int = 15,
    polyorder: int = 3,
) -> np.ndarray:
    """Apply smoothing filter to an S-parameter response purely for display.

    Args:
        y: 1D array of values (e.g. S21 in dB).
        method: 'savgol' (Savitzky-Golay) or 'moving_avg' (uniform moving average).
        window_len: Number of points in smoothing window (will be forced to odd for savgol).
        polyorder: Polynomial order for Savitzky-Golay (must be < window_len).

    Returns:
        Smoothed 1D array with same length as y.
    """
    n = len(y)
    if n < 5:
        return np.copy(y)

    # Ensure window is valid
    w = max(3, int(window_len))
    if w % 2 == 0:
        w += 1
    if w >= n:
        w = n if n % 2 != 0 else n - 1
    if w < 3:
        return np.copy(y)

    if method.lower() in ("savgol", "savitzky-golay"):
        order = min(polyorder, w - 1)
        try:
            return savgol_filter(y, window_length=w, polyorder=order, mode="nearest")
        except Exception:
            return np.copy(y)
    elif method.lower() in ("moving_avg", "ma", "boxcar"):
        # Uniform moving average with edge padding
        kernel = np.ones(w) / w
        pad_width = w // 2
        padded = np.pad(y, pad_width, mode="edge")
        smoothed = np.convolve(padded, kernel, mode="valid")
        return smoothed[:n]
    else:
        return np.copy(y)


def check_smoothing_shift(
    freq_hz: np.ndarray,
    raw_s21: np.ndarray,
    smoothed_s21: np.ndarray,
    tolerance_fc_pct: float = 0.5,
) -> Tuple[bool, str]:
    """Check if smoothing substantially shifts the detected center frequency peak.

    Returns:
        (has_significant_shift, warning_message)
    """
    if len(freq_hz) < 3 or len(raw_s21) != len(freq_hz):
        return False, ""

    raw_peak_idx = int(np.argmax(raw_s21))
    smooth_peak_idx = int(np.argmax(smoothed_s21))

    raw_fc = freq_hz[raw_peak_idx]
    smooth_fc = freq_hz[smooth_peak_idx]

    shift_pct = abs(smooth_fc - raw_fc) / raw_fc * 100.0 if raw_fc > 0 else 0.0

    if shift_pct > tolerance_fc_pct:
        from .units import format_frequency
        return True, (
            f"Caution: Smoothing shifted peak by {shift_pct:.2f}% "
            f"({format_frequency(raw_fc)} raw vs {format_frequency(smooth_fc)} smoothed). "
            f"Analysis uses raw data as source of truth."
        )
    return False, ""
