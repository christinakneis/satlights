import pytest
from pydantic import ValidationError

from src.satlight.config import validate_config


# This function creates a valid raw dictionary for testing.
def _valid_raw(overrides=None):
    base = {
        "lat": 37.8,
        "lon": -122.4,
        "satellites": {25544: "blue", "48915": "pink"},  # mixing int and str keys on purpose
        "outputs": ["stdout", "file:/tmp/passes.log", "tcp:127.0.0.1:9000"],
        # min_elevation_deg omitted to test default=10
    }
    if overrides:
        base.update(overrides)
    return base


# This test checks if the validate_config function validates the latitude, longitude, and minimum elevation.
def test_FR_1_1_1_2__validates_lat_lon_bounds_and_defaults_min_elev_10():
    cfg = validate_config(_valid_raw())
    assert cfg.lat == 37.8
    assert cfg.lon == -122.4
    assert cfg.min_elevation_deg == 10.0  # default applied
    # satellites keys should be normalized to int
    assert set(cfg.satellites.keys()) == {25544, 48915}
    print("✅test_FR_1_1_1_2__validates_lat_lon_bounds_and_defaults_min_elev_10 passed")


# This test checks if the validate_config function rejects disallowed output sinks.
def test_FR_1_1_1_2__rejects_disallowed_output_sinks():
    bad = _valid_raw({"outputs": ["stdout", "udp:1.2.3.4:9999"]})
    with pytest.raises(ValidationError):
        _ = validate_config(bad)
    print("✅test_FR_1_1_1_2__rejects_disallowed_output_sinks passed")


# This test checks if the validate_config function rejects out of range latitude and longitude.
def test_FR_1_1_1_2__rejects_out_of_range_lat_lon():
    with pytest.raises(ValidationError):
        _ = validate_config(_valid_raw({"lat": 123.0}))
    with pytest.raises(ValidationError):
        _ = validate_config(_valid_raw({"lon": -222.0}))
    print("✅test_FR_1_1_1_2__rejects_out_of_range_lat_lon passed")


# This test checks if the validate_config function rejects empty satellites and bad keys.
def test_FR_1_1_1_2__rejects_empty_satellites_and_bad_keys():
    with pytest.raises(ValidationError):
        _ = validate_config(_valid_raw({"satellites": {}}))
    with pytest.raises(ValidationError):
        _ = validate_config(_valid_raw({"satellites": {-1: "red"}}))
    with pytest.raises(ValidationError):
        _ = validate_config(_valid_raw({"satellites": {25544: ""}}))
    print("✅test_FR_1_1_1_2__rejects_empty_satellites_and_bad_keys passed")
