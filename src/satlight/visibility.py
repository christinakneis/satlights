from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass

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


#
# Simple in-memory cache: one entry per satellite.
# We cache the latest pass object until its "set" time. If fetch fails,
# we set a retry_after time to avoid hammering the API (helps with 429s).
#
@dataclass
class _CacheEntry:
    pass_obj: Dict[str, Any]  # raw pass object
    set_ts: int  # cached pass 'set' timestamp
    retry_after: float = 0.0  # monotonic time; don't refetch before this


_CACHE: Dict[int, _CacheEntry] = {}
_RR_IDX: int = 0  # round-robin start index across ticks


def clear_cache_for_tests() -> None:  # exported for unit tests
    _CACHE.clear()
    global _RR_IDX
    _RR_IDX = 0


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


def _extract_set_ts(pass_obj: Dict[str, Any]) -> Optional[int]:
    try:
        set_ts = int(pass_obj["set"]["utc_timestamp"])
        return set_ts
    except Exception:
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


# This function gets the pass object with cache.
def _get_pass_with_cache(
    sat_id: int,
    cfg: AppConfig,
    now_utc: int,
    *,
    fetcher: Callable[[int, float, float], Optional[Dict[str, Any]]],
    mono: Callable[[], float],
) -> Optional[Dict[str, Any]]:
    """
    Return a pass_obj using cache when possible; otherwise fetch and cache.
    - Reuse cached pass until its set time.
    - After a failed fetch, back off for ~60 s before trying again.
    """
    entry = _CACHE.get(sat_id)
    if entry:
        # If we have a valid pass and we're still before its set time, reuse it.
        if now_utc <= entry.set_ts:
            return entry.pass_obj
        # If we're before retry_after (monotonic clock), skip calling the API now.
        if mono() < entry.retry_after:
            return None

    # Either no cache, expired pass, or backoff elapsed: try to fetch
    pass_obj = fetcher(sat_id, cfg.lat, cfg.lon)
    if pass_obj is None:
        # Set/refresh backoff (60 s) to avoid hammering (helps with 429).
        backoff_until = mono() + 60.0
        if entry:
            entry.retry_after = backoff_until
            _CACHE[sat_id] = entry
        else:
            _CACHE[sat_id] = _CacheEntry(pass_obj={}, set_ts=0, retry_after=backoff_until)
        return None

    set_ts = _extract_set_ts(pass_obj)
    if set_ts is None:
        # Bad pass shape; don't cache long-term
        return pass_obj

    _CACHE[sat_id] = _CacheEntry(pass_obj=pass_obj, set_ts=set_ts, retry_after=0.0)
    return pass_obj


# This function checks if the satellite is visible now.
def visible_now(
    cfg: AppConfig,
    *,
    fetcher: Callable[[int, float, float], Optional[Dict[str, Any]]] = fetch_next_pass,
    now_fn: Callable[[], float] = time.time,
    mono_fn: Callable[[], float] = time.monotonic,
    max_fetches_per_tick: Optional[int] = None,
) -> List[Tuple[int, str]]:
    """
    Return list of (sat_id, color) for satellites considered 'overhead now'
    under the documented rule (DP-1.1.2.2) using pass predictions.

    - Calls fetcher(id, cfg.lat, cfg.lon) per configured id.
    - Uses now_utc = int(now_fn()) for deterministic testing.
    """
    now_utc = int(now_fn())
    results: List[Tuple[int, str]] = []

    # Determine round-robin order so we don't hammer the API for all sats at once.
    sat_items = list(cfg.satellites.items())
    n = len(sat_items)
    if n == 0:
        return results

    global _RR_IDX
    start = _RR_IDX % n
    ordered = sat_items[start:] + sat_items[:start]

    fetch_budget = max_fetches_per_tick if max_fetches_per_tick is not None else n

    for sat_id, color in ordered:
        # Try cache first; only fetch if we still have budget and cache is unusable.
        entry = _CACHE.get(sat_id)
        pass_obj: Optional[Dict[str, Any]] = None
        if entry and now_utc <= entry.set_ts:
            pass_obj = entry.pass_obj
        elif mono_fn() < (entry.retry_after if entry else 0.0):
            pass_obj = None  # in backoff
        else:
            if fetch_budget > 0:
                pass_obj = _get_pass_with_cache(
                    sat_id, cfg, now_utc, fetcher=fetcher, mono=mono_fn
                )
                fetch_budget -= 1
            else:
                # No budget left this tick; skip fetching this satellite now.
                pass_obj = None

        if pass_obj is None:
            continue
        if _is_overhead_now(pass_obj, now_utc, cfg.min_elevation_deg):
            results.append((sat_id, color))

    # Advance round-robin pointer for the next tick
    _RR_IDX = (_RR_IDX + 1) % n

    return results
