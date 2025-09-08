from __future__ import annotations

from typing import Optional, Any, Callable

from src.satlight.config import AppConfig
from src.satlight.visibility import visible_now


# This function creates a fake fetcher factory.
def _fake_fetcher_factory(
    payload_by_id: dict[int, Optional[dict[str, Any]]],
) -> Callable[[int, float, float], Optional[dict[str, Any]]]:
    def _fetch(id_: int, lat: float, lon: float) -> Optional[dict[str, Any]]:
        return payload_by_id.get(id_)

    return _fetch


# This function creates a fake configuration.
def _cfg(min_elev: float = 10.0) -> AppConfig:
    return AppConfig(
        lat=37.8,
        lon=-122.4,
        satellites={25544: "blue", 48915: "pink"},
        outputs=["stdout"],
        min_elevation_deg=min_elev,
    )


# This test checks if the visible_now function includes satellites inside the window and with a peak greater than or equal to the minimum elevation.
def test_FR_1_1_2_2__includes_inside_window_and_peak_ge_min(monkeypatch):
    from src.satlight.visibility import clear_cache_for_tests
    clear_cache_for_tests()  # Clear cache before test
    
    # now between rise and set
    now = 1500
    monkeypatch.setattr("time.time", lambda: float(now))

    payload = {
        25544: {
            "rise": {"utc_timestamp": 1000, "alt": "10.00"},
            "culmination": {"utc_timestamp": 1400, "alt": "46.00"},
            "set": {"utc_timestamp": 2000, "alt": "10.00"},
            "norad_id": 25544,
        },
        48915: None,  # simulate API error for the other sat
    }
    fetcher = _fake_fetcher_factory(payload)
    res = visible_now(_cfg(min_elev=10.0), fetcher=fetcher, now_fn=lambda: float(now))
    assert (25544, "blue") in res
    # 48915 absent because fetcher returned None
    assert all(sid != 48915 for sid, _ in res)
    print("\n.✅test_FR_1_1_2_2__includes_inside_window_and_peak_ge_min passed")


# This test checks if the visible_now function excludes satellites if the peak is below the minimum elevation even when inside the window.
def test_FR_1_1_2_2__excludes_if_peak_below_min_even_when_inside_window(monkeypatch):
    from src.satlight.visibility import clear_cache_for_tests
    clear_cache_for_tests()  # Clear cache before test
    
    now = 1500
    monkeypatch.setattr("time.time", lambda: float(now))

    payload = {
        25544: {
            "rise": {"utc_timestamp": 1000, "alt": "10.00"},
            "culmination": {"utc_timestamp": 1400, "alt": "9.90"},  # below 10
            "set": {"utc_timestamp": 2000, "alt": "10.00"},
            "norad_id": 25544,
        }
    }
    fetcher = _fake_fetcher_factory(payload)
    res = visible_now(_cfg(min_elev=10.0), fetcher=fetcher, now_fn=lambda: float(now))
    assert res == []
    print("✅test_FR_1_1_2_2__excludes_if_peak_below_min_even_when_inside_window passed")


# This test checks if the visible_now function includes satellites exactly at the rise and set edges.
def test_FR_1_1_2_2__includes_exactly_at_rise_and_set_edges():
    from src.satlight.visibility import clear_cache_for_tests
    clear_cache_for_tests()  # Clear cache before test
    
    cfg = _cfg(min_elev=10.0)
    # One pass object used for both sub-cases; peak meets threshold
    pass_obj = {
        "rise": {"utc_timestamp": 1000, "alt": "10.00"},
        "culmination": {"utc_timestamp": 1400, "alt": "20.00"},
        "set": {"utc_timestamp": 2000, "alt": "10.00"},
        "norad_id": 25544,
    }

    # now == rise edge
    res1 = visible_now(
        cfg,
        fetcher=_fake_fetcher_factory({25544: pass_obj, 48915: None}),
        now_fn=lambda: float(1000),
    )
    assert (25544, "blue") in res1

    # now == set edge
    res2 = visible_now(
        cfg,
        fetcher=_fake_fetcher_factory({25544: pass_obj}),
        now_fn=lambda: float(2000),
    )
    assert (25544, "blue") in res2
    print("✅test_FR_1_1_2_2__includes_exactly_at_rise_and_set_edges passed")


# This test checks if the visible_now function maps IDs to configured colors and returns a list of pairs.
def test_FR_1_1_2_3__maps_ids_to_configured_colors_and_returns_list_of_pairs():
    cfg = _cfg(min_elev=10.0)
    payload = {
        25544: {
            "rise": {"utc_timestamp": 1000, "alt": "10.00"},
            "culmination": {"utc_timestamp": 1400, "alt": "50.00"},
            "set": {"utc_timestamp": 2000, "alt": "10.00"},
            "norad_id": 25544,
        },
        48915: {
            "rise": {"utc_timestamp": 3000, "alt": "10.00"},
            "culmination": {"utc_timestamp": 3200, "alt": "5.00"},  # below min => excluded
            "set": {"utc_timestamp": 3300, "alt": "10.00"},
            "norad_id": 48915,
        },
    }
    res = visible_now(cfg, fetcher=_fake_fetcher_factory(payload), now_fn=lambda: float(1500))
    # Only the first should pass; and it must carry the configured color
    assert res == [(25544, "blue")]
    print("✅test_FR_1_1_2_3__maps_ids_to_configured_colors_and_returns_list_of_pairs passed")
