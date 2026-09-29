"""Passband and resonant peak detection algorithms for microwave filters."""

from typing import List, Tuple
import numpy as np
from scipy.signal import find_peaks

from .data_model import PassbandInfo


def detect_passbands(
    freq_hz: np.ndarray,
    s21_db: np.ndarray,
    min_prominence_db: float = 3.0,
    min_peak_height_db: float = -35.0,
    peak_distance_points: int = 15,
) -> List[PassbandInfo]:
    """Identify transmission passbands (peaks) in S21 response.

    Args:
        freq_hz: 1D array of frequency in Hz.
        s21_db: 1D array of transmission in dB.
        min_prominence_db: Minimum prominence of peak above local floor (dB).
        min_peak_height_db: Absolute minimum height of peak to be considered a passband.
        peak_distance_points: Minimum separation between peaks in data indices.

    Returns:
        List of PassbandInfo objects sorted by peak S21 descending (strongest transmission first).
    """
    if len(freq_hz) < 10 or len(s21_db) != len(freq_hz):
        return []

    # If peak prominence is high or curve is relatively flat, try standard peak finder
    peaks, properties = find_peaks(
        s21_db,
        height=min_peak_height_db,
        prominence=min_prominence_db,
        distance=peak_distance_points,
    )

    # If no peaks found with strict thresholds, relax and look for global maximum
    if len(peaks) == 0:
        global_max_idx = int(np.argmax(s21_db))
        peaks = np.array([global_max_idx])
        prominences = np.array([abs(s21_db[global_max_idx] - np.min(s21_db))])
    else:
        prominences = properties.get("prominences", np.zeros(len(peaks)))

    passbands: List[PassbandInfo] = []

    for idx, peak_idx in enumerate(peaks):
        fc = float(freq_hz[peak_idx])
        peak_val = float(s21_db[peak_idx])
        target_3db = peak_val - 3.0

        # Rough search for -3 dB boundaries
        # Left search
        f_lower = float(freq_hz[0])
        for i in range(peak_idx, -1, -1):
            if s21_db[i] <= target_3db:
                # Linear interp
                if i < peak_idx:
                    f1, f2 = freq_hz[i], freq_hz[i + 1]
                    s1, s2 = s21_db[i], s21_db[i + 1]
                    if s2 != s1:
                        f_lower = float(f1 + (target_3db - s1) * (f2 - f1) / (s2 - s1))
                    else:
                        f_lower = float(f1)
                else:
                    f_lower = float(freq_hz[i])
                break

        # Right search
        f_upper = float(freq_hz[-1])
        for i in range(peak_idx, len(freq_hz)):
            if s21_db[i] <= target_3db:
                if i > peak_idx:
                    f1, f2 = freq_hz[i - 1], freq_hz[i]
                    s1, s2 = s21_db[i - 1], s21_db[i]
                    if s2 != s1:
                        f_upper = float(f1 + (target_3db - s1) * (f2 - f1) / (s2 - s1))
                    else:
                        f_upper = float(f2)
                else:
                    f_upper = float(freq_hz[i])
                break

        bw = max(0.0, f_upper - f_lower)
        fbw_pct = (bw / fc * 100.0) if fc > 0 else 0.0
        prom = float(prominences[idx]) if idx < len(prominences) else 0.0

        passbands.append(
            PassbandInfo(
                index=idx,
                fc_hz=fc,
                peak_s21_db=peak_val,
                f_lower_hz=f_lower,
                f_upper_hz=f_upper,
                bw_hz=bw,
                fbw_pct=fbw_pct,
                prominence_db=prom,
            )
        )

    # Sort so strongest passband (highest peak S21) is first
    passbands.sort(key=lambda p: p.peak_s21_db, reverse=True)
    # Re-index
    for i, pb in enumerate(passbands):
        pb.index = i

    return passbands
