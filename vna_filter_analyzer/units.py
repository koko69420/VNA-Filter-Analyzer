"""Engineering unit conversion and formatting utilities."""

import re
from typing import Optional, Tuple


def format_frequency(hz: float, precision: int = 3, show_unit: bool = True) -> str:
    """Format frequency in Hz into sensible engineering units (Hz, kHz, MHz, GHz).

    Args:
        hz: Frequency in Hertz.
        precision: Decimal precision.
        show_unit: Whether to include the unit suffix.

    Returns:
        Formatted frequency string (e.g. '3.520 GHz', '420.000 MHz').
    """
    if hz is None or not isinstance(hz, (int, float)) or hz != hz:  # NaN check
        return "N/A"

    abs_hz = abs(hz)
    if abs_hz >= 1e9:
        val = hz / 1e9
        unit = "GHz"
    elif abs_hz >= 1e6:
        val = hz / 1e6
        unit = "MHz"
    elif abs_hz >= 1e3:
        val = hz / 1e3
        unit = "kHz"
    else:
        val = hz
        unit = "Hz"

    if show_unit:
        return f"{val:.{precision}f} {unit}"
    return f"{val:.{precision}f}"


def format_bandwidth(hz: float, precision: int = 2, show_unit: bool = True) -> str:
    """Format bandwidth in Hz into sensible engineering units (Hz, kHz, MHz, GHz).

    Args:
        hz: Bandwidth in Hertz.
        precision: Decimal precision.
        show_unit: Whether to include unit string.

    Returns:
        Formatted string (e.g. '420.00 MHz', '1.25 GHz').
    """
    return format_frequency(hz, precision=precision, show_unit=show_unit)


def format_db(val_db: float, precision: int = 2, show_unit: bool = True) -> str:
    """Format a decibel value.

    Args:
        val_db: Value in dB.
        precision: Decimal precision.
        show_unit: Whether to append 'dB'.

    Returns:
        Formatted dB string.
    """
    if val_db is None or not isinstance(val_db, (int, float)) or val_db != val_db:
        return "N/A"
    unit_str = " dB" if show_unit else ""
    return f"{val_db:.{precision}f}{unit_str}"


def format_percentage(val_pct: float, precision: int = 2, show_unit: bool = True) -> str:
    """Format percentage value."""
    if val_pct is None or not isinstance(val_pct, (int, float)) or val_pct != val_pct:
        return "N/A"
    unit_str = " %" if show_unit else ""
    return f"{val_pct:.{precision}f}{unit_str}"


def parse_frequency(text: str) -> Optional[float]:
    """Parse a frequency string with optional engineering unit into Hz.

    Examples:
        '3.52 GHz' -> 3.52e9
        '420 MHz'  -> 4.2e8
        '100 kHz'  -> 1.0e5
        '3520000'  -> 3520000.0

    Returns:
        Frequency in Hz or None if invalid.
    """
    if not text:
        return None
    text = text.strip()
    match = re.match(r"^([-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z]*)$", text)
    if not match:
        return None

    number_str, unit_str = match.groups()
    try:
        val = float(number_str)
    except ValueError:
        return None

    unit = unit_str.lower()
    if unit in ("ghz", "g"):
        return val * 1e9
    elif unit in ("mhz", "m"):
        return val * 1e6
    elif unit in ("khz", "k"):
        return val * 1e3
    elif unit in ("hz", "h", ""):
        return val
    return None
