"""Data models for VNA measurements, filter metrics, and passbands."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import numpy as np


@dataclass
class PassbandInfo:
    """Represents a detected passband peak and its approximate boundaries."""
    index: int
    fc_hz: float
    peak_s21_db: float
    f_lower_hz: float
    f_upper_hz: float
    bw_hz: float
    fbw_pct: float
    prominence_db: float = 0.0

    @property
    def label(self) -> str:
        from .units import format_frequency, format_bandwidth
        return (f"Passband {self.index + 1}: {format_frequency(self.fc_hz)} "
                f"(Peak: {self.peak_s21_db:.2f} dB, BW: {format_bandwidth(self.bw_hz)})")


@dataclass
class FilterMetrics:
    """Filter parameters calculated from measurements."""
    center_freq_hz: float
    peak_s21_db: float
    insertion_loss_db: float  # Magnitude of peak attenuation (positive dB)
    f_lower_hz: float
    f_upper_hz: float
    bandwidth_hz: float
    fractional_bw: float
    fractional_bw_pct: float
    loaded_q: float
    bw_threshold_db: float = 3.0
    is_manual_override: bool = False

    # Return Loss & VSWR (requires S11)
    min_s11_db: Optional[float] = None
    return_loss_db: Optional[float] = None
    vswr_at_fc: Optional[float] = None
    min_vswr: Optional[float] = None

    # Passband Ripple
    passband_ripple_db: Optional[float] = None

    # Stopband & Selectivity
    lower_stopband_atten_db: Optional[float] = None
    upper_stopband_atten_db: Optional[float] = None
    stopband_rejections: Dict[float, float] = field(default_factory=dict)  # freq_hz -> rejection_db
    lower_transition_slope_db_per_ghz: Optional[float] = None
    upper_transition_slope_db_per_ghz: Optional[float] = None


class MeasurementData:
    """Represents a single imported VNA measurement file with raw and processed responses."""

    DEFAULT_COLORS = [
        "#1f77b4",  # Blue
        "#ff7f0e",  # Orange
        "#2ca02c",  # Green
        "#d62728",  # Red
        "#9467bd",  # Purple
        "#8c564b",  # Brown
    ]

    def __init__(
        self,
        file_path: str,
        name: str,
        raw_freq_hz: np.ndarray,
        raw_s_params: Dict[str, np.ndarray],
        metadata: Optional[Dict[str, str]] = None,
        color: Optional[str] = None,
        index: int = 0,
    ):
        self.file_path = file_path
        self.name = name
        self.color = color or self.DEFAULT_COLORS[index % len(self.DEFAULT_COLORS)]
        self.line_style = "solid"
        self.visible = True
        self.metadata = metadata or {}
        self.quality_warnings: List[str] = []

        # Raw arrays (the immutable source of truth)
        self.raw_freq_hz = np.asarray(raw_freq_hz, dtype=np.float64)
        self.raw_s_params = {k: np.asarray(v, dtype=np.float64) for k, v in raw_s_params.items()}

        # Cleaned/sanitized arrays (sorted, NaNs handled)
        self.clean_freq_hz = np.copy(self.raw_freq_hz)
        self.clean_s_params = {k: np.copy(v) for k, v in self.raw_s_params.items()}

        # Display smoothing
        self.smoothing_enabled = False
        self.smoothing_method = "savgol"  # 'savgol' or 'moving_avg'
        self.smoothing_window = 15
        self.smoothing_polyorder = 3
        self.display_mode = "Raw"  # 'Raw', 'Smoothed', 'Both'
        self.smoothed_s_params: Dict[str, np.ndarray] = {}

        # Analysis state
        self.active_s_param = "S21" if "S21" in self.raw_s_params else next(iter(self.raw_s_params.keys()), "S21")
        self.detected_passbands: List[PassbandInfo] = []
        self.active_passband_idx = 0
        self.bw_threshold_db = 3.0  # e.g. 1.0, 3.0, 6.0, 10.0 dB
        self.metrics: Optional[FilterMetrics] = None

        # Manual marker overrides
        self.use_manual_markers = False
        self.manual_fc_hz: Optional[float] = None
        self.manual_fl_hz: Optional[float] = None
        self.manual_fh_hz: Optional[float] = None

    @property
    def num_points(self) -> int:
        return len(self.clean_freq_hz)

    @property
    def freq_range_hz(self) -> tuple[float, float]:
        if len(self.clean_freq_hz) > 0:
            return float(self.clean_freq_hz[0]), float(self.clean_freq_hz[-1])
        return 0.0, 0.0

    def available_s_params(self) -> List[str]:
        return list(self.clean_s_params.keys())

    def get_display_trace(self, param: str) -> Dict[str, np.ndarray]:
        """Return dict of traces to plot according to display_mode."""
        result = {}
        if param not in self.clean_s_params:
            return result

        if self.display_mode in ("Raw", "Both"):
            result["raw"] = self.clean_s_params[param]

        if self.display_mode in ("Smoothed", "Both"):
            if param in self.smoothed_s_params:
                result["smoothed"] = self.smoothed_s_params[param]
            else:
                result["smoothed"] = self.clean_s_params[param]

        return result
