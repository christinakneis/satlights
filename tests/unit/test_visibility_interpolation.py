from typing import Dict, Any

from src.satlight.visibility import visible_now, clear_cache_for_tests
from src.satlight.config import AppConfig


# This function creates a pass object with the given rise, culmination, and set times and altitudes.
def _make_pass(
    rise_ts: int, culm_ts: int, set_ts: int, rise_alt: float, culm_alt: float, set_alt: float
) -> Dict[str, Any]:
    return {
        "rise": {"utc_timestamp": rise_ts, "alt": str(rise_alt)},
        "culmination": {"utc_timestamp": culm_ts, "alt": str(culm_alt)},
        "set": {"utc_timestamp": set_ts, "alt": str(set_alt)},
        "visible": True,
        "norad_id": 12345,
    }


# This test checks if the satellite is not overhead before the threshold.
def test_interp_before_threshold_no_emit(monkeypatch):
    """
    Before: now < t_enter, even if peak >= min_elev, we should NOT emit.
    rise=1000@10°, peak=1100@46°, set=1200@10°, min=25°.
    t_enter ≈ 1042, so now=1030 -> no emission.
    """
    clear_cache_for_tests()

    cfg = AppConfig(
        lat=37.8,
        lon=-122.4,
        satellites={12345: "blue"},
        outputs=["stdout"],
        min_elevation_deg=25.0,
    )
    pass_obj = _make_pass(1000, 1100, 1200, 10.0, 46.0, 10.0)

    def fake_fetcher(_id: int, _lat: float, _lon: float):
        return pass_obj

    # now before threshold entry
    now_val = 1030
    res = visible_now(
        cfg,
        fetcher=fake_fetcher,
        now_fn=lambda: now_val,
        mono_fn=lambda: 0.0,
    )
    assert res == []
    print("\n.✅test_interp_before_threshold_no_emit passed")


# This test checks if the satellite is overhead between the enter and exit times.
def test_interp_between_enter_and_exit_emit(monkeypatch):
    """
    Inside: t_enter <= now <= t_exit -> we DO emit.
    Using same pass as above; pick now=1100 (at culmination) -> emit.
    """
    clear_cache_for_tests()

    cfg = AppConfig(
        lat=37.8,
        lon=-122.4,
        satellites={12345: "blue"},
        outputs=["stdout"],
        min_elevation_deg=25.0,
    )
    pass_obj = _make_pass(1000, 1100, 1200, 10.0, 46.0, 10.0)
    print("✅test_interp_between_enter_and_exit_emit passed")

    # At t_enter (inclusive)
    def fake_fetcher(_id: int, _lat: float, _lon: float):
        return pass_obj

    res = visible_now(
        cfg,
        fetcher=fake_fetcher,
        now_fn=lambda: 1100,  # exactly at peak
        mono_fn=lambda: 0.0,
    )
    assert res == [(12345, "blue")]
    print("✅test_interp_between_enter_and_exit_emit passed")


# This test checks if the satellite is overhead at the enter and exit times.
def test_interp_edges_inclusive():
    """
    Edge inclusion: choose threshold so the crossings land exactly at half-way points.
    rise=1000@10°, peak=1100@46°, set=1200@10°, pick min=28°.
    Ascend fraction (10->46): (28-10)/(46-10)=18/36=0.5 => t_enter=1050
    Descend fraction (46->10): (46-28)/36=18/36=0.5 => t_exit=1150
    """
    clear_cache_for_tests()

    cfg = AppConfig(
        lat=0.0,
        lon=0.0,
        satellites={12345: "green"},
        outputs=["stdout"],
        min_elevation_deg=28.0,
    )
    pass_obj = _make_pass(1000, 1100, 1200, 10.0, 46.0, 10.0)

    def fake_fetcher(_id: int, _lat: float, _lon: float):
        return pass_obj

    # At t_enter (inclusive)
    res_enter = visible_now(
        cfg,
        fetcher=fake_fetcher,
        now_fn=lambda: 1050,
        mono_fn=lambda: 0.0,
    )
    assert res_enter == [(12345, "green")]

    # At t_exit (inclusive)
    res_exit = visible_now(
        cfg,
        fetcher=fake_fetcher,
        now_fn=lambda: 1150,
        mono_fn=lambda: 0.0,
    )
    assert res_exit == [(12345, "green")]

    # After t_exit (exclusive)
    res_after = visible_now(
        cfg,
        fetcher=fake_fetcher,
        now_fn=lambda: 1151,
        mono_fn=lambda: 0.0,
    )
    assert res_after == []
    print("✅test_interp_edges_inclusive passed")
