from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from .config import AppConfig
from .api import fetch_next_pass
from .log import get_logger

"""
Visibility decision
- DP-1.1.2.2: Filter by time window (rise..set) AND min_elevation_deg using culmination.alt
- DP-1.1.2.3: Collect (id, color) pairs from configured satellites

Maps to:
  FR-1.1.2.*, CN-1.1, CN-1.2
"""

# This function gets the logger for the visibility decision.
_LOG = get_logger(__name__)

# This function parses the altitude from the pass object.
def _parse_alt(value: Any) -> Optional[float]:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            return float(value.strip())
    except (TypeError, ValueError):
        return None
    return None

# This function checks if the satellite is overhead now by checking if the rise time is less than or equal to the current time and the set time is greater than or equal to the current time and the culmination altitude is greater than or equal to the minimum elevation.
def _is_overhead_now(pass_obj: Dict[str, Any], now_utc: int, min_elev: float) -> bool:
    """
    Inclusive time window and minimum-peak-elevation rule:
      rise.utc_timestamp <= now <= set.utc_timestamp  AND  culmination.alt >= min_elev
    """
    try:
        rise = pass_obj["rise"]
        setp = pass_obj["set"]
        culm = pass_obj["culmination"]

        rise_ts = int(rise["utc_timestamp"])
        set_ts = int(setp["utc_timestamp"])

        alt = _parse_alt(culm.get("alt"))
        if alt is None:
            _LOG.error("culmination.alt missing or invalid: %r", culm.get("alt"))
            return False

        return (rise_ts <= now_utc <= set_ts) and (alt >= min_elev)
    except Exception:
        _LOG.error("malformed pass object: %r", pass_obj)
        return False

# This function checks if the satellite is visible now.
def visible_now(
    cfg: AppConfig,
    *,
    fetcher: Callable[[int, float, float], Optional[Dict[str, Any]]] = fetch_next_pass,
    now_fn: Callable[[], float] = time.time,
) -> List[Tuple[int, str]]:
    """
    Return list of (sat_id, color) for satellites considered 'overhead now'
    under the documented rule (DP-1.1.2.2) using pass predictions.

    - Calls fetcher(id, cfg.lat, cfg.lon) per configured id.
    - Uses now_utc = int(now_fn()) for deterministic testing.
    """
    now_utc = int(now_fn())
    results: List[Tuple[int, str]] = []

    for sat_id, color in cfg.satellites.items(): # Iterate over the satellites in the configuration and fetch the pass object.
        pass_obj = fetcher(sat_id, cfg.lat, cfg.lon)
        if pass_obj is None:
            continue
        if _is_overhead_now(pass_obj, now_utc, cfg.min_elevation_deg):
            results.append((sat_id, color))

    return results
