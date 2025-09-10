from __future__ import annotations

import time
import random
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass

from .config import AppConfig
from .api import fetch_next_pass
from .log import get_logger

"""
Visibility decision
- DP-1.1.2.2: Filter by time window (rise..set) AND min_elevation_deg using linear interpolation
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
    pass_obj: Optional[Dict[str, Any]]  # raw pass object (None if none cached yet)
    set_ts: int  # cached pass 'set' timestamp (0 if unknown)
    retry_after: float = 0.0  # monotonic time; don't refetch before this
    fail_streak: int = 0  # consecutive failures for exponential backoff


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


# This function converts a value to an integer.
def _safe_int(v: Any) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None


# This function clamps (limits) a value between a minimum and maximum. This is used to ensure that the value is within the range of min_elevation_deg to 90 degrees.
def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# This function calculates the time when a line crosses a certain altitude using linear interpolation.
def _cross_time(t1: int, a1: float, t2: int, a2: float, m: float) -> Optional[int]:
    """
    Return the timestamp (int) when a line between (t1,a1) -> (t2,a2) crosses altitude m.
    If the segment is flat:
      - if a1 >= m: crossing occurs at t1 (we're already above m)
      - else: no crossing on this segment
    If the crossing fraction is outside [0,1], return None (no crossing on this segment).
    """
    if a1 == a2:
        return t1 if a1 >= m else None
    f = (m - a1) / (a2 - a1)
    if f < 0.0 or f > 1.0:
        return None
    # Use nearest-int; timestamps are seconds and our 10 s cadence makes ±1 s irrelevant.
    return int(round(t1 + f * (t2 - t1)))


# This function calculates the time window during which the altitude is greater than or equal to the minimum elevation using linear interpolation.
def _compute_threshold_window(
    pass_obj: Dict[str, Any], min_elev: float
) -> Optional[Tuple[int, int]]:
    """
    Compute the inclusive window [t_enter, t_exit] during which altitude >= min_elev,
    using linear interpolation between rise->culmination and culmination->set.
    Returns None if the pass never reaches min_elev.
    """
    try:
        rise = pass_obj["rise"]
        culm = pass_obj["culmination"]
        setp = pass_obj["set"]

        tr = _safe_int(rise.get("utc_timestamp"))
        tc = _safe_int(culm.get("utc_timestamp"))
        ts = _safe_int(setp.get("utc_timestamp"))
        if tr is None or tc is None or ts is None:
            return None

        ar = _parse_alt(rise.get("alt"))
        ac = _parse_alt(culm.get("alt"))
        aS = _parse_alt(setp.get("alt"))
        if ar is None or ac is None or aS is None:
            return None

        # If the peak never reaches min_elev, the pass never qualifies.
        if ac < min_elev:
            return None

        # Ascending (rise -> culmination): when do we first cross up through min_elev?
        if ar >= min_elev:
            t_enter = tr  # already above threshold at rise
        else:
            t_enter_result = _cross_time(tr, ar, tc, ac, min_elev)
            if t_enter_result is None:
                return None  # couldn't cross up (shouldn't happen if ac >= min_elev)
            t_enter = t_enter_result

        # Descending (culmination -> set): when do we fall back below min_elev?
        if aS >= min_elev:
            t_exit = ts  # stay above threshold until set
        else:
            t_exit_result = _cross_time(tc, ac, ts, aS, min_elev)
            if t_exit_result is None:
                t_exit = ts  # conservative: treat remainder until set as above
            else:
                t_exit = t_exit_result

        return (t_enter, t_exit)
    except Exception:
        return None


# This function checks if the satellite is overhead now by checking if the time window is within the current time.
def _is_overhead_now(pass_obj: Dict[str, Any], now_utc: int, min_elev: float) -> bool:
    """
    Interpolation rule (DP-1.1.2.2, refined):
      Compute [t_enter, t_exit] where the pass is at/above min_elev via linear interpolation
      between (rise->culmination) and (culmination->set). Consider 'overhead now' iff
      t_enter <= now_utc <= t_exit (inclusive).
    """
    window = _compute_threshold_window(pass_obj, min_elev)
    if window is None:
        return False
    t_enter, t_exit = window
    return t_enter <= now_utc <= t_exit


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
        # Exponential backoff with jitter: base 60s, cap at 3600s
        base = 60.0
        streak = (entry.fail_streak + 1) if entry else 1
        delay = min(3600.0, base * (2 ** (streak - 1)))
        jitter = delay * 0.1 * (2 * random.random() - 1.0)  # ±10%
        backoff_until = mono() + max(1.0, delay + jitter)
        new_entry = entry or _CacheEntry(pass_obj=None, set_ts=0)
        new_entry.retry_after = backoff_until
        new_entry.fail_streak = streak
        _CACHE[sat_id] = new_entry
        return None

    set_ts = _extract_set_ts(pass_obj)
    if set_ts is None:
        # Bad pass shape; don't cache long-term
        # Reset failure streak on "success" but no set time; still return pass.
        new_entry = entry or _CacheEntry(pass_obj=None, set_ts=0)
        new_entry.pass_obj = pass_obj
        new_entry.set_ts = 0
        new_entry.retry_after = 0.0
        new_entry.fail_streak = 0
        _CACHE[sat_id] = new_entry
        return pass_obj

    # Success: cache until set time; clear backoff.
    _CACHE[sat_id] = _CacheEntry(pass_obj=pass_obj, set_ts=set_ts, retry_after=0.0, fail_streak=0)
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

    # Determine the fetch budget for this tick.
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
                pass_obj = _get_pass_with_cache(sat_id, cfg, now_utc, fetcher=fetcher, mono=mono_fn)
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
