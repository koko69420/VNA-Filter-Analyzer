"""Multi-dialect CSV, Touchstone (.s2p/.s1p), RVITM, and Dassault CST file parser."""

import csv
import glob
import io
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


@dataclass
class ColumnDetection:
    """Detected column mappings and frequency scale."""
    freq_col: Optional[str] = None
    freq_scale_to_hz: float = 1.0  # Multiplier to convert to Hz
    freq_unit_name: str = "Hz"
    s_params: Dict[str, str] = field(default_factory=dict)  # 'S21': col_name, etc.
    confidence: float = 1.0
    detected_delimiters: str = ","


@dataclass
class VNAFileParseResult:
    """Complete result of parsing a VNA data file."""
    file_path: str
    freq_hz: np.ndarray
    s_params: Dict[str, np.ndarray]
    metadata: Dict[str, str] = field(default_factory=dict)
    detection: Optional[ColumnDetection] = None
    raw_dataframe: Optional[pd.DataFrame] = None
    parse_warnings: List[str] = field(default_factory=list)
    measurement_name: Optional[str] = None


def detect_delimiter(file_path: str, max_lines: int = 50) -> str:
    """Sniff CSV delimiter from sample lines."""
    delimiters = [",", ";", "\t", " "]
    counts = {d: 0 for d in delimiters}
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines_checked = 0
        for line in f:
            line_str = line.strip()
            if not line_str or line_str.startswith(("#", "!", "//", "*", "[", "-")):
                continue
            for d in delimiters:
                counts[d] += line_str.count(d)
            lines_checked += 1
            if lines_checked >= max_lines:
                break
    for d in ["\t", ";", ","]:
        if counts[d] > 5:
            return d
    return max(counts, key=counts.get) if any(counts.values()) else ","


def parse_metadata_headers(file_path: str, max_lines: int = 100) -> Dict[str, str]:
    """Extract metadata key-values from VNA comment lines or CST headers."""
    metadata = {}
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f):
            if idx >= max_lines:
                break
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith(("#", "!", "//", "*", "[", ";", "-")):
                clean = re.sub(r"^[\#\!\/\/\*\[\]\;\-\s]+", "", line_str).strip()
                if not clean:
                    continue

                if "rohde" in clean.lower() or "r&s" in clean.lower():
                    metadata["VNA Model"] = clean
                elif "cst" in clean.lower():
                    metadata["Simulation Tool"] = clean
                elif ":" in clean:
                    parts = clean.split(":", 1)
                    k, v = parts[0].strip(), parts[1].strip()
                    if k and v:
                        metadata[k] = v
                elif "=" in clean:
                    parts = clean.split("=", 1)
                    k, v = parts[0].strip(), parts[1].strip()
                    if k and v:
                        metadata[k] = v
            else:
                break
    return metadata


def detect_frequency_column(df: pd.DataFrame) -> Tuple[Optional[str], float, str]:
    """Detect frequency column name, unit multiplier to Hz, and unit name.
    
    Supports R&S VNA, Dassault CST, RVITM, and generic formats.
    """
    col_names = [str(c).strip().strip('"').strip("'") for c in df.columns]

    freq_patterns = [
        # CST: "Frequency / GHz", "Freq. / GHz", "Frequency [GHz]"
        r"^(?:frequency|freq\.?|f)\s*[/\[\(]\s*(ghz|mhz|khz|hz)\s*[\]\)]?$",
        r"^(?:frequency|freq\.?|f)\s*[/]\s*(ghz|mhz|khz|hz)",
        r"^(?:frequency|freq\.?|f)$",
        r"(?:freq|frequency)",
        r"^hz$",
        r"^ghz$",
        r"^mhz$",
    ]

    matched_col = None
    explicit_unit = None

    for pat in freq_patterns:
        for orig_col in df.columns:
            c_str = str(orig_col).strip().strip('"').strip("'")
            match = re.search(pat, c_str, re.IGNORECASE)
            if match:
                matched_col = orig_col
                if match.groups() and match.group(1):
                    explicit_unit = match.group(1).lower()
                break
        if matched_col is not None:
            break

    # If still not found, check the first column if numeric
    if matched_col is None and len(df.columns) > 0:
        first_col = df.columns[0]
        try:
            numeric_vals = pd.to_numeric(df[first_col].dropna().iloc[:20], errors="coerce").dropna()
            if len(numeric_vals) > 0 and numeric_vals.is_monotonic_increasing:
                matched_col = first_col
        except Exception:
            pass

    if matched_col is None:
        return None, 1.0, "Hz"

    unit_multiplier = 1.0
    unit_name = "Hz"

    col_str = str(matched_col).lower()
    if explicit_unit:
        unit_str = explicit_unit
    elif "ghz" in col_str:
        unit_str = "ghz"
    elif "mhz" in col_str:
        unit_str = "mhz"
    elif "khz" in col_str:
        unit_str = "khz"
    elif "hz" in col_str:
        unit_str = "hz"
    else:
        unit_str = None

    # Inspect data values:
    # In RVITM and some CST files, the header might say 'Freq(Hz)' but values are 0.700 to 1.100 (GHz)!
    try:
        sample_vals = pd.to_numeric(df[matched_col].dropna().iloc[:50], errors="coerce").dropna()
        if len(sample_vals) > 0:
            median_val = float(sample_vals.median())
            # If values are small (< 150), they are physically in GHz for RF microwave applications
            if 0.01 <= median_val <= 150.0:
                unit_multiplier = 1e9
                unit_name = "GHz"
            elif 150.0 < median_val <= 50000.0:
                unit_multiplier = 1e6
                unit_name = "MHz"
            elif 50000.0 < median_val <= 1e7:
                unit_multiplier = 1e3
                unit_name = "kHz"
            elif unit_str == "ghz":
                unit_multiplier = 1e9
                unit_name = "GHz"
            elif unit_str == "mhz":
                unit_multiplier = 1e6
                unit_name = "MHz"
            else:
                unit_multiplier = 1.0
                unit_name = "Hz"
    except Exception:
        unit_multiplier = 1.0
        unit_name = "Hz"

    return matched_col, unit_multiplier, unit_name


def detect_s_parameter_columns(df: pd.DataFrame, freq_col: Optional[str]) -> Dict[str, str]:
    """Detect available S-parameter columns.
    
    Supports:
    - Standard VNA: S21, S11, S12, S22, Trc1_S21_dB, S21 [dB], S21(dB), S21 Mag
    - Dassault CST: S2,1, S1,1, S1,2, S2,2, "S2,1 / dB", S(2,1), SZmax(2),Zmax(1)
    - RVITM: 'Data' column
    """
    detected: Dict[str, str] = {}
    target_params = ["S21", "S11", "S12", "S22"]

    # Mapping patterns for CST and VNA formats
    cst_patterns = {
        "S21": [
            r"^(?:trc\d+_)?S21(?:\s*[\(\[/]?\s*(?:db|mag|log\s*mag|magnitude)[\)\]/]?)?$",
            r"S2[,\s]*1",
            r"S\(2[,\s]*1\)",
            r"SZmax\(2\)[,\s]*Zmax\(1\)",
            r"\bS21\b",
        ],
        "S11": [
            r"^(?:trc\d+_)?S11(?:\s*[\(\[/]?\s*(?:db|mag|log\s*mag|magnitude)[\)\]/]?)?$",
            r"S1[,\s]*1",
            r"S\(1[,\s]*1\)",
            r"SZmax\(1\)[,\s]*Zmax\(1\)",
            r"\bS11\b",
        ],
        "S12": [
            r"^(?:trc\d+_)?S12(?:\s*[\(\[/]?\s*(?:db|mag|log\s*mag|magnitude)[\)\]/]?)?$",
            r"S1[,\s]*2",
            r"S\(1[,\s]*2\)",
            r"SZmax\(1\)[,\s]*Zmax\(2\)",
            r"\bS12\b",
        ],
        "S22": [
            r"^(?:trc\d+_)?S22(?:\s*[\(\[/]?\s*(?:db|mag|log\s*mag|magnitude)[\)\]/]?)?$",
            r"S2[,\s]*2",
            r"S\(2[,\s]*2\)",
            r"SZmax\(2\)[,\s]*Zmax\(2\)",
            r"\bS22\b",
        ],
    }

    for param, patterns in cst_patterns.items():
        for pat in patterns:
            found = False
            for col in df.columns:
                if col == freq_col or col in detected.values():
                    continue
                col_clean = str(col).strip().strip('"').strip("'")
                if re.search(pat, col_clean, re.IGNORECASE):
                    detected[param] = col
                    found = True
                    break
            if found:
                break

    # If only 2 columns in df and non-freq col is named 'Data' or similar
    if not detected and len(df.columns) == 2:
        other_col = df.columns[1] if df.columns[0] == freq_col else df.columns[0]
        detected["S21"] = other_col

    return detected


def detect_columns(df: pd.DataFrame) -> ColumnDetection:
    """Run full automatic column detection on dataframe."""
    freq_col, mult, unit_name = detect_frequency_column(df)
    s_params = detect_s_parameter_columns(df, freq_col)
    confidence = 1.0 if (freq_col and "S21" in s_params) else (0.6 if freq_col else 0.2)
    return ColumnDetection(
        freq_col=freq_col,
        freq_scale_to_hz=mult,
        freq_unit_name=unit_name,
        s_params=s_params,
        confidence=confidence,
    )


def parse_touchstone(file_path: str) -> Optional[VNAFileParseResult]:
    """Attempt to parse Touchstone (.s2p, .s1p) file format from VNA or Dassault CST."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in (".s2p", ".s1p", ".snp"):
        return None

    try:
        freq_unit_multiplier = 1.0
        format_code = "DB"  # DB, MA (mag-angle), RI (real-imag)
        is_s2p = ext == ".s2p"
        metadata = {}
        data_rows = []

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                if line_str.startswith("!"):
                    comment = line_str[1:].strip()
                    if ":" in comment:
                        parts = comment.split(":", 1)
                        metadata[parts[0].strip()] = parts[1].strip()
                    elif not metadata.get("VNA Model") and ("rohde" in comment.lower() or "r&s" in comment.lower() or "cst" in comment.lower()):
                        metadata["Tool / Model"] = comment
                    continue
                if line_str.startswith("#"):
                    tokens = line_str[1:].strip().split()
                    for t in tokens:
                        t_upper = t.upper()
                        if t_upper == "GHZ":
                            freq_unit_multiplier = 1e9
                        elif t_upper == "MHZ":
                            freq_unit_multiplier = 1e6
                        elif t_upper == "KHZ":
                            freq_unit_multiplier = 1e3
                        elif t_upper == "HZ":
                            freq_unit_multiplier = 1.0
                        elif t_upper in ("DB", "MA", "RI"):
                            format_code = t_upper
                    continue

                tokens = line_str.split()
                if tokens:
                    try:
                        row = [float(t) for t in tokens]
                        data_rows.append(row)
                    except ValueError:
                        continue

        if not data_rows:
            return None

        arr = np.array(data_rows, dtype=np.float64)
        freq_hz = arr[:, 0] * freq_unit_multiplier
        s_params: Dict[str, np.ndarray] = {}

        if is_s2p and arr.shape[1] >= 9:
            s11_1, s11_2 = arr[:, 1], arr[:, 2]
            s21_1, s21_2 = arr[:, 3], arr[:, 4]
            s12_1, s12_2 = arr[:, 5], arr[:, 6]
            s22_1, s22_2 = arr[:, 7], arr[:, 8]

            def to_db(v1, v2):
                if format_code == "DB":
                    return v1
                elif format_code == "MA":
                    mag = np.maximum(v1, 1e-12)
                    return 20.0 * np.log10(mag)
                else:  # RI
                    mag = np.sqrt(v1**2 + v2**2)
                    mag = np.maximum(mag, 1e-12)
                    return 20.0 * np.log10(mag)

            s_params["S11"] = to_db(s11_1, s11_2)
            s_params["S21"] = to_db(s21_1, s21_2)
            s_params["S12"] = to_db(s12_1, s12_2)
            s_params["S22"] = to_db(s22_1, s22_2)

        elif arr.shape[1] >= 3:
            s11_1, s11_2 = arr[:, 1], arr[:, 2]
            if format_code == "DB":
                s_params["S11"] = s11_1
            else:
                mag = np.sqrt(s11_1**2 + s11_2**2) if format_code == "RI" else s11_1
                s_params["S11"] = 20.0 * np.log10(np.maximum(mag, 1e-12))

        detection = ColumnDetection(
            freq_col="Frequency",
            freq_scale_to_hz=1.0,
            freq_unit_name="Hz",
            s_params={k: k for k in s_params},
            confidence=1.0,
        )

        return VNAFileParseResult(
            file_path=file_path,
            freq_hz=freq_hz,
            s_params=s_params,
            metadata=metadata,
            detection=detection,
            raw_dataframe=pd.DataFrame({"Frequency": freq_hz, **s_params}),
        )
    except Exception:
        return None


def is_rvitm_style(file_path: str) -> bool:
    """Check if file matches the RVITM format (e.g. S21_with_DGS, S11_without_DGS)."""
    fname = os.path.basename(file_path)
    if re.search(r"^S\d\d_", fname, re.IGNORECASE):
        return True
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline().strip()
            if "freq" in first_line.lower() and "data" in first_line.lower():
                return True
    except Exception:
        pass
    return False


def parse_rvitm_directory(dir_path: str) -> List[VNAFileParseResult]:
    """Scan an RVITM folder, group sibling S-parameter files, and return parsed measurements.
    
    Pairs e.g.:
      S11_with_DGS, S12_with_DGS, S21_with_DGS, S22_with_DGS -> 'DGS'
      S11_without_DGS, S12_without_DGS, S21_without_DGS, S22_without_DGS -> 'Without DGS'
    """
    if not os.path.isdir(dir_path):
        return []

    files = sorted([os.path.join(dir_path, f) for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))])
    groups: Dict[str, Dict[str, str]] = {}

    for fpath in files:
        fname = os.path.basename(fpath)
        match = re.search(r'(S\d\d)', fname, re.IGNORECASE)
        if not match:
            continue
        sparam = match.group(1).upper()
        
        # Clean condition name
        if "without" in fname.lower() or "wodgs" in fname.lower():
            cond = "Without DGS"
        elif "with_dgs" in fname.lower() or "dgs" in fname.lower():
            cond = "DGS"
        else:
            cond = re.sub(r'S\d\d_?', '', fname).strip('_') or "Measurement"

        if cond not in groups:
            groups[cond] = {}
        groups[cond][sparam] = fpath

    results: List[VNAFileParseResult] = []

    for cond_name, sparams_map in groups.items():
        # Require at least one S-parameter
        if not sparams_map:
            continue

        # Choose primary file (prefer S21)
        primary_sp = "S21" if "S21" in sparams_map else next(iter(sparams_map.keys()))
        primary_fpath = sparams_map[primary_sp]

        # Read primary file
        df_prim = pd.read_csv(primary_fpath, sep=r"\s+", engine="python")
        df_prim.columns = [str(c).strip().strip('"') for c in df_prim.columns]
        
        freq_raw = df_prim.iloc[:, 0].to_numpy(dtype=np.float64)
        mult = 1e9 if np.median(freq_raw) < 150.0 else 1.0
        freq_hz = freq_raw * mult

        s_params: Dict[str, np.ndarray] = {
            primary_sp: df_prim.iloc[:, 1].to_numpy(dtype=np.float64)
        }

        # Read sibling files
        for sp, sibling_path in sparams_map.items():
            if sp == primary_sp:
                continue
            try:
                df_sib = pd.read_csv(sibling_path, sep=r"\s+", engine="python")
                df_sib.columns = [str(c).strip().strip('"') for c in df_sib.columns]
                sib_f = df_sib.iloc[:, 0].to_numpy(dtype=np.float64) * mult
                sib_vals = df_sib.iloc[:, 1].to_numpy(dtype=np.float64)
                
                # Align to primary frequency grid
                if len(sib_f) == len(freq_hz) and np.allclose(sib_f, freq_hz, rtol=1e-4):
                    s_params[sp] = sib_vals
                else:
                    s_params[sp] = np.interp(freq_hz, sib_f, sib_vals)
            except Exception:
                pass

        metadata = {
            "Format": "RVITM Laboratory Export",
            "Condition": cond_name,
            "Points": str(len(freq_hz)),
            "Source Folder": dir_path,
        }

        detection = ColumnDetection(
            freq_col="Frequency",
            freq_scale_to_hz=mult,
            freq_unit_name="GHz" if mult == 1e9 else "Hz",
            s_params={k: k for k in s_params},
            confidence=1.0,
        )

        results.append(VNAFileParseResult(
            file_path=primary_fpath,
            freq_hz=freq_hz,
            s_params=s_params,
            metadata=metadata,
            detection=detection,
            raw_dataframe=pd.DataFrame({"Frequency": freq_hz, **s_params}),
            measurement_name=cond_name,
        ))

    return results


def parse_vna_file(
    file_path: str,
    freq_col: Optional[str] = None,
    freq_unit_mult: Optional[float] = None,
    s21_col: Optional[str] = None,
    s11_col: Optional[str] = None,
    s12_col: Optional[str] = None,
    s22_col: Optional[str] = None,
) -> VNAFileParseResult:
    """Parse VNA CSV, Touchstone, RVITM, or Dassault CST measurement files."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Measurement file not found: {file_path}")

    # 1. Touchstone check
    touchstone_result = parse_touchstone(file_path)
    if touchstone_result is not None:
        return touchstone_result

    # 2. RVITM File & Sibling Auto-Merging Check
    fname = os.path.basename(file_path)
    parent_dir = os.path.dirname(os.path.abspath(file_path))
    match_sp = re.search(r'(S\d\d)', fname, re.IGNORECASE)

    if match_sp and is_rvitm_style(file_path):
        # Determine condition
        if "without" in fname.lower() or "wodgs" in fname.lower():
            cond_name = "Without DGS"
            pat_suffix = r"(?:without|wodgs)"
        elif "with_dgs" in fname.lower() or "dgs" in fname.lower():
            cond_name = "DGS"
            pat_suffix = r"(?:with_dgs|dgs)"
        else:
            cond_name = re.sub(r'S\d\d_?', '', fname).strip('_') or "Measurement"
            pat_suffix = None

        # Look for sibling files in parent_dir
        sibling_map = {}
        for sib in os.listdir(parent_dir):
            sib_path = os.path.join(parent_dir, sib)
            if not os.path.isfile(sib_path):
                continue
            sib_match = re.search(r'(S\d\d)', sib, re.IGNORECASE)
            if not sib_match:
                continue
            sib_sp = sib_match.group(1).upper()
            if pat_suffix:
                if re.search(pat_suffix, sib, re.IGNORECASE):
                    sibling_map[sib_sp] = sib_path
            else:
                sibling_map[sib_sp] = sib_path

        # If siblings found, parse as group
        if len(sibling_map) >= 2:
            df_prim = pd.read_csv(file_path, sep=r"\s+", engine="python")
            df_prim.columns = [str(c).strip().strip('"') for c in df_prim.columns]
            f_raw = df_prim.iloc[:, 0].to_numpy(dtype=np.float64)
            mult = 1e9 if np.median(f_raw) < 150.0 else 1.0
            freq_hz = f_raw * mult

            curr_sp = match_sp.group(1).upper()
            s_params: Dict[str, np.ndarray] = {curr_sp: df_prim.iloc[:, 1].to_numpy(dtype=np.float64)}

            for sp, s_fpath in sibling_map.items():
                if sp == curr_sp:
                    continue
                try:
                    df_sib = pd.read_csv(s_fpath, sep=r"\s+", engine="python")
                    df_sib.columns = [str(c).strip().strip('"') for c in df_sib.columns]
                    sib_f = df_sib.iloc[:, 0].to_numpy(dtype=np.float64) * mult
                    sib_vals = df_sib.iloc[:, 1].to_numpy(dtype=np.float64)
                    if len(sib_f) == len(freq_hz) and np.allclose(sib_f, freq_hz, rtol=1e-4):
                        s_params[sp] = sib_vals
                    else:
                        s_params[sp] = np.interp(freq_hz, sib_f, sib_vals)
                except Exception:
                    pass

            detection = ColumnDetection(
                freq_col="Frequency",
                freq_scale_to_hz=mult,
                freq_unit_name="GHz" if mult == 1e9 else "Hz",
                s_params={k: k for k in s_params},
                confidence=1.0,
            )
            return VNAFileParseResult(
                file_path=file_path,
                freq_hz=freq_hz,
                s_params=s_params,
                metadata={"Format": "RVITM / CST Multi-file", "Condition": cond_name},
                detection=detection,
                raw_dataframe=pd.DataFrame({"Frequency": freq_hz, **s_params}),
                measurement_name=cond_name,
            )

    # 3. Standard CSV / Dassault CST 1D ASCII File
    delim = detect_delimiter(file_path)
    metadata = parse_metadata_headers(file_path)

    # Scan for header line, skipping comments and CST decorative dashes '-----'
    header_line_idx = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f):
            line_str = line.strip()
            if not line_str or line_str.startswith(("#", "!", "//", "*", "[", "-")):
                header_line_idx = idx + 1
            else:
                break

    try:
        df = pd.read_csv(
            file_path,
            sep=delim,
            skiprows=header_line_idx,
            skipinitialspace=True,
            encoding="utf-8",
            on_bad_lines="skip",
        )
    except Exception:
        df = pd.read_csv(
            file_path,
            sep=None,
            engine="python",
            skiprows=header_line_idx,
            encoding="utf-8",
            on_bad_lines="skip",
        )

    # Clean column names
    df.columns = [str(c).strip().strip('"').strip("'") for c in df.columns]

    # Filter out any non-numeric separator rows (e.g. CST dashed divider lines)
    if len(df) > 0:
        first_col = df.columns[0]
        numeric_mask = pd.to_numeric(df[first_col], errors="coerce").notna()
        if not numeric_mask.all():
            df = df[numeric_mask].reset_index(drop=True)

    detection = detect_columns(df)
    detection.detected_delimiters = delim

    selected_freq_col = freq_col or detection.freq_col
    selected_mult = freq_unit_mult if freq_unit_mult is not None else detection.freq_scale_to_hz

    if selected_freq_col is None or selected_freq_col not in df.columns:
        raise ValueError(
            f"Could not identify a frequency column in '{os.path.basename(file_path)}'. "
            f"Available columns: {list(df.columns)}"
        )

    freq_series = pd.to_numeric(df[selected_freq_col], errors="coerce")
    freq_hz = freq_series.to_numpy(dtype=np.float64) * selected_mult

    # Build S-parameter dict
    s_col_map = {
        "S21": s21_col or detection.s_params.get("S21"),
        "S11": s11_col or detection.s_params.get("S11"),
        "S12": s12_col or detection.s_params.get("S12"),
        "S22": s22_col or detection.s_params.get("S22"),
    }

    s_params: Dict[str, np.ndarray] = {}
    warnings: List[str] = []

    for param, col_name in s_col_map.items():
        if col_name and col_name in df.columns:
            s_series = pd.to_numeric(df[col_name], errors="coerce")
            s_params[param] = s_series.to_numpy(dtype=np.float64)

    if not s_params:
        # Check if single value column like 'Data'
        if len(df.columns) == 2:
            val_col = df.columns[1] if df.columns[0] == selected_freq_col else df.columns[0]
            sp_name = match_sp.group(1).upper() if match_sp else "S21"
            s_params[sp_name] = pd.to_numeric(df[val_col], errors="coerce").to_numpy(dtype=np.float64)

    if not s_params:
        raise ValueError(
            f"Could not identify any S-parameter columns in '{os.path.basename(file_path)}'. "
            f"Columns found: {list(df.columns)}"
        )

    return VNAFileParseResult(
        file_path=file_path,
        freq_hz=freq_hz,
        s_params=s_params,
        metadata=metadata,
        detection=detection,
        raw_dataframe=df,
        parse_warnings=warnings,
    )
