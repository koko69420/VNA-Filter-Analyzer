"""Project state persistence (.vna files)."""

import json
import os
from typing import Any, Dict, List, Optional
import numpy as np

from .data_model import MeasurementData, FilterMetrics
from .filter_metrics import calculate_filter_metrics


def serialize_measurement(m: MeasurementData) -> Dict[str, Any]:
    """Convert a MeasurementData instance into a JSON-serializable dictionary."""
    return {
        "file_path": m.file_path,
        "name": m.name,
        "color": m.color,
        "line_style": m.line_style,
        "visible": m.visible,
        "metadata": m.metadata,
        "raw_freq_hz": m.raw_freq_hz.tolist(),
        "raw_s_params": {k: v.tolist() for k, v in m.raw_s_params.items()},
        "active_s_param": m.active_s_param,
        "active_passband_idx": m.active_passband_idx,
        "bw_threshold_db": m.bw_threshold_db,
        "smoothing_enabled": m.smoothing_enabled,
        "smoothing_method": m.smoothing_method,
        "smoothing_window": m.smoothing_window,
        "smoothing_polyorder": m.smoothing_polyorder,
        "display_mode": m.display_mode,
        "use_manual_markers": m.use_manual_markers,
        "manual_fc_hz": m.manual_fc_hz,
        "manual_fl_hz": m.manual_fl_hz,
        "manual_fh_hz": m.manual_fh_hz,
    }


def deserialize_measurement(data: Dict[str, Any], index: int = 0) -> MeasurementData:
    """Reconstruct a MeasurementData instance from serialized dictionary."""
    freq_arr = np.array(data["raw_freq_hz"], dtype=np.float64)
    s_params = {k: np.array(v, dtype=np.float64) for k, v in data["raw_s_params"].items()}

    m = MeasurementData(
        file_path=data.get("file_path", ""),
        name=data.get("name", f"Filter {index + 1}"),
        raw_freq_hz=freq_arr,
        raw_s_params=s_params,
        metadata=data.get("metadata", {}),
        color=data.get("color"),
        index=index,
    )

    m.line_style = data.get("line_style", "solid")
    m.visible = data.get("visible", True)
    m.active_s_param = data.get("active_s_param", "S21")
    m.active_passband_idx = data.get("active_passband_idx", 0)
    m.bw_threshold_db = float(data.get("bw_threshold_db", 3.0))
    m.smoothing_enabled = data.get("smoothing_enabled", False)
    m.smoothing_method = data.get("smoothing_method", "savgol")
    m.smoothing_window = int(data.get("smoothing_window", 15))
    m.smoothing_polyorder = int(data.get("smoothing_polyorder", 3))
    m.display_mode = data.get("display_mode", "Raw")
    m.use_manual_markers = data.get("use_manual_markers", False)
    m.manual_fc_hz = data.get("manual_fc_hz")
    m.manual_fl_hz = data.get("manual_fl_hz")
    m.manual_fh_hz = data.get("manual_fh_hz")

    return m


def save_project(
    project_path: str,
    measurements: List[MeasurementData],
    active_index: int = 0,
    normalized: bool = False,
    notes: str = "",
) -> None:
    """Save full project session state to a .vna file."""
    payload = {
        "version": "1.0",
        "app": "Rohde & Schwarz VNA Filter Analyzer",
        "active_index": active_index,
        "normalized": normalized,
        "notes": notes,
        "measurements": [serialize_measurement(m) for m in measurements],
    }

    with open(project_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_project(
    project_path: str,
) -> Tuple[List[MeasurementData], int, bool, str]:
    """Load project session state from a .vna file.

    Returns:
        Tuple of (measurements_list, active_index, normalized, notes)
    """
    if not os.path.exists(project_path):
        raise FileNotFoundError(f"Project file does not exist: {project_path}")

    with open(project_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    raw_list = payload.get("measurements", [])
    measurements = []
    for idx, item in enumerate(raw_list):
        m = deserialize_measurement(item, index=idx)
        # Re-compute metrics and smoothing
        s21 = m.clean_s_params.get("S21", next(iter(m.clean_s_params.values())))
        s11 = m.clean_s_params.get("S11")
        m.metrics = calculate_filter_metrics(
            m.clean_freq_hz,
            s21,
            s11_db=s11,
            threshold_db=m.bw_threshold_db,
            manual_fc_hz=m.manual_fc_hz if m.use_manual_markers else None,
            manual_fl_hz=m.manual_fl_hz if m.use_manual_markers else None,
            manual_fh_hz=m.manual_fh_hz if m.use_manual_markers else None,
        )
        measurements.append(m)

    active_index = int(payload.get("active_index", 0))
    normalized = bool(payload.get("normalized", False))
    notes = str(payload.get("notes", ""))

    return measurements, active_index, normalized, notes
